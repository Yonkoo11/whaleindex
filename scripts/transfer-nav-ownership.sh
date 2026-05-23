#!/usr/bin/env zsh
# One-shot: transfer NAVOracle ownership to RebalanceExecutor.
#
# Needed because Deploy.s.sol intentionally leaves NAVOracle owned by `operator`
# to support the two-key (deployer != operator) case. In the single-key case
# (operator == deployer), this transfer must happen before rebalance() works.
#
# Idempotent: skips if owner is already the executor.
set -euo pipefail

NAV=0xEde6Db2855BACF191E5B2E2d91B6276bB56bf183
EXEC=0x9A6d36A0487EA52df43E7704a97F47844C4Eac4E

# Load env into THIS subshell only.
# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
: "${ARC_RPC_URL:=${RPC:-}}"

if [[ -z "${DEPLOYER_PRIVATE_KEY:-}" ]]; then
  echo "MISSING: DEPLOYER_PRIVATE_KEY" >&2; exit 2
fi
if [[ -z "${ARC_RPC_URL:-}" ]]; then
  # arc-canteen sometimes prints status lines to stdout — grep the URL only.
  ARC_RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)
fi
if [[ -z "$ARC_RPC_URL" ]]; then
  echo "MISSING: ARC_RPC_URL / RPC" >&2; exit 2
fi
export DEPLOYER_PRIVATE_KEY ARC_RPC_URL

current_owner=$(cast call "$NAV" "owner()(address)" --rpc-url "$ARC_RPC_URL")
echo "current NAVOracle.owner: $current_owner"
if [[ "${current_owner:l}" == "${EXEC:l}" ]]; then
  echo "already correct — no tx needed."
  exit 0
fi

echo "transferring ownership to RebalanceExecutor..."
cast send "$NAV" "transferOwnership(address)" "$EXEC" \
  --rpc-url "$ARC_RPC_URL" \
  --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "transactionHash|status|gasUsed|blockNumber" | head -8

echo
echo "verifying new owner..."
cast call "$NAV" "owner()(address)" --rpc-url "$ARC_RPC_URL"
