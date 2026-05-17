# Fix Plan — WhaleIndex

Builder agent reads this file top-to-bottom. Each task has a binary acceptance test. Mark a task `[x]` only after the acceptance test passes against a running system, not against compiled code.

## Phase 1 — Core Action (BLOCKING — finish before Phase 2)

- [x] Task 1: Bootstrap Foundry project + OZ v5 contracts library
  - Files: `contracts/foundry.toml`, `contracts/lib/forge-std`, `contracts/lib/openzeppelin-contracts`
  - Acceptance: `forge build` succeeds in `contracts/` — DONE 2026-05-17

- [x] Task 2: Six core contracts written + 28 passing tests (replaces the original IndexToken-only Task 2)
  - Files: `contracts/src/IndexToken.sol`, `contracts/src/NAVOracle.sol`, `contracts/src/CCTPRouter.sol`, `contracts/src/USYCParkVault.sol`, `contracts/src/RebalanceExecutor.sol`, `contracts/src/interfaces/*.sol`, `contracts/src/mocks/*.sol`, `contracts/test/*.t.sol`
  - Acceptance: `forge test` shows 28 passed / 0 failed — DONE 2026-05-17

- [ ] Task 3: Deploy full stack to Arc testnet via Canteen-hosted RPC + record addresses
  - Files: `contracts/script/Deploy.s.sol` (DONE), `deployments/arc-testnet.json` (TBD)
  - Acceptance: all 8 contract addresses on Arcscan, `Deploy.s.sol` broadcast succeeds, addresses written to `deployments/arc-testnet.json`

- [x] Task 4: Python leaderboard-reader agent reads live Hyperliquid `clearinghouseState`
  - Files: `agent/leaderboard_reader.py`, `agent/allocation_engine.py`, `agent/main.py`, `agent/requirements.txt`, `data/whales-hl.json`
  - Acceptance: `python3 agent/main.py` returns a JSON plan with whales_count >= 0 and allocations array — DONE 2026-05-17

- [ ] Task 5: Wire rebalance executor signing — agent signs an Arc tx that calls `RebalanceExecutor.rebalance(...)` and a `CCTPRouter` move lands on chain
  - Files: `agent/rebalance_executor.py`, `agent/contract_client.py`
  - Acceptance: invoking executor with one allocation produces an on-chain `Routed` event + `NAVUpdated` event on Arc testnet

- [ ] Task 6: Minimal Next.js UI — landing page with NAV, last rebalance receipt, buy/redeem stubs
  - Files: `web/pages/index.tsx`, `web/lib/contract.ts`
  - Acceptance: `pnpm dev` loads page locally, NAV reads from Arc testnet contract via viem

- [ ] Task 7: End-to-end Phase 1 Gate test on Arc testnet
  - Acceptance: agent reads one HL whale → CCTPRouter.Routed event lands on Arc testnet → NAVOracle.NAVUpdated event lands → UI shows new NAV + receipt → **screenshot-shareable moment captured**
  - **If this passes, Phase 1 is DONE. Update `ai/memory.md` status to `[x] PASSED`.**

## Phase 2 — Data Flows (after Phase 1 passes)

- [ ] Task 8: Add Aster leaderboard reader → multi-venue allocation
- [ ] Task 9: Add Polynomial leaderboard reader → 3-venue allocation
- [ ] Task 10: USYC parking integration — idle USDC > threshold auto-routes to USYC
- [ ] Task 11: Buyer mint flow — user pays USDC, receives IndexToken
- [ ] Task 12: Paymaster wiring — buyer without Arc native gas completes purchase
- [ ] Task 13: Buyer redeem flow — user burns IndexToken, receives USDC
- [ ] Task 13a: Strategy-degradation detector (RFB 06 explicit ask) — rolling 30d Sharpe per whale, drop from top-10 when rank decays >2 places or Sharpe drops >40%, log eviction with reason to NAV history
- [ ] Task 13b: Risk-adjusted weighting — replace flat top-10 with Sharpe-weighted allocation across the 10 whales

## Phase 3 — Product Complete

- [ ] Task 14: README with reproduce-this instructions
- [ ] Task 15: Add LICENSE (MIT or Apache 2.0)
- [ ] Task 16: Landing page with App Kit Unified Balance widget
- [ ] Task 17: History view — list of past 30 rebalances with NAV deltas
- [ ] Task 18: Public NAV chart
- [ ] Task 19: Plausible analytics on `/buy` page
- [ ] Task 20: Feedback log (`ai/feedback-log.md`) — document every Circle DX friction point

## Phase 4 — Polish + Submit

- [ ] Task 21: Run `/design whaleindex`
- [ ] Task 22: Run `/landing whaleindex`
- [ ] Task 23: Run `/demo-video` for ≤ 3 min walkthrough
- [ ] Task 24: Phase 4.5 sponsor-depth re-audit (run within 48h of 2026-05-25)
- [ ] Task 25: Phase 4.7 communication-pack checklist
- [ ] Task 26: `/submit whaleindex` — final pre-deadline checklist
- [ ] Task 27: Distribution day-1: tweet thread + screenshot

## Completed
(builder agent fills this in)
