#!/usr/bin/env zsh
# Print the public address derived from DEPLOYER_PRIVATE_KEY.
# Addresses are NOT secrets — they're how you fund the wallet.
# Private key never leaves this subshell.
set -euo pipefail
source "$HOME/.zshenv" >/dev/null 2>&1 || true
: "${DEPLOYER_PRIVATE_KEY:=${FAKTORY_PRIVATE_KEY:-}}"
if [[ -z "${DEPLOYER_PRIVATE_KEY:-}" ]]; then
  echo "MISSING: DEPLOYER_PRIVATE_KEY (or FAKTORY_PRIVATE_KEY)" >&2
  exit 1
fi
addr=$(cast wallet address --private-key "$DEPLOYER_PRIVATE_KEY")
echo "Deployer address: $addr"

# Also show balance on Arc testnet (helps confirm whether funding is needed).
RPC_URL=""
if command -v arc-canteen >/dev/null 2>&1; then
  RPC_URL="$(arc-canteen rpc-url 2>/dev/null || true)"
fi
if [[ -n "$RPC_URL" ]]; then
  bal_wei=$(cast balance "$addr" --rpc-url "$RPC_URL" 2>/dev/null || echo "")
  if [[ -n "$bal_wei" ]]; then
    bal_eth=$(cast to-unit "$bal_wei" ether 2>/dev/null || echo "?")
    echo "Arc testnet balance: $bal_eth (native gas token)"
  fi
fi
