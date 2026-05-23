#!/usr/bin/env zsh
# Run the Arc-testnet smoke test against the live deployment.
#
# Loads env (DEPLOYER_PRIVATE_KEY, RPC) inside this subshell only. Values
# never enter logs — the smoke test echoes only env var NAMES and tx hashes.
#
# Required env:
#   DEPLOYER_PRIVATE_KEY  (or OPERATOR_PRIVATE_KEY — same wallet for this deploy)
#   ARC_RPC_URL           (or RPC — arc-canteen CLI sets RPC in ~/.arc-canteen/env)

set -euo pipefail

# Load env. Stdout/stderr silenced so .zshenv contents can't leak.
# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true
if [[ -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
fi

: "${OPERATOR_PRIVATE_KEY:=${DEPLOYER_PRIVATE_KEY:-${FAKTORY_PRIVATE_KEY:-}}}"
: "${ARC_RPC_URL:=${RPC:-${ARC_TESTNET_RPC:-}}}"
export OPERATOR_PRIVATE_KEY ARC_RPC_URL

# Validate presence by length only.
fail=0
check() {
  local name="$1"
  local val="${(P)name}"
  if [[ -z "$val" ]]; then
    printf "  MISSING: %s\n" "$name" >&2
    fail=1
  else
    printf "  ok %-22s len=%d\n" "$name" "${#val}"
  fi
}
echo "Env presence check (length only, never values):"
check OPERATOR_PRIVATE_KEY
check ARC_RPC_URL
if (( fail )); then exit 2; fi

cd "${0:A:h}/.."   # repo root

# Make sure ABIs are present (smoke test loads them from contracts/out).
if [[ ! -d contracts/out/RebalanceExecutor.sol ]]; then
  echo "ABIs missing; running forge build..."
  (cd contracts && forge build --silent)
fi

# Activate venv if present so eth_account / web3 are importable.
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python3 -m agent._smoke_test_arc
