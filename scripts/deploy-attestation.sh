#!/usr/bin/env zsh
# Deploy WhaleAttestation V3 to Arc testnet against the live V2 IndexToken
# (slash beneficiary). Costs ~0.02 USDC in gas.
set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
: "${ARC_RPC_URL:=${RPC:-${ARC_TESTNET_RPC:-${ARC_RPC:-}}}}"
if [[ -z "${ARC_RPC_URL:-}" && -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
  : "${ARC_RPC_URL:=${RPC:-}}"
fi
if [[ -z "${ARC_RPC_URL:-}" ]] && command -v arc-canteen >/dev/null 2>&1; then
  ARC_RPC_URL=$(arc-canteen rpc-url 2>/dev/null | grep -oE 'https://[^[:space:]]+' | head -1)
fi
export DEPLOYER_PRIVATE_KEY ARC_RPC_URL

fail=0
check() {
  local name="$1"; local val="${(P)name}"
  if [[ -z "$val" ]]; then printf "  MISSING: %s\n" "$name" >&2; fail=1
  else printf "  ok %-22s len=%d\n" "$name" "${#val}"
  fi
}
echo "Env presence check:"
check DEPLOYER_PRIVATE_KEY
check ARC_RPC_URL
(( fail )) && exit 2

cd "${0:A:h}/.."/contracts
forge build --silent

tmp=$(mktemp -t deploy-att.XXXXXX)
trap 'rm -f "$tmp"' EXIT
forge script script/DeployWhaleAttestation.s.sol \
  --rpc-url "$ARC_RPC_URL" \
  --broadcast \
  --slow \
  --skip-simulation \
  -vvv \
  2>&1 | tee "$tmp"
status_=${pipestatus[1]}

# Same leak scan as deploy-arc-v2.sh.
leak=$(grep -B1 -E '0x[a-fA-F0-9]{64}' "$tmp" \
  | grep -viE '(transactionHash|tx hash|blockHash|stateRoot|receiptsRoot|parentHash|sha3|topics|root|hash|withdrawalsRoot|requestsHash|parentBeaconBlockRoot|mixHash)' \
  | grep -Eo '0x[a-fA-F0-9]{64}' | head -1 || true)
if [[ -n "$leak" ]]; then
  echo "ABORT: unidentified 64-hex string in output - rotate DEPLOYER_PRIVATE_KEY."
  exit 3
fi
exit "$status_"
