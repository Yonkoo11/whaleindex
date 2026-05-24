#!/usr/bin/env zsh
# Deploy CCTPProbe and try to burn 0.1 USDC from a contract context.
set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"

RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)

USDC=0x3600000000000000000000000000000000000000
MSG=0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA
RECIPIENT_PADDED=0x000000000000000000000000f9946775891a24462cD4ec885d0D4E2675C84355

cd "${0:A:h}/.."/contracts
forge build --silent

echo "--- Deploy CCTPProbe ---"
PROBE_ADDR=$(forge create src/probes/CCTPProbe.sol:CCTPProbe \
  --broadcast \
  --rpc-url "$RPC_URL" \
  --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep "Deployed to:" | awk '{print $3}')

if [[ -z "$PROBE_ADDR" ]]; then
  echo "Probe deploy failed"; exit 2
fi
echo "Probe deployed at: $PROBE_ADDR"

echo
echo "--- Operator approves Probe for 0.1 USDC ---"
cast send "$USDC" "approve(address,uint256)" "$PROBE_ADDR" 100000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed" | head -2

echo
echo "--- Probe.probe(0.1 USDC -> Arbitrum) — pure contract-side burn ---"
cast send "$PROBE_ADDR" \
  "probe(uint256,uint32,bytes32,address,address,uint256,uint32)" \
  100000 3 "$RECIPIENT_PADDED" "$USDC" "$MSG" 50000 2000 \
  --rpc-url "$RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash|revert" | head -5

# If the above worked, also try with forceApprove-style reset-then-set (router pattern).
