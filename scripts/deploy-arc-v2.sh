#!/usr/bin/env zsh
# Arc testnet deploy — V2: real native USDC + real CCTP TokenMessengerV2.
#
# Differences from deploy-arc.sh:
#   - USDC_ADDRESS forced to 0x3600...0000 (real native USDC ERC-20 interface)
#   - TOKEN_MESSENGER forced to 0x8FE6B999...42DAA (real CCTP V2 TokenMessenger)
#   - USYC_ADDRESS unset → falls back to MockUSYC (Teller allowlist pending)
#
# Same key/RPC handling as deploy-arc.sh: values stay in subshell, scan for leaks.

set -euo pipefail

# Real Arc-testnet canonical addresses (verified via probe + arc-canteen context).
export USDC_ADDRESS=0x3600000000000000000000000000000000000000

# TOKEN_MESSENGER deliberately unset — falls back to MockTokenMessengerV2.
#
# Why mock: Arc testnet's real CCTP V2 TokenMessenger (0x8FE6B999...42DAA) silently
# rejects contract callers — verified 2026-05-23 via the CCTPProbe contract at
# 0xe4F6a70ab9eB591d557011c5A71A8bb8E3B913F6. EOA → depositForBurn works (burned
# 0.1 USDC: tx 0x24f2b089...01c2cf95a). Contract → depositForBurn with valid
# balance + allowance silently reverts (no error data). Likely a tx.origin == msg.sender
# check or an undocumented contract allowlist in the messenger. All Arc-context CCTP
# samples use EOAs only, never contracts on Arc as source.
#
# V3 unblockers: contact Circle to verify the gate, request allowlisting for our
# RebalanceExecutor address, or migrate to an off-chain orchestration pattern where
# the operator EOA signs depositForBurn directly after the executor pulls USDC.

# USYC_ADDRESS deliberately unset — Teller allowlist not yet approved.

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
echo "Env presence check (length only, never values):"
check DEPLOYER_PRIVATE_KEY
check ARC_RPC_URL
echo "External addresses:"
printf "  USDC_ADDRESS:    %s\n" "${USDC_ADDRESS:-unset}"
printf "  TOKEN_MESSENGER: %s\n" "${TOKEN_MESSENGER:-unset (will use MockTokenMessengerV2 - Arc contract-side gate)}"
printf "  USYC_ADDRESS:    %s\n" "${USYC_ADDRESS:-unset (will use MockUSYC - Teller allowlist pending)}"
(( fail )) && exit 2

cd "${0:A:h}/.."
cd contracts

echo
echo "Compiling..."
forge build --silent

echo "Broadcasting V2 deploy to Arc testnet..."
tmp=$(mktemp -t deploy-arc-v2.XXXXXX)
trap 'rm -f "$tmp"' EXIT
forge script script/Deploy.s.sol \
  --rpc-url "$ARC_RPC_URL" \
  --broadcast \
  --slow \
  --skip-simulation \
  -vvv \
  2>&1 | tee "$tmp"
forge_status=${pipestatus[1]}

# Same key-surface scan as deploy-arc.sh.
leak=$(grep -Eo '0x[a-fA-F0-9]{64}' "$tmp" \
  | grep -vE '^(0x0+|0x[a-fA-F0-9]+)$' >/dev/null && \
  grep -B1 -E '0x[a-fA-F0-9]{64}' "$tmp" \
  | grep -viE '(transactionHash|tx hash|blockHash|stateRoot|receiptsRoot|parentHash|sha3|topics|root|hash)' \
  | grep -Eo '0x[a-fA-F0-9]{64}' || true)
if [[ -n "$leak" ]]; then
  echo
  echo "ABORT: unidentified 64-hex string in deploy output - rotate DEPLOYER_PRIVATE_KEY."
  exit 3
fi
if (( forge_status != 0 )); then
  echo "Deploy failed (forge exit $forge_status)."; exit "$forge_status"
fi

echo
echo "V2 deploy complete. Update deployments/arc-testnet.json with the new addresses above."
