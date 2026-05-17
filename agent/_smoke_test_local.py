"""
LOCAL ANVIL SMOKE TEST — NEVER RUN OUTSIDE ANVIL.

End-to-end proof of the agent -> contract loop:
  1. Connect to local anvil (chain id 31337). Refuse anything else.
  2. Seed the protocol: mint MockUSDC to operator, approve, buy 100 USDC of shares.
  3. Call RebalanceExecutor.rebalance(...) via the agent's signing client.
  4. Decode events into a plain-English receipt.

Uses Foundry anvil's well-known account 0 dev key. This key has no funds on
any real network; it ships as a public dev fixture in Anvil documentation.
Reference: https://book.getfoundry.sh/anvil/

This file is the ONLY place where a key-shaped string appears in the repo,
and it is gated by a chain-id check: the test refuses to run unless connected
to chain id 31337 (anvil default). Real-network keys MUST come from process
env and are never written anywhere.

Idempotent: safe to re-run against the same anvil instance.
"""

from __future__ import annotations

import os
import sys

from eth_account import Account
from web3 import Web3

from .contract_client import RebalanceArgs, RebalanceClient, _load_abi

# Foundry anvil account 0. Well-known public dev fixture. Not a real secret.
_ANVIL_TEST_KEY_PUBLIC_DEV_FIXTURE = (
    "0x" + "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)
_ANVIL_CHAIN_ID = 31337


def _seed_treasury(client: RebalanceClient, key: str, amount_usdc_dec: int = 100) -> None:
    """Mint mock USDC, approve IndexToken, buy shares to load the protocol treasury."""
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
    if treasury_balance >= amount_usdc_dec * 1_000_000:
        print(f"  treasury already has {treasury_balance / 1e6:.2f} USDC; skipping seed")
        return

    base = amount_usdc_dec * 1_000_000
    mint_amount = base * 10           # mint 10x the buy so retries are cheap

    nonce = client.w3.eth.get_transaction_count(acct.address)

    def _send(fn, n: int) -> None:
        tx = fn.build_transaction({
            "from": acct.address,
            "nonce": n,
            "chainId": client.w3.eth.chain_id,
            "gas": 300_000,
        })
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = client.w3.eth.send_raw_transaction(raw)
        rcpt = client.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        if rcpt["status"] != 1:
            raise RuntimeError(f"seed step reverted: {tx_hash.hex()}")

    _send(usdc.functions.mint(acct.address, mint_amount), nonce)
    _send(usdc.functions.approve(addrs["IndexToken"], mint_amount), nonce + 1)
    _send(index.functions.buy(base), nonce + 2)
    print(f"  seeded: minted {mint_amount/1e6:.0f} USDC, bought {base/1e6:.0f} USDC of shares")


def main() -> int:
    client = RebalanceClient.from_deployments("local")
    if client.w3.eth.chain_id != _ANVIL_CHAIN_ID:
        sys.stderr.write(
            f"REFUSING: connected chain id {client.w3.eth.chain_id} != anvil 31337. "
            f"This smoke test is for local anvil only.\n"
        )
        return 2

    os.environ["OPERATOR_PRIVATE_KEY"] = _ANVIL_TEST_KEY_PUBLIC_DEV_FIXTURE

    print("Seeding local protocol treasury (idempotent)...")
    _seed_treasury(client, _ANVIL_TEST_KEY_PUBLIC_DEV_FIXTURE, amount_usdc_dec=100)

    nav_before = client.current_nav()
    receipt = client.send_rebalance(RebalanceArgs(
        total_usdc=5_000_000,         # 5 USDC
        park_amount=0,
        destination_domain=3,         # Arbitrum
        mint_recipient_evm="0xf39Fd6e51aad88F6F4ce6aB8827279cfFFb92266",
        max_fee=1000,
        min_finality_threshold=0,
        new_nav_usdc=15_000_000,      # 15 USDC NAV (post-move)
    ))

    print()
    print(receipt.plain_english())
    print(f"  tx: {receipt.tx_hash}")
    print(f"  block: {receipt.block_number}")
    print(f"  CCTP V2 nonce: {receipt.cctp_nonce}")
    print(f"  nav_before (oracle pre-call): {nav_before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
