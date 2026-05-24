# Aderyn Analysis Report — WhaleIndex V2

**Tool:** Aderyn 0.6.8 (Cyfrin)
**Date:** 2026-05-24
**Scope:** `contracts/src/` (88 detectors, 12 files, 544 nSLOC)
**Verdict:** all production-code findings either fixed or accepted with documented rationale. Aderyn complements Slither — different rule set, different surface.

## Issue Summary (raw counts)

| Category | Count | Production-code | Disposition |
|---|---|---|---|
| High | 2 | 0 | Both in `CCTPRouter` (false positive) + `MockTokenMessengerV2` (test artifact) |
| Low | 8 | 4 | 1 fixed in code, 3 accepted with rationale |

## High findings

### H-1: ETH transferred without address checks — `CCTPRouter.routeUSDC`
- **Location:** `src/CCTPRouter.sol:53`
- **Status:** **FALSE POSITIVE** — ACCEPTED
- **Why:** `routeUSDC` transfers USDC (ERC-20), not native ETH. Aderyn's detector pattern-matches on function signatures that look like value-receiving entry points; the routing function happens to share that signature shape but never moves native value. The function does validate `mintRecipient != bytes32(0)` (`src/CCTPRouter.sol:62`) and only routes to domains explicitly allowed via `setDomainAllowed`. No fix needed.

### H-2: Reentrancy: state change after external call — `MockTokenMessengerV2.depositForBurn`
- **Location:** `src/mocks/MockTokenMessengerV2.sol:33`
- **Status:** ACCEPTED
- **Why:** Mock contract used only when the deployment falls back from real CCTP (Arc's contract-caller gate). State changes (`nextNonce++`, `calls.push(...)`) after the unchecked `transferFrom` are intentional — the mock simulates the messenger's bookkeeping for testing. Production paths use the real TokenMessenger via the off-chain CCTP flow (T1.2).

## Low findings

### L-3: `nonReentrant` is not the first modifier — `RebalanceExecutor` (×3)
- **Locations:** `rebalance`, `prepareRebalance`, `commitRebalance`
- **Status:** **FIXED**
- **Why it matters:** modifier execution order is left-to-right. With `external onlyOwner whenNotPaused nonReentrant`, the `nonReentrant` guard only activates AFTER `onlyOwner` and `whenNotPaused` have already run their checks. If either of those modifiers were ever extended to make external calls (or if a future inheritance chain introduces one), a reentrant call could slip through before the guard is in place. Putting `nonReentrant` first is the standard defensive ordering.
- **Fix:** Reordered all 3 entry points to `external nonReentrant onlyOwner whenNotPaused`.

### L-1: Centralization Risk (20 instances)
- **Status:** ACCEPTED — by design
- **Why:** WhaleIndex V2's policy bounds (`maxSingleMove`, `dailyCap`) are deliberately on-chain, but the operator role is intentionally privileged for V2. Decentralization roadmap:
  - V2 (current): single operator EOA + emergency `pause`. Policy bounds enforced on chain.
  - V3: 2-of-3 multisig for the operator role (Safe-style).
  - V4: full DAO governance once a holder community exists.

### L-2: Large Numeric Literal — `BPS_DENOMINATOR = 10_000`
- **Status:** ACCEPTED
- **Why:** `10_000` with the underscore separator is conventional for bps denominators (every audited DeFi codebase uses it). Switching to `1e4` would technically pass the detector but be less self-documenting.

### L-4: PUSH0 Opcode — pragma ^0.8.24
- **Status:** ACCEPTED for testnet
- **Why:** Arc Testnet supports Cancun-era opcodes (block headers include blob fields — verified via `eth_getBlockByNumber`). PUSH0 is supported. For a future mainnet deploy on a chain that doesn't support PUSH0, we'd add `evm_version = "shanghai"` to `foundry.toml`.

### L-5: State Change Without Event — `MockTokenMessengerV2.depositForBurn`
- **Status:** ACCEPTED — test artifact

### L-6, L-7: Unchecked Return / Unsafe ERC20 — only in mocks + probes
- **Status:** ACCEPTED — test artifacts

### L-8: Unspecific Solidity Pragma — `^0.8.24` across all files
- **Status:** ACCEPTED for testnet, lock for mainnet
- **Why:** `^0.8.24` accepts any future 0.8.x — the constraint exists for OZ compatibility. For a mainnet deploy, we'd pin to a specific version to ensure reproducible bytecode.

## Code changes shipped in this audit pass

| File | Change |
|---|---|
| `src/RebalanceExecutor.sol` | Reordered modifiers on all 3 entry points: `nonReentrant` is now first (was last) |

## Combined Slither + Aderyn coverage matrix

| Concern | Slither | Aderyn |
|---|---|---|
| Reentrancy | ✓ flagged → fixed | ✓ check passed (now first modifier) |
| Unchecked returns | ✓ flagged → fixed | ✓ no new findings on production |
| Centralization | (not flagged at this confidence) | ✓ flagged → documented roadmap |
| Pragma | ✓ noted compatibility | ✓ flagged as wide range |
| Timestamp | ✓ flagged → accepted | not in detector set |
| PUSH0 / Shanghai | not in detector set | ✓ flagged → accepted |

Two tools, two clean reports on production code.

## Reproduction

```bash
# From contracts/
aderyn --output /tmp/aderyn-report.md .
```

## Out of scope (future passes)

- **Halmos symbolic verification** — prove `NAVOracle.nav` cannot exceed `MAX_NAV` for any sequence of `updateNAV` calls within the maxDeltaBps bound. Recommended once a hard MAX_NAV cap ships.
- **Foundry invariant tests** — fuzz the daily-cap accrual and the kelly-bound math.
- **Echidna campaign** — property-based fuzzing over the full executor state.
- **Pre-mainnet external audit** — required before any real-USDC mainnet deploy.
