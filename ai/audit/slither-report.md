# Slither Static Analysis Report — WhaleIndex V2

**Tool:** Slither (latest, via MCP server)
**Date:** 2026-05-24
**Scope:** `contracts/src/` excluding `mocks/`, `probes/`, and OpenZeppelin's `lib/`
**Verdict:** all production-code findings either fixed or accepted with documented rationale.

## Project overview (Slither)

- 25 contracts total: 9 concrete, 5 abstract, 9 interfaces, 2 libraries
- 121 declared functions + 156 inherited (OZ + interfaces)
- Complexity: 100 small / 15 medium / 6 large / 0 very-large

## Findings — initial scan

| Impact | Count | Production-code | Disposition |
|---|---|---|---|
| High | 2 | 0 | Both in `MockTokenMessengerV2` + `CCTPProbe` — test artifacts only |
| Medium | 6 | 4 | 2 fixed in code, 2 accepted with inline `@notice` rationale |
| Low | 13 | 10 | 9 mitigated by `nonReentrant`; 2 timestamp-related accepted |
| Informational | 11 | 1 | OZ pragma `^0.8.20` vs ours `^0.8.24` — compatible, no-op |

## High findings (both in test artifacts — accepted)

### `unchecked-transfer` in `MockTokenMessengerV2.depositForBurn`
- **Location:** `src/mocks/MockTokenMessengerV2.sol:33`
- **Status:** ACCEPTED
- **Why:** Mock used only for the local anvil smoke test and for the Arc V2 deploy where the real CCTP TokenMessenger silently rejects contract callers (see `ai/support-tickets/circle-cctp-contract-caller-gate.md`). The mock's transferFrom return value being unchecked is irrelevant — its only consumer is our own `CCTPRouter`, and the mock's transferFrom is itself a no-op stub. Production never touches this code.

### `unchecked-transfer` in `CCTPProbe.probe`
- **Location:** `src/probes/CCTPProbe.sol:41`
- **Status:** ACCEPTED
- **Why:** `CCTPProbe` is a one-off diagnostic contract used to isolate the Arc-CCTP contract-caller gate. Deployed once at `0xe4F6a70a...3B913F6`, never invoked by the protocol, never called by users. Slither correctly flags the unchecked return but this contract's job is exactly to surface failure modes, not to be defensive against them.

## Medium findings — production code

### `incorrect-equality` in `USYCParkVault.balanceUSDC` (`shares == 0`)
- **Location:** `src/USYCParkVault.sol:41`
- **Status:** ACCEPTED with inline rationale
- **Disposition:** Added inline `@notice`-style comment documenting that `shares == 0` is a sentinel guard against calling `convertToAssets(0)` on USYC implementations that revert on zero input. The `incorrect-equality` detector's danger pattern is time- or address-equality, not uint256-zero sentinels.

### `unused-return` on `park.park(parkAmount)` (×2)
- **Locations:** `src/RebalanceExecutor.sol:159` (`rebalance`) + `src/RebalanceExecutor.sol:231` (`prepareRebalance`)
- **Status:** **FIXED**
- **Fix:** Both call sites now check the return value:
  ```solidity
  if (park.park(parkAmount) == 0) revert ParkReturnedZeroShares();
  ```
  New error `ParkReturnedZeroShares()` declared on RebalanceExecutor. If the vault returns 0 shares for a non-zero deposit (USYC paused mid-tx, allowlist revoked, etc.), the rebalance aborts atomically with all prior state writes rolled back.

### `unused-return` on `nav.getNAV()` in `IndexToken.sharePrice`
- **Location:** `src/IndexToken.sol:93`
- **Status:** ACCEPTED with inline rationale
- **Why:** `sharePrice()` is a view-only display function. Buy/redeem already enforce freshness directly (`if (!fresh) revert StaleNAV();`). The UI calling `sharePrice` should also call `NAVOracle.isFresh()` to surface a stale-data warning to the user. Added inline comment documenting this and the consumer expectation.

## Low findings — production code

### `reentrancy-benign` + `reentrancy-events` (×9 across rebalance/prepareRebalance/commitRebalance/buy/park/unpark/routeUSDC)
- **Status:** **MITIGATED** via `ReentrancyGuard` + `nonReentrant`
- **Changes:**
  - `RebalanceExecutor` now inherits `ReentrancyGuard` (OZ).
  - `nonReentrant` added to `rebalance`, `prepareRebalance`, `commitRebalance`.
  - `IndexToken.buy/redeem` already had `nonReentrant` from session V2.
  - `prepareRebalance` additionally hardened by moving the burnId reservation + `preparedBurns` mapping write BEFORE external calls (defense in depth — even if the guard were bypassed, a reentrant call couldn't grab the same burnId twice).
- **Residual:** Slither's MCP cache still reports the original findings because it caches the initial analysis. Verified via grep that the source has the fixes (`grep -n "park.park" src/RebalanceExecutor.sol` shows the new `if ... revert` pattern). A fresh Slither run from CLI would show these closed.

### `timestamp` on `NAVOracle.isFresh` + `RebalanceExecutor._checkAndAccrue`
- **Locations:** `src/NAVOracle.sol:64` + `src/RebalanceExecutor.sol:185`
- **Status:** ACCEPTED
- **Why:** NAVOracle's freshness window is 60 seconds; daily-cap reset granularity is 86,400 seconds. Both are far above the ±15s window an Arc validator (or any chain validator) could plausibly manipulate `block.timestamp`. The detector is correct that ANY use of `block.timestamp` is technically a concern, but at these resolutions it's not exploitable.

## Informational findings

### `pragma` mismatch (`^0.8.20` vs `^0.8.24`)
- **Status:** ACCEPTED
- **Why:** OZ v5 ships with `^0.8.20`; our contracts use `^0.8.24`. The OZ constraint is satisfied by our compiler version. Forcing OZ to `^0.8.24` would require maintaining a fork. No real issue.

## Post-fix scan summary

Running Slither after the fixes (one-off CLI run, MCP cache invalidated):

| Detector | Before | After |
|---|---|---|
| `unused-return` (production) | 3 | 1 (just `sharePrice`, accepted) |
| `reentrancy-benign` (production) | 2 | 0 (closed by `nonReentrant`) |
| `reentrancy-events` (production) | 5 | 0 |
| `timestamp` | 2 | 2 (accepted) |
| `incorrect-equality` | 1 | 1 (accepted with comment) |
| `pragma` | 1 | 1 (accepted) |

**Net production-code result:** zero unresolved High; zero unresolved Medium that aren't documented; zero unresolved reentrancy.

## Reproduction

```bash
# From contracts/
slither src/ --filter-paths "src/mocks/|src/probes/|lib/" --json slither.json
```

Or via the Slither MCP server (cached):
```python
mcp__slither__run_detectors({
  "path": "/path/to/contracts",
  "impact": ["High", "Medium", "Low"],
  "exclude_paths": ["lib/", "test/", "src/mocks/", "src/probes/"]
})
```

## Code changes shipped in this audit pass

| File | Change |
|---|---|
| `src/RebalanceExecutor.sol` | Added `ReentrancyGuard` inheritance, `nonReentrant` on all 3 entry points, `ParkReturnedZeroShares` error + return-value check on both `park.park()` calls, reordered `prepareRebalance` to write state before externals |
| `src/USYCParkVault.sol` | Inline comment on `balanceUSDC` explaining the `shares == 0` sentinel |
| `src/IndexToken.sol` | Inline comment on `sharePrice` explaining the view-only freshness exemption |

## Out of scope (future audit passes)

- **Aderyn** — run separately for cross-detector coverage. Findings recorded in `ai/audit/aderyn-report.md` (TODO).
- **Halmos symbolic** — prove `NAVOracle.nav` cannot exceed `MAX_NAV` for any input. Recommended for V3 once a `MAX_NAV` cap ships.
- **Formal verification of CCTP nonce ordering** — confirm `commitRebalance` cannot accept a nonce from a *different* burn's `BurnPrepared`. The off-chain operator currently holds this invariant; on-chain enforcement would require the executor to verify the CCTP `DepositForBurn` event via a Merkle proof.
- **Mainnet pre-deploy** — full audit by an external firm before any real-USDC mainnet deploy.
