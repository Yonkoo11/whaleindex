#!/usr/bin/env zsh
# Verify all V2 contracts on Arcscan via Blockscout-style API.
# All addresses + constructor args derived from deployments/arc-testnet.json.

set -euo pipefail

# Add Foundry bin to PATH so forge + cast resolve without sourcing user profile.
export PATH="$HOME/.foundry/bin:$PATH"

cd "${0:A:h}/.."/contracts

CHAIN=5042002
URL="https://testnet.arcscan.app/api/"
VERIFIER=(--chain-id "$CHAIN" --verifier blockscout --verifier-url "$URL")

# V2 deployed addresses (from deployments/arc-testnet.json):
NAV=0xcbA2b630051527Cbebdc9212611a059c080B9e1c
ROUTER=0xC74Efa01142F7BA9e6B96C5c0841DcA0aB744E34
PARK=0xE8682ca1cE90A6be3BD91A01Bf3e39c19543521A
INDEX=0x68a8809E118E6C778D199e0Dc7586AC88589b708
EXEC=0x2096B1FCad5d3d4303f1Ac3DABA4116c73B0D282
MOCK_USYC=0x86df318Ff4356682Da819516bd05B9873f3b8F07
MOCK_MSG=0x60612Ad24e730aBF256cCFDd77dd0F431B20a079

# External addresses referenced as constructor args:
USDC=0x3600000000000000000000000000000000000000
DEPLOYER=0xf9946775891a24462cD4ec885d0D4E2675C84355

verify() {
  local name="$1"; shift
  local addr="$1"; shift
  local path="$1"; shift
  local args="${1:-}"
  echo
  echo "=== verifying $name @ $addr ==="
  if [[ -n "$args" ]]; then
    "$HOME/.foundry/bin/forge" verify-contract "${VERIFIER[@]}" "$addr" "$path" --constructor-args "$args" 2>&1 | /usr/bin/tail -5
  else
    "$HOME/.foundry/bin/forge" verify-contract "${VERIFIER[@]}" "$addr" "$path" 2>&1 | /usr/bin/tail -5
  fi
}

# MockTokenMessengerV2 — no constructor args
verify "MockTokenMessengerV2" "$MOCK_MSG" "src/mocks/MockTokenMessengerV2.sol:MockTokenMessengerV2"

# MockUSYC(address underlying_) — underlying = real USDC
verify "MockUSYC" "$MOCK_USYC" "src/mocks/MockUSYC.sol:MockUSYC" \
  "$("$HOME/.foundry/bin/cast" abi-encode 'constructor(address)' "$USDC")"

# CCTPRouter(address usdc_, address tokenMessenger_, uint32[] initialDomains) — domains [3,5]
verify "CCTPRouter" "$ROUTER" "src/CCTPRouter.sol:CCTPRouter" \
  "$("$HOME/.foundry/bin/cast" abi-encode 'constructor(address,address,uint32[])' "$USDC" "$MOCK_MSG" '[3,5]')"

# USYCParkVault(address usdc_, address usyc_, address executor) — executor was deployer initially
verify "USYCParkVault" "$PARK" "src/USYCParkVault.sol:USYCParkVault" \
  "$("$HOME/.foundry/bin/cast" abi-encode 'constructor(address,address,address)' "$USDC" "$MOCK_USYC" "$DEPLOYER")"

# IndexToken(address usdc_, address navOracle_, address owner_) — owner was deployer initially
verify "IndexToken" "$INDEX" "src/IndexToken.sol:IndexToken" \
  "$("$HOME/.foundry/bin/cast" abi-encode 'constructor(address,address,address)' "$USDC" "$NAV" "$DEPLOYER")"

# RebalanceExecutor(usdc, index, nav, router, park, operator, maxSingleMove=500e6, dailyCap=10000e6)
verify "RebalanceExecutor" "$EXEC" "src/RebalanceExecutor.sol:RebalanceExecutor" \
  "$("$HOME/.foundry/bin/cast" abi-encode 'constructor(address,address,address,address,address,address,uint256,uint256)' \
    "$USDC" "$INDEX" "$NAV" "$ROUTER" "$PARK" "$DEPLOYER" 500000000 10000000000)"
