#!/usr/bin/env zsh
# One-shot fix: update WhaleAttestation.slashBeneficiary from the legacy V2
# IndexToken to the live V3 IndexToken. Only the attestation owner can do
# this (operator EOA in our deploy). ~0.001 USDC gas.
set -euo pipefail

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
export PATH="$HOME/.foundry/bin:$PATH"

ATT=0x1d2d34D941b13CbF233051074F007ecf68fB0F7f
NEW_BEN=0xAdEa3FaE6011c2D275868d1c1933B37BE7648269

echo "--- current slashBeneficiary ---"
cast call "$ATT" "slashBeneficiary()(address)" --rpc-url "$ARC_RPC_URL"
echo
echo "--- setSlashBeneficiary($NEW_BEN) ---"
cast send "$ATT" "setSlashBeneficiary(address)" "$NEW_BEN" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash" | head -3
echo
echo "--- new slashBeneficiary ---"
cast call "$ATT" "slashBeneficiary()(address)" --rpc-url "$ARC_RPC_URL"
