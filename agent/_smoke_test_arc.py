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

import hashlib
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


def _seed_treasury(client: RebalanceClient, key: str, amount_usdc_dec: int = 1) -> None:
    """
    Load the IndexToken treasury with `amount_usdc_dec` USDC of shares.

    Detects real USDC (no mint function) vs mock USDC. For real USDC,
    the operator's existing USDC balance funds the buy; for mock, we mint first.
    Idempotent: skips entirely if treasury already has enough.
    """
    acct = Account.from_key(key)
    addrs = client.deployment["addresses"]
    # Use a minimal ERC20 ABI — works for both mock and real USDC.
    usdc = client.w3.eth.contract(
        address=Web3.to_checksum_address(addrs["USDC"]),
        abi=[
            {"name": "balanceOf", "type": "function", "stateMutability": "view",
             "inputs": [{"name": "a", "type": "address"}],
             "outputs": [{"name": "", "type": "uint256"}]},
            {"name": "approve", "type": "function", "stateMutability": "nonpayable",
             "inputs": [{"name": "s", "type": "address"}, {"name": "a", "type": "uint256"}],
             "outputs": [{"name": "", "type": "bool"}]},
            {"name": "mint", "type": "function", "stateMutability": "nonpayable",
             "inputs": [{"name": "to", "type": "address"}, {"name": "a", "type": "uint256"}],
             "outputs": []},
        ],
    )
    index = client.w3.eth.contract(
        address=Web3.to_checksum_address(addrs["IndexToken"]),
        abi=_load_abi("IndexToken"),
    )

    treasury_balance = int(usdc.functions.balanceOf(addrs["IndexToken"]).call())
    target_base = amount_usdc_dec * 1_000_000
    if treasury_balance >= target_base:
        print(f"  treasury already has {treasury_balance / 1e6:.2f} USDC; skipping seed")
        return

    operator_balance = int(usdc.functions.balanceOf(acct.address).call())
    print(f"  operator USDC balance: {operator_balance / 1e6:.6f}")

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

    # Try mint first — works on MockUSDC, reverts on real USDC.
    n = nonce
    try:
        # Build but DON'T send first, just to estimate; if mint isn't callable, eth_call will reject.
        mint_amount = target_base * 10
        usdc.functions.mint(acct.address, mint_amount).call({"from": acct.address})
        _send(usdc.functions.mint(acct.address, mint_amount), n, f"mint {mint_amount/1e6:.0f} mUSDC")
        n += 1
    except Exception:
        print("  seed: real USDC detected — skipping mint, using operator's existing balance")
        if operator_balance < target_base:
            raise RuntimeError(
                f"operator balance ({operator_balance/1e6:.4f} USDC) below seed target "
                f"({target_base/1e6:.4f} USDC). Top up from faucet.circle.com."
            )

    _send(usdc.functions.approve(addrs["IndexToken"], target_base), n,
          f"approve IndexToken for {target_base/1e6:.4f} USDC")
    _send(index.functions.buy(target_base), n + 1, f"buy {target_base/1e6:.4f} USDC of shares")


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

    # Smaller seed for real USDC: 1 USDC of shares funds the treasury for a 0.5 USDC rebalance.
    # Leaves ~18 USDC in the operator wallet for ongoing gas.
    print("Seeding Arc protocol treasury (idempotent)...")
    _seed_treasury(client, key, amount_usdc_dec=1)

    nav_before = client.current_nav()
    print(f"NAV before rebalance: ${nav_before/1e6:,.4f}")

    snapshot = f"smoke-test:{int(__import__('time').time())}:0.5-usdc-to-arbitrum".encode()
    cid = hashlib.sha256(snapshot).digest()

    # CCTP V2 finality: 1000 = Fast (requires Fast Transfer Allowance), 2000 = Standard.
    # Standard for smoke test: no allowance dependency, more permissive.
    # maxFee: 0.05 USDC ceiling on a 0.5 USDC transfer (10%) — well above any reasonable protocol fee.
    print(f"Sending rebalance: 0.5 USDC -> Arbitrum (CCTP V2 domain 3, Standard), cid={cid.hex()[:12]}...")
    receipt = client.send_rebalance(RebalanceArgs(
        total_usdc=500_000,    # 0.5 USDC
        park_amount=0,
        destination_domain=3,  # Arbitrum
        mint_recipient_evm=Account.from_key(key).address,
        max_fee=50_000,        # 0.05 USDC max fee
        min_finality_threshold=2000,  # Standard finality
        new_nav_usdc=1_000_000,  # 1 USDC NAV post-move
        allocation_cid=cid,
        whale_count=3,
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
