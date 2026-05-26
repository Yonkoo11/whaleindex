#!/usr/bin/env zsh
# One real operator buy against the live V4 stack: approve USDC + IndexToken.buy.
# Proves the public buy path end-to-end and gives the dashboard a real holder.
# No rebalance — this does NOT emit any trade/AllocationDecided event.
#
# Key + RPC load inside this subshell only; output is scanned, never the values.
set -euo pipefail

USDC=0x3600000000000000000000000000000000000000
INDEX=0x2415F39a3831aCd403b8353A7850A71a9515Da08
AMOUNT=${1:-1000000}   # default 1.00 USDC (6 decimals)

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi
: "${DEPLOYER_PRIVATE_KEY:=${OPERATOR_PRIVATE_KEY:-${FAKTORY_PRIVATE_KEY:-}}}"
: "${ARC_RPC_URL:=${RPC:-}}"
if [[ -z "${ARC_RPC_URL:-}" ]] && command -v arc-canteen >/dev/null 2>&1; then
  ARC_RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)
fi
[[ -z "${DEPLOYER_PRIVATE_KEY:-}" ]] && { echo "MISSING: DEPLOYER_PRIVATE_KEY" >&2; exit 2; }
[[ -z "${ARC_RPC_URL:-}" ]] && { echo "MISSING: ARC_RPC_URL" >&2; exit 2; }
export DEPLOYER_PRIVATE_KEY ARC_RPC_URL

echo "approve IndexToken for $((AMOUNT)) base-units USDC..."
cast send "$USDC" "approve(address,uint256)" "$INDEX" "$AMOUNT" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" \
  | grep -E "transactionHash|status|blockNumber" | head -4

echo "buy $AMOUNT base-units USDC of WHALE shares..."
cast send "$INDEX" "buy(uint256)" "$AMOUNT" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" \
  | grep -E "transactionHash|status|blockNumber" | head -4

echo
echo "new totalSupply (18dp WHALE): $(cast call "$INDEX" 'totalSupply()(uint256)' --rpc-url "$ARC_RPC_URL")"
