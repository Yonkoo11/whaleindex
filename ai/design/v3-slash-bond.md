# V3 Mechanism Design — Whale Opt-In Slash-Bond

**Status:** reference implementation shipped at `contracts/src/v3/WhaleAttestation.sol`, 21 forge tests green, not yet deployed.

## Problem

Every existing copy-trading / social-trading index has the same structural flaw: **the signal source carries zero economic accountability**. A whale's past performance becomes the index's signal; they receive no upside from helping the index work, and no downside if their strategy degrades and the index follows them down.

This is the source of the RFB 06 "follow blindly" failure mode. Index holders absorb 100% of the loss from a decayed leader; the leader keeps their reputation intact and moves on to the next product that copies them.

## Mechanism

`WhaleAttestation` lets a whale **opt in** to skin-in-the-game:

1. **Operator allowlists** a wallet (must already be on the off-chain watchlist).
2. **Whale posts a USDC bond** from their own wallet. Bond size is the whale's choice. The bond's public size becomes the on-chain attestation badge of conviction.
3. **Bond is locked** while the index actively mirrors them.
4. **Rank-decay agent** (`selection_engine.py`) evicts whales whose rank fell by > `decay_threshold` places. When the agent evicts a bonded whale, the **operator calls `slash(wallet, slashBps, evidenceCid)`** with the eviction reasoning anchored to an off-chain document (same CID pattern as `AllocationDecided` in `RebalanceExecutor`).
5. **Slashed USDC routes to `slashBeneficiary`** (typically the index treasury), partial restitution for holders mirrored through the decay.
6. **Whale calls `requestUnbond`** to start an `unbondCooldown` timer. Crucially, the bond remains **slashable during the cooldown** — a whale can't front-run a slash by unbonding.
7. **After cooldown elapses**, `claimUnbond()` returns whatever remains.

## Invariants enforced on chain

- `slashBps <= maxSlashBps` (default 5000 = 50%, owner-tunable)
- `evidenceCid != bytes32(0)` (every slash carries off-chain provenance)
- `unbondCooldown` is configurable; default 7 days
- `bond` reverts unless `registered[msg.sender] == true`
- Bond top-up cancels any pending unbond request (re-commits to the index)
- Slash is allowed during cooldown (anti-front-run)
- All state-mutating functions guarded by `nonReentrant` + `whenNotPaused`
- `pause()` halts new bonds, slashes, requests, and claims — emergency stop

## Why this is the right "Innovation" contribution for RFB 06

The Agora rubric's Innovation 20% category explicitly rewards "novel approaches, emergent behavior, research insight." The 5 most common derivative copy-trading frames (Toros, dHEDGE, SocialFi mirror tokens, leaderboard widgets, intent solvers that copy trades) all share the same hole: leaders bear no cost when they degrade. This mechanism closes it.

Three design choices that distinguish this from "generic staking":

1. **Cooldown-resistant slashing.** The cooldown is for the WHALE'S protection (they can withdraw before they stop trading), not the operator's. Slashing during cooldown is the point — otherwise a whale who saw the eviction coming could escape it.
2. **Evidence CID required.** Every slash anchors to a public off-chain document — same provenance pattern as `AllocationDecided` in the rebalance flow. A whale who believes they were unfairly slashed has a public, immutable record to dispute against.
3. **Bond size is the signal.** A whale who posts $10K vs $100 is publicly committing to different levels of conviction. The frontend can surface bonded-vs-unbonded whales differently; index holders can self-select for the higher-conviction subset.

## How it plugs into the existing flow

```
selection_engine.evaluate(scores)
  → rank-decay decisions: list of (wallet, verdict, reason)
  ↓
For each decision where verdict == "evict_decay":
  if attestation.isBonded(wallet):
    # Publish slash evidence doc to docs/allocations/<evidenceCid>.json
    # (same content-hash + GitHub Pages pattern as allocation docs)
    operator EOA calls:
      WhaleAttestation.slash(wallet, slashBps, evidenceCid)
  # Then standard eviction continues — wallet drops out of the survivors set
  # that feeds AllocatorAgent.

ALSO:
  agent/agents/scorer.py.score()
    For bonded whales, add a small bonus to recency_weight (configurable)
    so a bonded whale gets the benefit of the doubt within the rank-decay band.
```

The integration is OFF-CHAIN at the slash trigger (operator decides when decay is severe enough to slash) but ON-CHAIN at the slash effect (USDC moves, attestation updates, event emitted).

## What V3 deployment requires

1. Deploy `WhaleAttestation` with:
   - `usdc` = real Arc native USDC `0x3600...0000`
   - `slashBeneficiary` = `IndexToken` address (slash flows to index treasury, lifting NAV for surviving holders)
   - `maxSlashBps` = 5000
   - `unbondCooldown` = 7 days
   - `operator` = the orchestrator's operator EOA (same key that signs rebalances)
2. Add `WHALE_ATTESTATION` to `deployments/arc-testnet.json.addresses`.
3. Update `selection_engine.evaluate` to:
   - Accept an optional `WhaleAttestation` adapter (Python side calls the contract via `web3.py`)
   - On `evict_decay` verdict, return a tagged decision (`slash_pending`) instead of just `evict_decay`
4. Update `agent/orchestrator.py` Step 3.5 to:
   - For each `slash_pending` decision, build an evidence doc (similar shape to allocation doc), keccak it, publish to `docs/slashes/<cid>.json`, then call `attestation.slash(wallet, slashBps, cid)`.
   - Add the slash transactions to `data/orchestrator-history.jsonl`.
5. Frontend (`docs/index.html`) adds a "Bonded whales" card showing the active bonds + `unbondEligibleAt` + recent slash history.

## What this is NOT

- It's not opt-out — a whale who doesn't bond still appears in the watchlist if curated by the operator. They just don't have the public skin-in-game attestation.
- It's not real-time. Slash is operator-triggered, not automatic. This is by design — automatic slashing risks ban-by-mistake when, e.g., the HL API has an outage.
- It's not the index treasury. The treasury is `IndexToken` — bond slashes flow there to lift NAV. The bond contract is a separate escrow.

## Out of scope for V3

- **DAO governance** of `slashBps`, `slashBeneficiary`, `unbondCooldown`. V3 keeps these owner-managed; V4 moves them behind a 2/3 multisig or proper DAO.
- **Multi-token bonds** — bond is USDC-only in V3 to keep accounting simple.
- **Dispute / appeal mechanism** — V3 records the evidence CID immutably; a future V4 could add an on-chain dispute window where a slashed whale can stake a counter-bond to challenge.
- **Risk-adjusted slash sizing** — V3's `slashBps` is operator-set; V4 could derive it from the realized loss the index took during the whale's decay window.

## Test coverage (21 forge tests, all green)

| Behavior | Test |
|---|---|
| `bond` requires registration | `test_bond_revertsWhenNotRegistered` |
| `setRegisteredWhale` is owner-only | `test_setRegisteredWhale_onlyOwner` |
| Bonds accumulate across multiple deposits | `test_bond_acceptsAndAccumulates` |
| `bond(0)` reverts | `test_bond_revertsOnZero` |
| Bond top-up cancels pending unbond request | `test_bond_cancelsPendingUnbondRequest` |
| Slash moves USDC to beneficiary | `test_slash_movesUsdcToBeneficiary` |
| Slash bound by `maxSlashBps` | `test_slash_revertsAboveMaxSlashBps` |
| Zero slashBps rejected | `test_slash_revertsOnZeroBps` |
| Zero evidence CID rejected | `test_slash_revertsOnZeroCid` |
| Slash without bond reverts | `test_slash_revertsWithoutBond` |
| Slash is owner-only | `test_slash_onlyOwner` |
| Unbond flow respects cooldown | `test_unbondFlow_succeedsAfterCooldown` |
| Double unbond-request reverts | `test_requestUnbond_revertsIfAlreadyRequested` |
| **Slashable during cooldown** (anti-front-run) | `test_slashable_during_cooldown` |
| `claimUnbond` without request reverts | `test_claimUnbond_revertsWithoutRequest` |
| `unbondEligibleAt` view returns 0 without request | `test_unbondEligibleAt_returnsZeroWithoutRequest` |
| `setMaxSlashBps` owner-gated + zero-rejected | 2 tests |
| `pause` blocks bond + slash | `test_pause_blocksBondAndSlash` |
| Constructor rejects zero addresses + invalid bps | 2 tests |

## Files shipped

- `contracts/src/v3/WhaleAttestation.sol` — 205 lines including extensive doc comments
- `contracts/test/WhaleAttestation.t.sol` — 21 tests covering bond/slash/unbond + admin + invariants
- `ai/design/v3-slash-bond.md` — this document
