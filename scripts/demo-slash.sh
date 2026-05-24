#!/usr/bin/env zsh
# Live demo of the V3 WhaleAttestation slash flow:
#   1. Operator registers their own address as a whale (operator + whale = same EOA for the demo)
#   2. Operator approves USDC + bonds 0.05 USDC
#   3. Verify bondAmount > 0
#   4. Build a slash evidence document + content-hash CID
#   5. Operator calls attestation.slash(wallet, 1000, cid) — 10% slash
#   6. Verify bondAmount decreased by 10% (0.005 USDC moved to IndexToken)
#
# Total spend: ~0.05 USDC bond + 0.005 USDC slash + ~0.005 gas = ~0.06 USDC.

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
USDC=0x3600000000000000000000000000000000000000
DEPLOYER=0xf9946775891a24462cD4ec885d0D4E2675C84355
INDEX=0xAdEa3FaE6011c2D275868d1c1933B37BE7648269  # slashBeneficiary

BOND_AMOUNT=50000      # 0.05 USDC base units
SLASH_BPS=1000         # 10%

cd "${0:A:h}/.."

echo "=== 0. Pre-state ==="
echo "operator USDC:       $(cast call $USDC 'balanceOf(address)(uint256)' $DEPLOYER --rpc-url $ARC_RPC_URL)"
echo "attestation bond:    $(cast call $ATT 'bondAmount(address)(uint256)' $DEPLOYER --rpc-url $ARC_RPC_URL)"
echo "IndexToken USDC:     $(cast call $USDC 'balanceOf(address)(uint256)' $INDEX --rpc-url $ARC_RPC_URL)"

echo
echo "=== 1. Operator registers self as a whale (setRegisteredWhale) ==="
cast send "$ATT" "setRegisteredWhale(address,bool)" "$DEPLOYER" true \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash" | head -3

echo
echo "=== 2. Approve attestation contract for $BOND_AMOUNT USDC ==="
cast send "$USDC" "approve(address,uint256)" "$ATT" "$BOND_AMOUNT" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed" | head -2

echo
echo "=== 3. Bond $BOND_AMOUNT USDC ==="
cast send "$ATT" "bond(uint256)" "$BOND_AMOUNT" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash" | head -3

echo
echo "post-bond bondAmount: $(cast call $ATT 'bondAmount(address)(uint256)' $DEPLOYER --rpc-url $ARC_RPC_URL)"
echo "post-bond isBonded:   $(cast call $ATT 'isBonded(address)(bool)' $DEPLOYER --rpc-url $ARC_RPC_URL)"

echo
echo "=== 4. Build slash evidence doc + content-hash CID ==="
mkdir -p docs/slashes
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EPOCH=$(date -u +%s)
# Write a canonical JSON; compute keccak256 from canonical-sorted JSON to match
# the orchestrator's _build_slash_doc + _publish_slash_doc pattern.
python3 - <<PY
import json, hashlib
from pathlib import Path
from web3 import Web3
doc = {
    "version": 1,
    "kind": "slash_evidence",
    "snapshot_at": $EPOCH,
    "snapshot_iso": "$TS",
    "wallet": "$DEPLOYER",
    "prior_rank": 1,
    "current_rank": 4,
    "decay_places": 3,
    "slash_bps": $SLASH_BPS,
    "slash_bps_cap": 5000,
    "reason": "DEMO: operator-as-whale slash test; decay 3 places past threshold",
    "policy": "decay_severity_to_slash_bps: <=1 places -> 0, 2-3 -> 500, 4-5 -> 1500, 6-10 -> 3000, 11+ -> max_slash_bps",
}
canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
cid = Web3.keccak(canonical)
out = Path("docs/slashes") / f"{cid.hex()}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, sort_keys=True, indent=2))
print(f"evidence cid: 0x{cid.hex()}")
print(f"path:         {out}")
PY

CID=$(ls -t docs/slashes/*.json | head -1 | xargs basename -s .json)
echo "extracted cid: $CID"

echo
echo "=== 5. Slash 10% (1000 bps) with evidence CID ==="
cast send "$ATT" "slash(address,uint16,bytes32)" "$DEPLOYER" "$SLASH_BPS" "0x$CID" \
  --rpc-url "$ARC_RPC_URL" --private-key "$DEPLOYER_PRIVATE_KEY" 2>&1 \
  | grep -E "status|gasUsed|transactionHash" | head -3

echo
echo "=== 6. Post-slash state ==="
POST_BOND=$(cast call $ATT 'bondAmount(address)(uint256)' $DEPLOYER --rpc-url $ARC_RPC_URL | awk '{print $1}')
POST_INDEX=$(cast call $USDC 'balanceOf(address)(uint256)' $INDEX --rpc-url $ARC_RPC_URL | awk '{print $1}')
echo "bond remaining:       $POST_BOND  (expected: $BOND_AMOUNT * (10000-$SLASH_BPS)/10000 = $(( $BOND_AMOUNT * (10000 - $SLASH_BPS) / 10000 )))"
echo "IndexToken USDC:      $POST_INDEX  (rose by the slash amount: $(( $BOND_AMOUNT * $SLASH_BPS / 10000 )))"

echo
echo "Demo complete. Verify the slash on Arcscan:"
echo "  https://testnet.arcscan.app/address/$ATT"
echo "Evidence doc will be public at:"
echo "  https://yonkoo11.github.io/whaleindex/slashes/$CID.json"
