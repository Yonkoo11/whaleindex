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

# V3 deployed addresses (from deployments/arc-testnet.json.addresses).
# V2 retained in v2_legacy_addresses_for_reference if a separate verification
# run is needed for those.
NAV=0xfEbB84BE47b0d440Ba08DaE0f5E3b09B4f989Cf8
ROUTER=0x0D9D3e16258AAF3297A67a443a55ADe0E3f49849
PARK=0x59a69BAFb6dCc9BF304bBE0583561aDf3B613435
INDEX=0xAdEa3FaE6011c2D275868d1c1933B37BE7648269
EXEC=0xb06a30226979789508306dAA9b027914045a4024
MOCK_USYC=0x2B540589EAF231b930Ed5D53ee3CE292904ccb2d
MOCK_MSG=0x2522423855550e82016103c79F097042Cf2d5a0B
ATTESTATION=0x1d2d34D941b13CbF233051074F007ecf68fB0F7f

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
