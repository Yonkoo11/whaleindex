#!/usr/bin/env zsh
# Run the WhaleIndex orchestrator against Arc testnet.
# Loads OPERATOR_PRIVATE_KEY + ARC_RPC_URL inside this subshell only.

set -euo pipefail

# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi
: "${OPERATOR_PRIVATE_KEY:=${DEPLOYER_PRIVATE_KEY:-${FAKTORY_PRIVATE_KEY:-}}}"
: "${ARC_RPC_URL:=${RPC:-${ARC_TESTNET_RPC:-}}}"
export OPERATOR_PRIVATE_KEY ARC_RPC_URL

fail=0
check() {
  local name="$1"; local val="${(P)name}"
  if [[ -z "$val" ]]; then printf "  MISSING: %s\n" "$name" >&2; fail=1
  else printf "  ok %-22s len=%d\n" "$name" "${#val}"
  fi
}
echo "Env presence check (length only, never values):"
check OPERATOR_PRIVATE_KEY
check ARC_RPC_URL
(( fail )) && exit 2

cd "${0:A:h}/.."
if [[ ! -d contracts/out/RebalanceExecutor.sol ]]; then
  (cd contracts && forge build --silent)
fi

# Pass through any extra CLI flags to the orchestrator
python3 -m agent.orchestrator --network arc-testnet "$@"
