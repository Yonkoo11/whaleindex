#!/usr/bin/env zsh
# Direct-transfer USDC to the V2 IndexToken treasury. Skips the buy() flow
# which requires a fresh NAV oracle reading. Useful for seeding before an
# off-chain CCTP rebalance test.
set -euo pipefail

AMOUNT="${1:-500000}"  # default 0.5 USDC base units
INDEX=0xAdEa3FaE6011c2D275868d1c1933B37BE7648269  # V3 IndexToken
USDC=0x3600000000000000000000000000000000000000

source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi
: "${ARC_RPC_URL:=${RPC:-}}"
if [[ -z "${ARC_RPC_URL:-}" ]] && command -v arc-canteen >/dev/null 2>&1; then
  ARC_RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)
fi

cast send "$USDC" "transfer(address,uint256)" "$INDEX" "$AMOUNT" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" \
  | grep -E "status|gasUsed|transactionHash" | head -3
