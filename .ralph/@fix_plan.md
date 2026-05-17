# Fix Plan — WhaleIndex

Builder agent reads this file top-to-bottom. Each task has a binary acceptance test. Mark a task `[x]` only after the acceptance test passes against a running system, not against compiled code.

## Phase 1 — Core Action (BLOCKING — finish before Phase 2)

- [ ] Task 1: Bootstrap Foundry project + install Arc-CLI on this machine
  - Files: `contracts/foundry.toml`, `contracts/lib/`, `~/.config/arc/`
  - Acceptance: `forge build` succeeds in `contracts/`; `arc --help` prints CLI help

- [ ] Task 2: Write IndexToken.sol — ERC-20 with `rebalance(address[] venues, uint256[] weights)` (owner-only for Phase 1) and `nav()` view
  - Files: `contracts/src/IndexToken.sol`, `contracts/test/IndexToken.t.sol`
  - Acceptance: `forge test` passes for: mint, transfer, rebalance event emitted, nav() returns expected sum

- [ ] Task 3: Deploy IndexToken to Arc testnet via Canteen-hosted RPC
  - Files: `contracts/script/Deploy.s.sol`, `deployments/arc-testnet.json`
  - Acceptance: contract address on Arc explorer, `totalSupply()` returns >0

- [ ] Task 4: Write Python leaderboard-reader agent — reads HL public leaderboard, outputs `{wallet: weight}` JSON for top 10
  - Files: `agent/leaderboard_reader.py`, `agent/requirements.txt`
  - Acceptance: `python -m agent.leaderboard_reader` returns 10 wallet addresses with weights summing to 1.0

- [ ] Task 5: Write rebalance executor — signs and submits Gateway USDC move + contract `rebalance()`
  - Files: `agent/rebalance_executor.py`, `agent/gateway_client.py`
  - Acceptance: invoking executor with mock allocation produces a Gateway-tx hash on Arc testnet, NAV updates in IndexToken state

- [ ] Task 6: Minimal Next.js UI — single page showing current NAV + last rebalance receipt (timestamp, cost in cents, latency in ms)
  - Files: `web/pages/index.tsx`, `web/lib/contract.ts`
  - Acceptance: `pnpm dev` loads page locally, NAV reads from Arc testnet contract

- [ ] Task 7: End-to-end Phase 1 Gate test
  - Acceptance: trigger executor manually → Gateway move settles in <2 seconds → NAV updates correctly → UI shows the new NAV + receipt within 5 seconds → **screenshot-shareable moment captured**
  - **If this passes, Phase 1 is DONE. Update `ai/memory.md` status to `[x] PASSED`.**

## Phase 2 — Data Flows (after Phase 1 passes)

- [ ] Task 8: Add Aster leaderboard reader → multi-venue allocation
- [ ] Task 9: Add Polynomial leaderboard reader → 3-venue allocation
- [ ] Task 10: USYC parking integration — idle USDC > threshold auto-routes to USYC
- [ ] Task 11: Buyer mint flow — user pays USDC, receives IndexToken
- [ ] Task 12: Paymaster wiring — buyer without Arc native gas completes purchase
- [ ] Task 13: Buyer redeem flow — user burns IndexToken, receives USDC

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
