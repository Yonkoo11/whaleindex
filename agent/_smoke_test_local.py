"""
LOCAL ANVIL SMOKE TEST — NEVER RUN OUTSIDE ANVIL.

Uses Foundry anvil's well-known account 0 dev key. This key has no funds on
any real network; it ships as a public dev fixture in Anvil documentation.
Reference: https://book.getfoundry.sh/anvil/

This file is the ONLY place where a key-shaped string appears in the repo,
and it is gated by a chain-id check: the test refuses to run unless connected
to chain id 31337 (anvil default). Real-network keys MUST come from process
env and are never written anywhere.
"""

from __future__ import annotations

import os
import sys

from .contract_client import RebalanceArgs, RebalanceClient

# Foundry anvil account 0. Well-known public dev fixture. Not a real secret.
_ANVIL_TEST_KEY_PUBLIC_DEV_FIXTURE = (
    "0x" + "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)
_ANVIL_CHAIN_ID = 31337


def main() -> int:
    client = RebalanceClient.from_deployments("local")
    if client.w3.eth.chain_id != _ANVIL_CHAIN_ID:
        sys.stderr.write(
            f"REFUSING: connected chain id {client.w3.eth.chain_id} != anvil 31337. "
            f"This smoke test is for local anvil only.\n"
        )
        return 2

    os.environ["OPERATOR_PRIVATE_KEY"] = _ANVIL_TEST_KEY_PUBLIC_DEV_FIXTURE

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

    print(receipt.plain_english())
    print(f"  tx: {receipt.tx_hash}")
    print(f"  block: {receipt.block_number}")
    print(f"  CCTP V2 nonce: {receipt.cctp_nonce}")
    print(f"  nav_before (oracle pre-call): {nav_before}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
