"""
ARC TESTNET SMOKE TEST — End-to-end Phase 1 proof against live Arc.

Pipeline:
  1. Build Web3 from $ARC_RPC_URL or $RPC (arc-canteen CLI env name).
  2. Refuse anything other than Arc testnet (chain id 5042002).
  3. Read $OPERATOR_PRIVATE_KEY (falls back to $DEPLOYER_PRIVATE_KEY for the
     single-key deploy). Key is read from process env and never echoed.
  4. Seed MockUSDC: mint to operator, approve IndexToken, buy 100 USDC of shares.
     Idempotent — skips seeding if treasury already funded.
  5. Send a small rebalance via RebalanceExecutor: 5 USDC to Arbitrum (domain 3),
     NAV 0 -> 15. Decode events into a plain-English receipt.

Security:
  - This file references no key values. Only env var NAMES.
  - The RPC URL is loaded at runtime; the deployment file stores a placeholder.
  - If the key isn't in process env, the script exits cleanly with the env name.

Idempotent: safe to re-run; treasury seeding skips if balance already adequate.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from eth_account import Account
from web3 import Web3

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.contract_client import (
    RebalanceArgs,
    RebalanceClient,
    _load_abi,
    _load_deployment,
)

ARC_CHAIN_ID = 5042002
NETWORK = "arc-testnet"
OPERATOR_ENV = "OPERATOR_PRIVATE_KEY"
OPERATOR_FALLBACK_ENV = "DEPLOYER_PRIVATE_KEY"
RPC_ENV_CANDIDATES = ("ARC_RPC_URL", "RPC")


def _resolve_rpc_url() -> str:
    for name in RPC_ENV_CANDIDATES:
        val = os.getenv(name)
        if val:
            return val
    sys.stderr.write(
        f"MISSING RPC: set one of {' / '.join(RPC_ENV_CANDIDATES)} in env. "
        f"Tip: `source ~/.arc-canteen/env` or run via scripts/smoke-arc.sh\n"
    )
    sys.exit(2)


def _resolve_operator_key() -> str:
    key = os.getenv(OPERATOR_ENV)
    if key:
        return key
    fallback = os.getenv(OPERATOR_FALLBACK_ENV)
    if fallback:
        os.environ[OPERATOR_ENV] = fallback
        return fallback
    sys.stderr.write(
        f"MISSING KEY: set ${OPERATOR_ENV} (or ${OPERATOR_FALLBACK_ENV}) in env. "
        f"Never paste it inline. Run via scripts/smoke-arc.sh which sources ~/.zshenv.\n"
    )
    sys.exit(2)


def _seed_treasury(client: RebalanceClient, key: str, amount_usdc_dec: int = 100) -> None:
    acct = Account.from_key(key)
    addrs = client.deployment["addresses"]
    usdc = client.w3.eth.contract(
        address=Web3.to_checksum_address(addrs["USDC"]),
        abi=_load_abi("MockUSDC"),
    )
    index = client.w3.eth.contract(
        address=Web3.to_checksum_address(addrs["IndexToken"]),
        abi=_load_abi("IndexToken"),
    )

    treasury_balance = int(usdc.functions.balanceOf(addrs["IndexToken"]).call())
    target_base = amount_usdc_dec * 1_000_000
    if treasury_balance >= target_base:
        print(f"  treasury already has {treasury_balance / 1e6:.2f} mock USDC; skipping seed")
        return

    mint_amount = target_base * 10  # 10x headroom for retries
    nonce = client.w3.eth.get_transaction_count(acct.address)

    def _send(fn, n: int, label: str) -> None:
        tx = fn.build_transaction({
            "from": acct.address,
            "nonce": n,
            "chainId": client.w3.eth.chain_id,
            "gas": 400_000,
        })
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = client.w3.eth.send_raw_transaction(raw)
        rcpt = client.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if rcpt["status"] != 1:
            raise RuntimeError(f"seed step '{label}' reverted: {tx_hash.hex()}")
        print(f"  seed: {label} ok (block {rcpt['blockNumber']}, gas {rcpt['gasUsed']:,})")

    _send(usdc.functions.mint(acct.address, mint_amount), nonce, f"mint {mint_amount/1e6:.0f} mUSDC")
    _send(usdc.functions.approve(addrs["IndexToken"], mint_amount), nonce + 1, "approve IndexToken")
    _send(index.functions.buy(target_base), nonce + 2, f"buy {target_base/1e6:.0f} mUSDC of shares")


def main() -> int:
    rpc_url = _resolve_rpc_url()
    key = _resolve_operator_key()

    deployment = _load_deployment(NETWORK)
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        sys.stderr.write("RPC connect failed.\n")
        return 2

    cid = w3.eth.chain_id
    if cid != ARC_CHAIN_ID:
        sys.stderr.write(
            f"REFUSING: connected chain id {cid} != Arc testnet {ARC_CHAIN_ID}.\n"
        )
        return 2

    client = RebalanceClient(w3, deployment)

    print("Seeding Arc protocol treasury (idempotent)...")
    _seed_treasury(client, key, amount_usdc_dec=100)

    nav_before = client.current_nav()
    print(f"NAV before rebalance: ${nav_before/1e6:,.2f}")

    print("Sending rebalance: 5 USDC -> Arbitrum (CCTP V2 domain 3)...")
    receipt = client.send_rebalance(RebalanceArgs(
        total_usdc=5_000_000,
        park_amount=0,
        destination_domain=3,
        mint_recipient_evm=Account.from_key(key).address,
        max_fee=1000,
        min_finality_threshold=0,
        new_nav_usdc=15_000_000,
    ))

    print()
    print(receipt.plain_english())
    print(f"  tx:    {receipt.tx_hash}")
    print(f"  block: {receipt.block_number}")
    print(f"  CCTP V2 nonce: {receipt.cctp_nonce}")
    print(f"  nav_before: ${nav_before/1e6:,.2f}")

    if receipt.latency_seconds < 2.0:
        print(f"PHASE 1 GATE: PASS — settlement {receipt.latency_seconds:.2f}s < 2.00s target")
    else:
        print(f"PHASE 1 GATE: latency {receipt.latency_seconds:.2f}s exceeds 2.00s target (NAV update ok)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
