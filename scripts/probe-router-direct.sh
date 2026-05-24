#!/usr/bin/env zsh
# Probe whether our CCTPRouter works directly against real CCTP TokenMessenger.
# Operator approves Router, then calls Router.routeUSDC. Burns 0.1 USDC on success.
#
# Isolates: Router -> real CCTP works?  (vs Executor -> Router which fails)

set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"

RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)

USDC=0x3600000000000000000000000000000000000000
ROUTER=0x5A832cb202aeBa13E50CFc03FF3D4C51462d0541
RECIPIENT_PADDED=0x000000000000000000000000f9946775891a24462cD4ec885d0D4E2675C84355

# Router.owner() — needed to check if routeUSDC is gated.
echo "--- Router.owner ---"
cast call "$ROUTER" "owner()(address)" --rpc-url "$RPC_URL"

echo
echo "--- 1. Operator approves Router for 0.1 USDC ---"
cast send "$USDC" "approve(address,uint256)" "$ROUTER" 100000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "transactionHash|status|gasUsed" | head -3

echo
echo "--- 2. Operator calls Router.routeUSDC(0.1 USDC, domain=3, recipient, maxFee=50000, finality=2000) ---"
cast send "$ROUTER" \
  "routeUSDC(uint256,uint32,bytes32,uint256,uint32)" \
  100000 3 "$RECIPIENT_PADDED" 50000 2000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "transactionHash|status|gasUsed|revert" | head -5
