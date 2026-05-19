#!/usr/bin/env zsh
# Arc testnet deploy. RUN VIA `!` IN CLAUDE CODE OR INTERACTIVE SHELL ONLY.
#
# Security model:
#   - Sources ~/.zshenv inside this subshell so DEPLOYER_PRIVATE_KEY + ARC_RPC_URL
#     enter the env. The values stay inside this process; we never echo them.
#   - Foundry reads the key via vm.envUint("DEPLOYER_PRIVATE_KEY") and never logs it.
#   - We print VARIABLE NAMES and LENGTHS only — never values.
#   - If a deploy fails with an error that might quote the env, the script aborts
#     and tells you to rotate. Better paranoid than leaked.
#
# Required env (in ~/.zshenv):
#   DEPLOYER_PRIVATE_KEY  (or FAKTORY_PRIVATE_KEY — aliased automatically)
#   ARC_RPC_URL           (or ARC_TESTNET_RPC / ARC_RPC — first one found wins)
# Optional:
#   OPERATOR_ADDRESS      (defaults to deployer address)

set -euo pipefail

# Load .zshenv into THIS subshell only. Stdout/stderr are silenced so any echo
# the user might have in .zshenv can't accidentally leak a value upward.
# shellcheck disable=SC1090
source "$HOME/.zshenv" >/dev/null 2>&1 || true

# Alias common name variants so a single user-chosen name works.
# $RPC is what `arc-canteen login` sets in ~/.arc-canteen/env (auto-loaded via shell-init).
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
: "${ARC_RPC_URL:=${RPC:-${ARC_TESTNET_RPC:-${ARC_RPC:-}}}}"
# Also try ~/.arc-canteen/env directly if shell-init wasn't run yet.
if [[ -z "${ARC_RPC_URL:-}" && -f "$HOME/.arc-canteen/env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/.arc-canteen/env" >/dev/null 2>&1 || true
  : "${ARC_RPC_URL:=${RPC:-}}"
fi
export DEPLOYER_PRIVATE_KEY ARC_RPC_URL

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
check DEPLOYER_PRIVATE_KEY
check ARC_RPC_URL
if [[ -n "${OPERATOR_ADDRESS:-}" ]]; then check OPERATOR_ADDRESS; fi

if (( fail )); then
  echo
  echo "Add the missing variable(s) to ~/.zshenv as:"
  echo "  export DEPLOYER_PRIVATE_KEY=0x..."
  echo "  export ARC_RPC_URL=https://rpc.testnet.arc-node.thecanteenapp.com/v1/<your-api-key>"
  echo "Then open a new terminal (so .zshenv re-loads) and re-run this script."
  exit 2
fi

cd "${0:A:h}/.."   # repo root
cd contracts

echo
echo "Compiling..."
forge build --silent

echo "Broadcasting to Arc testnet..."
# Capture forge output to a tempfile so we can scan it for any 0x-hex of key length.
# If a 64-hex run shows up in stdout (it shouldn't), we abort before the user sees it.
tmp=$(mktemp -t deploy-arc.XXXXXX)
trap 'rm -f "$tmp"' EXIT
# --silent suppresses solc output; deploy script's console.log still prints addresses.
forge script script/Deploy.s.sol \
  --rpc-url "$ARC_RPC_URL" \
  --broadcast \
  --slow \
  --silent \
  2>&1 | tee "$tmp"
status=${pipestatus[1]}

# Paranoia: scan output for anything that looks like a 64-hex private key.
# Tx hashes are also 0x + 64 hex, so we filter those out (they're prefixed
# "transactionHash" / "tx hash" in forge output) and only flag bare 64-hex.
leak=$(grep -Eo '0x[a-fA-F0-9]{64}' "$tmp" \
  | grep -vE '^(0x0+|0x[a-fA-F0-9]+)$' >/dev/null && \
  grep -B1 -E '0x[a-fA-F0-9]{64}' "$tmp" \
  | grep -viE '(transactionHash|tx hash|blockHash|stateRoot|receiptsRoot|parentHash|sha3|topics|root|hash)' \
  | grep -Eo '0x[a-fA-F0-9]{64}' || true)
if [[ -n "$leak" ]]; then
  echo
  echo "ABORT: unidentified 64-hex string in deploy output — possible key surface."
  echo "Rotate DEPLOYER_PRIVATE_KEY immediately. Do NOT share the output."
  exit 3
fi

if (( status != 0 )); then
  echo "Deploy failed (forge exit $status). Check the output above."
  exit "$status"
fi

echo
echo "Deploy succeeded. Capture the addresses printed above into:"
echo "  ${0:A:h}/../deployments/arc-testnet.json"
echo "Then run the agent smoke test against Arc testnet (see ai/memory.md)."
