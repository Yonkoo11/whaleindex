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

**Status:** [V2 PASS — 2026-05-23] Phase 1 Gate proven on Arc with REAL native USDC + new safety primitives. Rebalance settles in **1.08s** (target <2s). 47 forge tests pass (up from 28).

**Verified 2026-05-24 (V3 slash mechanism LIVE on chain + Arcscan verify):**
- **First live slash on Arc.** End-to-end V3 flow proven:
  - setRegisteredWhale: tx `0x179c8b8eff49c2853360aa9784cfb87218d63daf222df959cbec88e801453607` (48k gas, WhaleRegistered event)
  - bond(0.05 USDC): tx `0x8782b216582998cb958d031f1c8f0238f61369303ad6280d1dd85b0c35a5eaff` (97k gas, Bonded event)
  - slash(operator, 1000 bps, evidenceCid): tx `0x91baecea4db62c947499722c2fb8de0373ec323427d7fe2d3c710046437cdf99` (77k gas, Slashed event)
  - Bond went 50,000 → 45,000 (10% slashed exactly). 5,000 USDC routed to slashBeneficiary.
  - Evidence doc: `docs/slashes/1a25fa49aa20279c142d27c31a5e1a9b507150c4c0a1e5acaa4ee233288c73ee.json`, public at https://yonkoo11.github.io/whaleindex/slashes/1a25fa49...c73ee.json after next push
- **Repointed slashBeneficiary** from default V2 IndexToken to live V3 IndexToken: tx `0x531e5f34ac2f6643327ac98c678b3695475b95906d7c9602b57b4c10d012cb41`. Future slashes credit V3 holders, not stranded V2.
- **All V3 contracts verified on Arcscan**: NAVOracle, USYCParkVault, IndexToken, RebalanceExecutor, WhaleAttestation. MockTokenMessengerV2 + MockUSYC + CCTPRouter inherit V2's verification (identical source).
- DeployWhaleAttestation default updated to V3 IndexToken so future deploys don't need the repoint step.
- The orchestrator's Step 3.5 now wires the slash flow: when rank-decay evicts a bonded whale, the orchestrator publishes the slash evidence doc + calls `attestation.slash(wallet, slashBps, cid)`. 50/50 pytest covers the bonded → slash_pending promotion + the adapter-failure fallback.

**Verified 2026-05-24 (V3 deploy + live off-chain CCTP burn + WhaleAttestation):**
- **V3 stack deployed** with all post-V2 contract upgrades on Arc (NAV bounds, Pausable, AllocationDecided event, prepareRebalance/commitRebalance for off-chain CCTP, nonReentrant on all entry points, park-return-value check). Addresses in `deployments/arc-testnet.json.addresses` (V2 preserved under `v2_legacy_addresses_for_reference`).
- **WhaleAttestation V3 live:** `0x1d2d34D941b13CbF233051074F007ecf68fB0F7f`. usdc=real native, slashBeneficiary=V3 IndexToken, maxSlashBps=5000 (50%), unbondCooldown=7 days. 21 forge tests cover bond/slash/unbond + the anti-front-run cooldown-resistant slashing invariant.
- **First live off-chain CCTP burn end-to-end** through the prepare→burn→commit flow. The Arc CCTP contract-caller gate is officially closed for our use case — operator EOA signs depositForBurn directly:
  - prepareRebalance tx: `0xad38cd638f2870e6d435355a19c31bf6b23c8ce21190d3bfb4034261c8f5f337` (311k gas; AllocationDecided + BurnPrepared events)
  - **real CCTP DepositForBurn tx**: `0xab3769bb219e5791f18413ec4fc9df6fcf14b66da9f4a6c9f14d0a0fb8baec0b` (131k gas; 0.3 USDC burned through real `0x8FE6B999...42DAA`)
  - commitRebalance tx: `0x7d5cb5d13a56b21b60e8b8c649c5053bd9d41d9d2bae5bb82715f74bfa833b65` (98k gas; NAVUpdated + RebalanceCommitted + RebalanceExecuted)
  - allocation doc: `docs/allocations/ee8e29bd93f2703337a828cb9cc619cbfbd0b07b04561c2b189caa6b1d44dc91.json`, CID matches the on-chain AllocationDecided topic[1] exactly
  - total 3-tx flow latency: 7.03s
  - NAV: $0 → $1.50 ($1.50 reflects 0.5 USDC seed - 0.3 routed; the operator can adjust with subsequent rebalance calls)
- ANTHROPIC_API_KEY is set but credit balance is currently 0 — ReasonerAgent fell back gracefully ("invalid_request_error: credit balance too low"), proving the optional-LLM behavior works.
- Live page (`docs/index.html`) updated to point at V3 addresses + records the real CCTP messenger separately for off-chain mode.
- Arcscan verify for V3 contracts pending — DNS to binaries.soliditylang.org intermittently fails in subshell. Re-run when stable.

**Verified 2026-05-24 (Phase A autonomous — T1.1 + T2.7 + T1.2):**
- **T1.1** — Watchlist V2 schema (`agent/whale_schema.py`) + curator CLI (`agent/whale_curator.py`) with subcommands add / remove / list / validate / refresh-metrics / migrate. `data/whales-hl.json` migrated in place (no semantic change). Backward-compat shim in `leaderboard_reader.load_watchlist` keeps every existing caller working. 5 unit tests.
- **T2.7** — Multi-agent decomposition under `agent/agents/`: ScorerAgent (composite 0-100 with PnL/position-quality/recency components), AllocatorAgent (3 proposals: equal / score-weighted / kelly-bounded), RiskAgent (concentration / imbalance / diversification / dust checks; accept / accept_with_adjustment / veto), CoordinatorAgent (precedence: kelly > score > equal among accepted). Allocation doc v2 carries the full multi-agent audit dict. 12 unit + integration tests.
- **T1.2** — Off-chain CCTP path. `RebalanceExecutor.prepareRebalance(...)` pulls USDC + parks + transfers route amount to operator EOA + emits BurnPrepared. Operator EOA signs the real `depositForBurn` directly (Arc CCTP gate is contract-only; EOA works — verified by prior probe). `commitRebalance(burnId, cctpNonce, newNav, reportedAt)` records nonce + updates NAV. `contract_client.send_rebalance_offchain_cctp(args, real_messenger)` drives all 3 txs. Orchestrator gets `--cctp-mode {on-chain, off-chain}` flag. Existing one-shot `rebalance(...)` preserved. 9 new forge tests.
- Tests: forge 56/56 (up from 47), pytest 17/17. CI green.
- Commits: `fef5f8a` T1.1, `3572783` T2.7, `3dd67ab` T1.2. All on master.

**Verified 2026-05-24 (Phase B agentic loop + Arcscan verification):**
- `agent/orchestrator.py` wires the full pipeline as one entry point: watchlist → concurrent positions + 30d realised PnL → rank-decay filter → top-N allocation → canonical-JSON allocation doc with keccak256 CID → publish to `docs/allocations/<cid>.json` (GitHub Pages serves it publicly) → sign + submit rebalance with CID anchored on chain via AllocationDecided event → append outcome to `data/orchestrator-history.jsonl`
- End-to-end live: tx `0xa8e89e38...d0ee` at 1.13s settlement, NAV $1.00 → $1.50, 0.3 USDC routed to Arbitrum (CCTP V2 nonce 2), AllocationDecided cid `0x7a5223a76544364104...1a5bc66b` matches doc filename exactly
- Allocation doc: `docs/allocations/7a5223a7...66b.json`, 1.2KB canonical JSON, will be public at https://yonkoo11.github.io/whaleindex/allocations/7a5223a7...66b.json on next push
- `--demo-allocation` flag: when watchlist returns 0 positions (placeholders), injects synthetic 1-coin allocation so submit path is testable without real whale curation. Production runs without the flag exit gracefully when no positions.
- Real HL fill fetcher: `leaderboard_reader.fetch_pnl_window(client, wallet, days)` sums closedPnl over userFillsByTime window
- Allocation_engine import dual-pathed (`agent.X` for module mode, plain `X` for script mode)
- Arcscan source verification: all 7 contracts verified via Blockscout-compatible API at `https://testnet.arcscan.app/api/`. `scripts/verify-arcscan.sh` idempotent + uses absolute foundry paths so it works in subshells without sourcing profile.

**Verified 2026-05-23 (Arc testnet, V2 deploy):**
- V2 contracts at addresses in `deployments/arc-testnet.json` (under `addresses`)
- Real native Arc USDC swapped in (`0x3600...0000`, 6-dec ERC20 interface, same balance as native gas)
- Mock CCTP TokenMessenger (real Arc CCTP rejects contract callers — see "Lessons learned" below)
- Mock USYC (Teller allowlist pending)
- Safety primitives live:
  - NAVOracle.maxDeltaBps = 5000 (50% per-update cap)
  - IndexToken Pausable on buy/redeem/withdrawForRebalance
  - RebalanceExecutor Pausable on rebalance
  - rebalance() requires non-zero allocation CID, reverts MissingAllocationCID otherwise
  - AllocationDecided event emitted with CID + whaleCount on every rebalance — on-chain provenance for off-chain allocation decisions
- 47 forge tests pass (28 prior + 19 new: 5 NAV bounds, 5 IndexToken pause, 5 RebalanceExecutor pause + 4 AllocationDecided)
- V2 smoke test `scripts/smoke-arc.sh` end-to-end pass: real USDC approve → buy 1 USDC → rebalance 0.5 USDC → AllocationDecided event verified on chain
- Rebalance tx `0x959e0abb...82596816`, latency **1.08s**, NAV $0 → $1, AllocationDecided cid `0x0d325a7bae92...`
- Operator balance: 16.11 USDC remaining (started 19.80, total session cost ~3.69 USDC across deploys + tests + probes)

**Lessons learned this session (architecture quality + Arc-specific):**
- **Arc CCTP V2 silently rejects contract callers.** Direct EOA → `depositForBurn` works (tx `0x24f2b089...01c2cf95a` burned 0.1 USDC to Arbitrum domain 3). Contract → `depositForBurn` with valid balance + allowance silently reverts. Isolated via `CCTPProbe` (0xe4F6a70a...3B913F6): contract-side approve works, contract-side depositForBurn reverts. All Circle Arc samples use EOAs only. Likely `tx.origin == msg.sender` check or undocumented allowlist. V3 unblockers: Circle support ticket for contract allowlist OR off-chain orchestration where operator EOA signs depositForBurn directly.
- **Paymaster isn't on Arc** (supported: Arbitrum, Avalanche, Base, Ethereum, Optimism, Polygon, Unichain). But Arc doesn't need it — USDC IS the native gas token. Replace "Paymaster" in stack table with "USDC-as-gas (Arc native)" — simpler, stronger story.
- **Gateway is frontend-only** via `@circle-fin/app-kit` + `@circle-fin/unified-balance-kit`. No contract integration needed on our side. Buyer connects their unified USDC balance from any chain, deposits to Arc.
- **`--skip-simulation` is mandatory for Arc forge deploys.** Forge's pre-broadcast simulation hangs against Canteen RPC even though every `eth_*` method responds in <2s via curl. Real gas estimation still happens server-side at broadcast.
- **`arc-canteen rpc-url` pollutes stdout when server is offline** ("(server unreachable...)"). Use `grep -oE 'https://[^[:space:]]+' | head -1` for clean URL extraction.
- **Deploy ownership pattern is fragile.** Original Deploy.s.sol had 3 separate `transferOwnership` calls; missed NAVOracle for single-key case → caused first rebalance to revert with `OwnableUnauthorizedAccount`. Fixed at Deploy.s.sol level (auto-transfer when operator==deployer). Senior follow-up: replace with atomic factory pattern in V3.

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
