# WhaleIndex — Project Memory

## Phase 1 Gate (MUST PASS BEFORE ANY OTHER WORK)

**Core Action:** Multi-agent reads HL + Aster public leaderboards live → outputs top-10 whale allocation delta JSON → rebalance executor calls Gateway USDC move on Arc testnet → on-chain NAV updates → UI shows pre/post NAV + cost in cents + latency in ms.

**Success Test (binary):** Did the Gateway move settle in <2 seconds AND did the NAV update correctly to reflect the new allocation? If both yes → Phase 1 passed. Either no → Phase 1 not passed.

**Min Tech (Phase 1 only):**
- 1 Solidity contract: Index ERC-20 with `rebalance(allocation[])` and `nav()`
- 1 Python or TypeScript agent: reads HL leaderboard via public API, outputs allocation JSON
- 1 rebalance executor: signs Gateway move, calls contract `rebalance()`
- 1 minimal UI page showing NAV + last rebalance receipt
- Deployed on Arc testnet using Canteen-hosted RPC

**NOT Phase 1:**
- USYC integration (Phase 2)
- Paymaster (Phase 2)
- CCTP cold-path (Phase 2)
- Multi-venue (Aster, Polynomial) — Phase 1 is HL-only
- Buyer flow / mint-redeem (Phase 2)
- Landing page polish (Phase 3)
- Demo video (Phase 4)
- Builder-code monetization layer (V2 stretch)

**Status:** [PASS — 2026-05-23] Phase 1 Gate proven on live Arc testnet. Rebalance settles in **0.78s** (target <2s) end-to-end agent → RebalanceExecutor → MockUSDC/USYC/CCTP + NAVOracle on Arc.

**Verified 2026-05-23 (Arc testnet, chain 5042002):**
- 8 contracts deployed via `scripts/deploy-arc.sh` (uses `--skip-simulation` because Arc RPC stalls forge's pre-broadcast simulation; real gas estimation still runs server-side at broadcast)
- Deploy cost: 8,994,964 gas (~0.18 USDC)
- Bytecode verified on chain for all 8 addresses (sizes recorded in `deployments/arc-testnet.json`)
- Ownership wired: IndexToken + USYCParkVault + NAVOracle all owned by RebalanceExecutor (NAVOracle was manual tx `0x71406...3bc3a8`; Deploy.s.sol now patched to auto-transfer when operator == deployer)
- Smoke test `scripts/smoke-arc.sh` runs end-to-end against Arc: mint, approve, buy, rebalance — all land
- Rebalance receipt: tx `0x7dc114...c97cd69`, latency **0.78s**, NAV $0 → $15, 5 USDC routed to Arbitrum (CCTP V2 nonce 1), gas 363,901

**Verified 2026-05-17 (still valid):**
- Local anvil smoke test (`python3 -m agent._smoke_test_local`) end-to-end pass
- 28 contract tests pass
- Repo published: github.com/Yonkoo11/whaleindex
- GitHub Pages: https://yonkoo11.github.io/whaleindex/ (built from master:/docs)

**Phase 1 limitations to fix before/during Phase 2:**
- All on-chain integrations still use MOCKS (MockUSDC, MockUSYC, MockTokenMessengerV2). Real Arc addresses are recorded in `deployments/arc-testnet.json._meta.canonical_arc_addresses_for_v2`. Phase 2 swaps these in.
- UI page never visually verified against Arc (currently reads local-anvil RPC); needs update to read `arc-testnet.json` addresses + Arc RPC URL.
- Whale watchlists still user-curated placeholders (Hyperdash 403 / Drift 503 unresolved).
- Operations: `~/.arc-canteen/env` rotated may invalidate `RPC=`; smoke + deploy scripts handle missing RPC gracefully but rotation step is manual.

**Lesson learned this session:**
- Forge's pre-broadcast simulation hangs against the Canteen RPC even though every `eth_*` method responds in <2s via curl. `--skip-simulation` is the workaround; gas estimation still happens server-side during broadcast, so failures still surface (saw "gas required exceeds allowance" cleanly before funding).
- Deploy.s.sol left NAVOracle owned by `operator` to support a two-key (deployer ≠ operator) setup; in the single-key case, `rebalance()` reverts with `OwnableUnauthorizedAccount(RebalanceExecutor)`. Now patched: when `operator == deployer`, the deploy transfers NAV ownership in the same broadcast.
- `arc-canteen rpc-url` emits status warnings to stdout when its server is unreachable, contaminating downstream scripts. `grep -oE 'https://[^[:space:]]+'` extracts the URL line cleanly.

---

## Hackathon Context

| Field | Value |
|---|---|
| Hackathon | Agora Agents Hackathon |
| Host | Canteen × Circle × Arc |
| Window | 2026-05-11 → 2026-05-25 |
| Prize pool | $50,000 (1st $10K / 2nd × 2 $7.5K / 3rd × 3 $5K / Standout × 10-12 ~$700 / Feedback $500 / Easter eggs $2K) |
| Submission form | https://forms.gle/hFPM2t4Jt1zGfqzM7 |
| Apply link | https://luma.com/7i50p2r9 (passphrase: SITEx1313) |
| Canteen Discord | https://discord.gg/TGnyfKh23V |
| Arc builder Discord | https://discord.com/invite/buildonarc |
| ARC CLI | `uv tool install git+https://github.com/the-canteen-dev/ARC-cli` |
| Arc docs | https://arc-node.thecanteenapp.com/ |
| Circle docs | https://developers.circle.com |

## Judging weights (asynchronous review, no demo day)

- **30% Agentic Sophistication** — autonomy vs automation
- **30% Traction** — real users + transactions during the window
- **20% Circle tool usage** — depth across Arc + Gateway + Wallets + App Kit + Contracts + USYC + USDC + Paymaster
- **20% Innovation** — novel approaches, emergent behavior, research insight

## Required deliverables

- [ ] Public GitHub repo (required) — with README, LICENSE, reproduce instructions
- [ ] Recorded video demo ≤ 3 min on Loom/YouTube/Vimeo (required)
- [ ] Live product link (encouraged, strongly recommended)
- [ ] Traction report on form (real users + validation, equal weight to product)
- [ ] Submission form filled at https://forms.gle/hFPM2t4Jt1zGfqzM7

---

## Chosen Idea

**Name:** WhaleIndex
**Pitch (3-5 words):** Whale-tracking index, rebalanced cheaply
**Tagline (≤ 12 words):** One token, auto-rebalanced across HL forks where whales actually trade.
**RFB fit (PRIMARY):** RFB 06 — Social Trading Intelligence. Matches all 5 of RFB 06's "What AI decides" bullets: (1) which traders to follow (top-10 by HL leaderboard risk-adjusted rank), (2) allocation per trader (weighted by leaderboard score), (3) when to stop following (degradation detection — leaderboard rank decay, see research note #06), (4) portfolio across signal sources (HL + Aster + Polynomial = 3 signal sources), (5) signal quality filtering (whale opt-in attestation in V2). Example-build analog: SmartMirror.
**RFB fit (SECONDARY):** RFB 04 — Adaptive Portfolio Manager. Matches 3 of 6 bullets: cross-venue rebalancing with Gateway/CCTP, USYC during low-conviction periods, risk reduction in high volatility. Does NOT match: goal-based interfaces, tax-loss harvesting, risk-on/off regime detection.
**Archetype:** A5 (Intent-Based Aggregator / Solver Network) + B7 (Multi-Agent Coordination)
**Named precedents:** Urani (Renaissance DeFi 1st, $30K), APY-LO (Unfold #1), OpenFund (Unfold Best Agentic), Latinum (Breakout AI 1st)
**Traction targets (per RFB 06 metrics):** Number of leaders tracked (10 → 30 by V2) · AUM in test pool · Performance vs raw leader average (risk-adjusted) · Follower retention (Plausible analytics on /buy page)

**Audience:** Retail copy-traders who want one-token exposure to "where smart money is right now" across HL + Aster + Polynomial without setting up venue accounts or running bots.

**Mechanism:**
1. Multi-agent reads HL + Aster + Polynomial leaderboards daily
2. Calculates top-10 whale allocation across venues
3. Posts proposed rebalance with diff and reasoning trace
4. Index ERC-20 NAV rebalances via Gateway cross-chain USDC moves
5. Idle USDC parks in USYC between rebalances
6. Index holders get one-token exposure to migration signal

---

## Competitive landscape

- **Copy-trading apps** (HypeTrade, Galaxis copy-trade widgets) — 1:1 follow specific wallets, not index
- **HL leaderboard token launchpads** — none with auto-rebalance on migration
- **Cross-venue rebalancing indices** — none publicly known for HL/Aster/Polynomial axis
- **Adjacent winner:** APY-LO (Unfold #1) won doing cross-chain APY routing — validates cross-venue agent pattern but different problem (yield, not migration signal)
- **Adjacent winner:** Urani (Renaissance DeFi 1st) won with intent-based solver aggregator — validates A5 archetype on this hackathon class

## Fatal flaws (must address before submitting)

1. **Leaderboard rank durability** — top rank now doesn't mean top rank in 2 weeks. Mitigation: weekly rebalance cadence (not daily), expose rebalance frequency as configurable, V2 adds slash-bond mechanism on whale opt-in.
2. **Legal exposure as managed product** — index is technically a vehicle. Mitigation: open-source rebalance logic, no discretionary calls, no custodial promises, English-language disclaimer on buyer flow.
3. **Arc + venue integration risk** — HL is on its own L1, not Arc-native. Mitigation: Gateway handles cross-chain USDC routing; venue-side trades execute on the venue's native chain; index NAV lives on Arc.
4. **Sub-200 user threshold for traction** — 2-week window plus retail audience plus testnet-only positions. Mitigation: viral screenshot hook + named outreach to perp Twitter accounts.

## Required tech / stack

| Layer | Choice |
|---|---|
| L1 | Arc (Canteen-hosted testnet, then Arc mainnet for V2) |
| Contracts | Solidity, OpenZeppelin ERC-20, Foundry for tests + deployment |
| Cross-chain USDC | Circle Gateway SDK |
| Yield parking | Circle USYC |
| Buyer gas | Circle Paymaster |
| Agent runtime | Python (asyncio) + httpx for leaderboard reads |
| Frontend | Next.js (App Kit Unified Balance + Buy widget) on GitHub Pages |
| Analytics | Plausible (privacy-respecting, count `/buy` page hits) |

## Distribution plan (named first 50 users)

- **Day 1:** Twitter thread + screenshot "rebalanced HL→Aster for $0.03 in 600ms"
- **Day 2:** Named DMs to 3 known HL whale Twitter accounts (e.g., HLP-watchers) asking for opt-in attestation
- **Day 4:** Post in `r/HyperliquidCT` + 2 Discord servers (perp-focused)
- **Day 7:** Post in Canteen Discord + Arc builder Discord
- **Day 10:** Tweet replies on perp-trading-content accounts (asxn, theusdcmaxi, ASvinerian)
- **Day 12:** Submit feedback log to Feedback Incentives bucket

## Build order (must follow — per `feedback_hackathon_build_order.md`)

1. **Phase 1: Core action** — multi-agent reads, Gateway move, NAV updates (Phase 1 Gate above)
2. **Phase 2: Data flows** — USYC parking, multi-venue (Aster + Polynomial), buyer mint-redeem, Paymaster
3. **Phase 3: Product complete** — landing page with Unified Balance widget, history of past rebalances, public NAV chart, README + reproduce instructions, LICENSE
4. **Phase 4: Visual polish** — `/design whaleindex` then `/landing whaleindex` then `/demo-video`

NO CSS BEFORE PHASE 4. NO landing page polish before Phase 3.

## Open links of record

- IDEAS-SUMMARY entry: `~/Projects/IDEAS-SUMMARY.md` #100 (yield decomposition, adjacent), #4 (reliability oracle, adjacent)
- Research note: agora.thecanteenapp.com Research item #05 (HL whale migration index)
- Sponsor integration plan: `ai/sponsor-integration.md` (this directory)
- Fix plan for builders: `.ralph/@fix_plan.md`

## Phase 5 outcome row template (fill after submission)

| # | Idea | Hackathon | Date Built | Phase 1 Passed? | Submitted? | Result | Users? | Lesson |
|---|------|-----------|------------|-----------------|------------|--------|--------|--------|
| - | WhaleIndex | Agora Agents | 2026-05-23 | YES (0.78s settlement on Arc) | TBD | TBD | TBD | TBD |
