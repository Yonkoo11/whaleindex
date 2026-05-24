#!/usr/bin/env zsh
# Seed IndexToken with 0.5 USDC of shares, then trigger an off-chain CCTP
# rebalance (3-tx flow) via the orchestrator. Spends ~0.32 USDC total.

set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
: "${OPERATOR_PRIVATE_KEY:=${DEPLOYER_PRIVATE_KEY:-}}"
: "${ARC_RPC_URL:=${RPC:-${ARC_TESTNET_RPC:-}}}"
export DEPLOYER_PRIVATE_KEY OPERATOR_PRIVATE_KEY ARC_RPC_URL

USDC=0x3600000000000000000000000000000000000000
INDEX=0x68a8809E118E6C778D199e0Dc7586AC88589b708

echo "--- Step 1: operator approves IndexToken for 0.5 USDC ---"
cast send "$USDC" "approve(address,uint256)" "$INDEX" 500000 \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed" | head -2

echo
echo "--- Step 2: operator buy(0.5 USDC) ---"
cast send "$INDEX" "buy(uint256)" 500000 \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash" | head -3

echo
echo "--- Step 3: IndexToken treasury after seed ---"
cast call "$USDC" "balanceOf(address)(uint256)" "$INDEX" --rpc-url "$ARC_RPC_URL"

echo
echo "--- Step 4: run orchestrator with --cctp-mode off-chain ---"
cd "${0:A:h}/.."
python3 -m agent.orchestrator \
  --network arc-testnet \
  --demo-allocation \
  --aum-usdc 0.3 \
  --new-nav-usdc 2000000 \
  --cctp-mode off-chain
