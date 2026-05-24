"""
Contract client. Signs and submits rebalance() transactions to the on-chain
RebalanceExecutor, then decodes the resulting events into a plain-English receipt.

Keys are read ONLY from process env at call time (os.getenv). Never from disk,
never logged, never written to any file. Compromise of any single file in this
project never reveals a key.

Usage (programmatic):
    from agent.contract_client import RebalanceClient, RebalanceArgs
    client = RebalanceClient.from_deployments("local")  # or "arc-testnet"
    receipt = client.send_rebalance(RebalanceArgs(
        total_usdc=10_000_000,
        park_amount=0,
        destination_domain=3,         # Arbitrum (CCTP V2 domain ID)
        mint_recipient_evm="0xf39...",
        max_fee=1000,
        min_finality_threshold=0,
        new_nav_usdc=10_000_000,
        allocation_cid=b"\\x00" * 32, # 32-byte commitment to off-chain allocation doc
        whale_count=8,
    ))
    print(receipt.plain_english())

Usage (CLI):
    python -m agent.contract_client --network local --total 10 --domain 3 \
        --recipient 0xf39Fd6e51aad88F6F4ce6aB8827279cfFFb92266
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import Web3
from web3.logs import DISCARD

REPO_ROOT = Path(__file__).parent.parent
DEPLOYMENTS_DIR = REPO_ROOT / "deployments"
FORGE_OUT_DIR = REPO_ROOT / "contracts" / "out"

# CCTP V2 domain IDs (verified 2026-05-17 from Circle docs)
DOMAIN_NAMES = {
    0: "Ethereum",
    1: "Avalanche",
    2: "OP",
    3: "Arbitrum",
    5: "Solana",
    6: "Base",
    7: "Polygon PoS",
    10: "Unichain",
}


def _load_abi(contract_name: str) -> list[dict[str, Any]]:
    """Load ABI from forge build output. Raises FileNotFoundError if not built."""
    path = FORGE_OUT_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"ABI not found at {path}. Run `forge build` in contracts/."
        )
    return json.loads(path.read_text())["abi"]


def _load_deployment(network: str) -> dict[str, Any]:
    path = DEPLOYMENTS_DIR / f"{network}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Deployment file missing: {path}. "
            f"Run forge script Deploy.s.sol against {network} first."
        )
    return json.loads(path.read_text())


def _evm_to_bytes32(address: str) -> bytes:
    """Pad a 20-byte EVM address to 32 bytes (CCTP V2 mintRecipient format)."""
    return bytes(12) + bytes.fromhex(address.removeprefix("0x"))


@dataclass
class RebalanceArgs:
    total_usdc: int               # base units (6 decimals)
    park_amount: int              # base units; 0 to skip USYC parking
    destination_domain: int       # CCTP V2 domain ID
    mint_recipient_evm: str       # EVM address (will be padded to bytes32)
    max_fee: int                  # CCTP V2 max fee
    min_finality_threshold: int   # CCTP V2 min finality
    new_nav_usdc: int             # NAV reading the agent computed
    allocation_cid: bytes         # 32-byte commitment to the allocation doc (IPFS CID truncated or keccak256)
    whale_count: int              # number of whales the allocation document covers
    reported_at: int | None = None  # unix seconds; defaults to now


@dataclass
class RebalanceReceipt:
    tx_hash: str
    block_number: int
    gas_used: int
    latency_seconds: float
    nav_before_usdc: int
    nav_after_usdc: int
    destination_domain: int
    usdc_routed: int
    cctp_nonce: int | None

    def plain_english(self) -> str:
        venue = DOMAIN_NAMES.get(self.destination_domain, f"domain #{self.destination_domain}")
        before = self.nav_before_usdc / 1e6
        after = self.nav_after_usdc / 1e6
        routed = self.usdc_routed / 1e6
        return (
            f"Rebalance settled in {self.latency_seconds:.2f}s. "
            f"Moved ${routed:,.2f} USDC to {venue}. "
            f"Index NAV: ${before:,.2f} -> ${after:,.2f}. "
            f"Gas used: {self.gas_used:,}."
        )


class RebalanceClient:
    """Thin signing client around RebalanceExecutor. Reads key from env at call time."""

    def __init__(
        self,
        w3: Web3,
        deployment: dict[str, Any],
        operator_key_env_var: str = "OPERATOR_PRIVATE_KEY",
    ):
        self.w3 = w3
        self.deployment = deployment
        self.key_env = operator_key_env_var

        addrs = deployment["addresses"]
        self.executor = w3.eth.contract(
            address=Web3.to_checksum_address(addrs["RebalanceExecutor"]),
            abi=_load_abi("RebalanceExecutor"),
        )
        self.nav_oracle = w3.eth.contract(
            address=Web3.to_checksum_address(addrs["NAVOracle"]),
            abi=_load_abi("NAVOracle"),
        )
        self.router = w3.eth.contract(
            address=Web3.to_checksum_address(addrs["CCTPRouter"]),
            abi=_load_abi("CCTPRouter"),
        )

    @classmethod
    def from_deployments(cls, network: str) -> RebalanceClient:
        deployment = _load_deployment(network)
        rpc = deployment["_meta"]["rpc"]
        w3 = Web3(Web3.HTTPProvider(rpc))
        if not w3.is_connected():
            raise ConnectionError(f"RPC unreachable: {rpc}")
        return cls(w3, deployment)

    def _operator_account(self) -> Any:
        key = os.getenv(self.key_env)
        if not key:
            raise EnvironmentError(
                f"{self.key_env} not set in environment. "
                f"Export it before calling send_rebalance; never paste it inline."
            )
        return Account.from_key(key)

    def current_nav(self) -> int:
        return int(self.nav_oracle.functions.nav().call())

    def send_rebalance(self, args: RebalanceArgs) -> RebalanceReceipt:
        operator = self._operator_account()
        reported_at = args.reported_at if args.reported_at is not None else int(time.time())
        mint_recipient = _evm_to_bytes32(args.mint_recipient_evm)
        nav_before = self.current_nav()

        nonce = self.w3.eth.get_transaction_count(operator.address)
        chain_id = self.w3.eth.chain_id

        if len(args.allocation_cid) != 32:
            raise ValueError(f"allocation_cid must be 32 bytes, got {len(args.allocation_cid)}")
        tx = self.executor.functions.rebalance(
            args.total_usdc,
            args.park_amount,
            args.destination_domain,
            mint_recipient,
            args.max_fee,
            args.min_finality_threshold,
            args.new_nav_usdc,
            reported_at,
            args.allocation_cid,
            args.whale_count,
        ).build_transaction({
            "from": operator.address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 800_000,
        })

        signed = operator.sign_transaction(tx)
        t0 = time.time()
        # web3.py v6 = signed.rawTransaction; v7 = signed.raw_transaction
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = self.w3.eth.send_raw_transaction(raw)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        latency = time.time() - t0

        if receipt["status"] != 1:
            raise RuntimeError(f"Rebalance reverted in tx {tx_hash.hex()}")

        nav_after, routed, cctp_nonce = self._decode_outcome(receipt)
        return RebalanceReceipt(
            tx_hash=tx_hash.hex(),
            block_number=receipt["blockNumber"],
            gas_used=receipt["gasUsed"],
            latency_seconds=latency,
            nav_before_usdc=nav_before,
            nav_after_usdc=nav_after,
            destination_domain=args.destination_domain,
            usdc_routed=routed,
            cctp_nonce=cctp_nonce,
        )

    def _decode_outcome(self, receipt: Any) -> tuple[int, int, int | None]:
        nav_after = 0
        routed = 0
        cctp_nonce: int | None = None
        # errors=DISCARD silently drops logs that don't match this event's ABI
        # (process_receipt iterates ALL logs, so non-matches are expected noise).
        for ev in self.nav_oracle.events.NAVUpdated().process_receipt(receipt, errors=DISCARD):
            nav_after = ev["args"]["nav"]
        for ev in self.router.events.Routed().process_receipt(receipt, errors=DISCARD):
            routed = ev["args"]["amount"]
            cctp_nonce = ev["args"]["nonce"]
        return nav_after, routed, cctp_nonce


def _main() -> None:
    parser = argparse.ArgumentParser(description="Send a rebalance to RebalanceExecutor")
    parser.add_argument("--network", default="local", help="Deployment name (local | arc-testnet)")
    parser.add_argument("--total", type=float, required=True, help="USDC amount to rebalance (decimal, e.g. 10)")
    parser.add_argument("--park", type=float, default=0.0, help="USDC to park in USYC (decimal)")
    parser.add_argument("--domain", type=int, required=True, help="CCTP V2 destination domain (e.g. 3 = Arbitrum)")
    parser.add_argument("--recipient", required=True, help="EVM mint recipient (will be padded to bytes32)")
    parser.add_argument("--max-fee", type=int, default=1000)
    parser.add_argument("--min-finality", type=int, default=0)
    parser.add_argument("--new-nav", type=float, help="New NAV in USDC (decimal). Defaults to --total.")
    parser.add_argument("--cid-hex", help="32-byte allocation CID as hex (with or without 0x). Default = keccak256(timestamp).")
    parser.add_argument("--whales", type=int, default=0, help="Whale count covered by the allocation doc.")
    args = parser.parse_args()

    client = RebalanceClient.from_deployments(args.network)
    new_nav_dec = args.new_nav if args.new_nav is not None else args.total

    if args.cid_hex:
        cid = bytes.fromhex(args.cid_hex.removeprefix("0x"))
    else:
        # Synthetic CID so the CLI is usable without IPFS pinning wired up.
        import hashlib
        cid = hashlib.sha256(str(int(time.time())).encode()).digest()

    receipt = client.send_rebalance(RebalanceArgs(
        total_usdc=int(args.total * 1e6),
        park_amount=int(args.park * 1e6),
        destination_domain=args.domain,
        mint_recipient_evm=args.recipient,
        max_fee=args.max_fee,
        min_finality_threshold=args.min_finality,
        new_nav_usdc=int(new_nav_dec * 1e6),
        allocation_cid=cid,
        whale_count=args.whales,
    ))
    print(receipt.plain_english())
    print(f"  tx: {receipt.tx_hash}")
    print(f"  block: {receipt.block_number}")
    if receipt.cctp_nonce is not None:
        print(f"  CCTP V2 nonce: {receipt.cctp_nonce}")


if __name__ == "__main__":
    _main()
