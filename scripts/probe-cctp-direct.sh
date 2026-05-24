#!/usr/bin/env zsh
# Probe whether real CCTP V2 TokenMessenger accepts our params, bypassing
# the WhaleIndex contracts. Operator approves TokenMessenger then calls
# depositForBurn directly. Burns 0.1 USDC on success.
#
# If this succeeds:    the bug is in our Router/Executor flow.
# If this reverts too: the bug is in our params (recipient format, fee, etc).

set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
if [[ -z "${DEPLOYER_PRIVATE_KEY:-}" ]]; then echo MISSING_KEY >&2; exit 2; fi

RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)
[[ -z "$RPC_URL" ]] && { echo MISSING_RPC >&2; exit 2; }

USDC=0x3600000000000000000000000000000000000000
MSG=0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA
DEPLOYER=0xf9946775891a24462cD4ec885d0D4E2675C84355
RECIPIENT_PADDED=0x000000000000000000000000f9946775891a24462cD4ec885d0D4E2675C84355
DESTCALLER_ZERO=0x0000000000000000000000000000000000000000000000000000000000000000

echo "--- 1. Operator approves TokenMessenger for 0.1 USDC ---"
cast send "$USDC" "approve(address,uint256)" "$MSG" 100000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "transactionHash|status|gasUsed" | head -3

echo
echo "--- 2. Direct depositForBurn: 0.1 USDC -> Arbitrum (domain 3), Standard finality (2000), maxFee=50000 ---"
cast send "$MSG" \
  "depositForBurn(uint256,uint32,bytes32,address,bytes32,uint256,uint32)" \
  100000 3 "$RECIPIENT_PADDED" "$USDC" "$DESTCALLER_ZERO" 50000 2000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | tail -20
