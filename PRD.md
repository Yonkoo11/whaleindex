# WhaleIndex — Product Requirements Document

**Version:** 1.0 (post Toly-level review)
**Date:** 2026-05-17
**Hackathon:** Agora Agents Hackathon (Canteen × Circle × Arc), submit by 2026-05-25
**RFB Primary:** RFB 06 — Social Trading Intelligence
**RFB Secondary:** RFB 04 — Adaptive Portfolio Manager
**Repo:** ~/Projects/whaleindex
**Author:** Alex (yonkoo11)

---

## 1. Problem

Retail copy-trading on perpetual futures is broken:

- Followers mirror leaders blindly with no risk model.
- Leader rank degrades silently (skill regression, regime change, MEV losses) and copy-traders find out from a blown account.
- Active copy-trading requires a venue account on every chain where signal lives — HyperEVM, Solana, Arbitrum — each with its own deposit flow, bridge, gas token, KYC posture.
- Capital sits unproductive between rebalance events.

Sub-second deterministic finality + USDC-as-gas on Arc plus CCTP V2's USDC routing to all three target chains makes one thing tractable that wasn't before: **a single USDC-denominated index on Arc that mirrors a Sharpe-weighted basket of top perp traders across HL + Drift + GMX, with idle USDC parked in USYC for yield and a Paymaster-sponsored buy flow so the holder never touches native gas.**

## 2. Product Definition

**Pitch (5 words):** Cross-venue whale index on Arc.

**Tagline (12 words):** One USDC token. Mirrors top perp traders across HL, Drift, GMX.

**Audience:** Retail copy-traders ($100-$10,000 per ticket) who want exposure to "where smart money is right now" without operating accounts on three venues.

**RFB 06 mapping (1:1 against "What AI decides"):**

| RFB 06 ask | WhaleIndex mechanism |
|---|---|
| Which traders to follow based on risk-adjusted returns | 30d rolling Sharpe ratio per whale; top-N selected per venue |
| How much capital to allocate to each trader | Sharpe-weighted within selected set, hard cap 25% per whale |
| When to stop following (degradation) | Rank-decay > 2 places OR 14d Sharpe drop > 40% OR drawdown > 25% → evict, log reason |
| Portfolio construction across signals | 3 venue universes (HL/Drift/GMX), 5-10 whales each, equal-weighted across venues |
| Signal quality filtering | Whitelist of known whales from public sources (Hyperdash, Drift dlob, GMX leaderboard scrape); exclude wash-traders by min-fills threshold |

## 3. Non-Goals

- Not a fund. No custody of user-deposited principal in a way that requires registration.
- Not real-money mainnet at submission. Testnet USDC only.
- Not building a perp DEX on Arc.
- Not a goal-based portfolio manager ("retire in 10 years"). That's RFB 04 example-build territory; WhaleIndex is RFB 06.
- Not a tax-loss harvester. Out of scope V1.

## 4. Architecture

```
   Off-chain agent (Python)
   ├── leaderboard_reader.py       — pulls each whale's clearinghouseState (HL),
   │                                 user account (Drift), positions (GMX) via public APIs
   ├── pnl_calculator.py           — 30d realized PnL + Sharpe per whale
   ├── selection_engine.py         — top-N filter + degradation eviction
   ├── allocation_engine.py        — Sharpe-weighted allocation per venue
   └── rebalance_executor.py       — signs CCTP V2 depositForBurn + Arc IndexToken.rebalance()
                                     and a signed NAV update

   Arc L1 (Canteen testnet, chain 5042002)
   ├── IndexToken.sol              — ERC-20, mint/redeem against USDC, holds NAV state
   ├── RebalanceExecutor.sol       — owner-only, calls CCTPRouter, updates IndexToken
   ├── NAVOracle.sol               — signed-update pattern with 60s freshness, V2: Pyth
   ├── USYCParkVault.sol           — wraps Circle USYC for idle USDC
   ├── CCTPRouter.sol              — wraps Circle TokenMessenger V2 (depositForBurn)
   └── Paymaster integration       — buyer pays USDC for gas, contract ABI handles refund

   Destination chains (CCTP V2 receive side)
   ├── HyperEVM: receive USDC, bridge to HyperCore for HL perp exposure (V2)
   ├── Solana:   receive USDC, deposit Drift, mirror position
   └── Arbitrum: receive USDC, deposit GMX vault, mirror position

   Frontend (Next.js on GitHub Pages)
   ├── App Kit Unified Balance widget (shows USDC across Arc + dest chains)
   ├── Buy / Redeem flow             — Paymaster covers gas
   ├── Holding view                  — NAV chart, last rebalance receipt
   ├── Rebalance history             — eviction log with reasons (RFB 06 transparency)
   └── Distribution analytics        — Plausible on /buy
```

## 5. Sponsor Primitives — every one load-bearing

| Primitive | Where used | Load-bearing? | Phase 1 touch? |
|---|---|---|---|
| Arc L1 (chain 5042002) | All contracts deployed here, all NAV state lives here | YES | YES |
| USDC | Settlement currency, denomination of NAV, gas-via-Paymaster | YES | YES |
| CCTP V2 | Move USDC Arc → HyperEVM / Solana / Arbitrum for venue collateral | YES | YES (one depositForBurn call) |
| USYC | Idle USDC parks in USYC during low-conviction periods (auto-routed when ARC balance > threshold) | YES | YES (mock vault deposit + real V2) |
| Paymaster | Buyer Paymaster sponsorship for `buy()` and `redeem()` calls so holders never source ARC gas | YES | YES (one sponsored tx) |
| Wallets SDK | Rebalance agent identity with on-chain policy (max move, daily cap, allowed venues) | YES | YES (policy struct in storage) |
| App Kit | Unified Balance + Buy widget on frontend | useful, not load-bearing | YES (component import) |
| EURC | EUR-denominated variant (V2 stretch) | NO | NO |

## 6. Phase 1 Gate — binary success test

**Action:** Off-chain agent pulls one HL whale's clearinghouseState via public API → computes intended allocation → calls RebalanceExecutor on Arc testnet → RebalanceExecutor calls CCTP V2 depositForBurn for USDC Arc→Arbitrum → IndexToken NAV updated with signed operator update → UI fetches NAV and displays "intended exposure: $X on HL via Arbitrum, last update Ys ago, cost Zc".

**Success test (binary):** All 5 of the following true:
1. `forge test` for IndexToken, CCTPRouter, NAVOracle, USYCParkVault, RebalanceExecutor passes 100%
2. Contracts deployed to Arc testnet (chain 5042002), addresses recorded in `deployments/arc-testnet.json`
3. CCTPRouter.depositForBurn call lands on Arc testnet with a real `depositForBurn` event matching the planned amount/destination
4. NAVOracle update lands on Arc testnet with signed payload + 60s freshness check holds
5. Frontend reads NAV from chain and displays it

## 7. Engineering Risks (named, with mitigation)

| Risk | Mitigation |
|---|---|
| CCTP V2 contracts not deployed on Arc testnet | Phase 1 deploys a thin CCTPRouter that calls the real Mainnet `TokenMessenger` interface but is mockable; V2 reads addresses from Canteen-published testnet registry once available |
| USYC not on Arc testnet | Phase 1 uses a `MockUSYC.sol` that mints yield-bearing tokens at fixed 5% APY; swap address at deploy time when Circle ships testnet USYC |
| Hyperliquid whale watchlist drifts | Watchlist committed to repo as `data/whales-hl.json` with source URL per entry; weekly cron updates V2 |
| NAV oracle freshness vs Pyth availability | Signed-operator-update with 60s window V1; replace with Pyth EVM pull oracle when available on Arc |
| Paymaster not on Arc testnet | Phase 1 stubs out via a `MockPaymaster.sol` that records sponsored calls; real Paymaster swap at deploy when live |
| Operator key compromise | V1: single-sig with spending policy; V2: 2/3 multisig via Wallets SDK |
| CCTP V2 finality > UX expectation | Marketing copy says "minutes, not blocks"; show real CCTP V2 attestation status in UI |
| Hackathon-window traction unreachable | State realistic 10-20 hackathon-internal users target on the submission form; don't promise mainstream |

## 8. Build Order (per `feedback_hackathon_build_order.md`)

1. **Phase 1 — Core action.** Contracts deployed, one whale read, one CCTP move, NAV updated, UI shows it.
2. **Phase 2 — Data flows.** Real USYC parking, Paymaster wiring, Drift + GMX added, buyer mint/redeem, eviction logging.
3. **Phase 3 — Product complete.** Landing page, README + reproduce instructions, LICENSE, NAV history chart, Plausible analytics.
4. **Phase 4 — Polish.** `/design whaleindex` → `/landing whaleindex` → `/demo-video` → `/submit whaleindex`.

## 9. Sponsor Depth Score Card (target by submission)

| Primitive | V1 target | Acceptance |
|---|---|---|
| Arc L1 | 5/5 | All NAV state on Arc, deployment proof on Arcscan |
| USDC | 5/5 | All accounting in USDC, no native ARC surfaced to user |
| CCTP V2 | 5/5 | Real depositForBurn calls land for at least 1 destination chain |
| USYC | 4/5 | Idle USDC > threshold auto-parks; yield accrues to NAV |
| Paymaster | 4/5 | Buy / redeem sponsored; user without ARC gas completes flow |
| Wallets SDK | 4/5 | Agent identity has on-chain policy struct, enforced at executor entrypoint |
| Contracts | 5/5 | 6 contracts coordinated (Index + Executor + Router + Oracle + Park + Paymaster shim) |
| App Kit | 3/5 | Unified Balance + Buy widget on landing page |

Total target: ≥35/40 (8 categories × 5).

## 10. Traction Plan (real, with named channels)

- Day 1 (deploy): tweet thread with deployment proof + screenshot of one rebalance.
- Day 2: post in Canteen Discord and Arc builder Discord with link.
- Day 4: outreach to 3 named HL whale Twitter accounts asking for opt-in attestation of the watchlist.
- Day 7: r/HyperliquidCT post + 2 perp-focused Discord servers.
- Day 9: tweet at @MertMumtaz and 2 perp content accounts.
- Day 12: feedback log submitted to Feedback Incentives bucket.

Target by submission: 10-20 unique testnet buyers, 2 published whale opt-ins, 3 published rebalances with eviction log shown.

## 11. Submission Deliverables Checklist

- [ ] Public GitHub repo with LICENSE (MIT), README with reproduce-this instructions, CONTRIBUTING.md
- [ ] Live demo URL on GitHub Pages
- [ ] Loom video ≤ 3 min: problem → solution → live demo → team
- [ ] Submission form filled at https://forms.gle/hFPM2t4Jt1zGfqzM7
- [ ] Traction report: count of unique buyers, rebalances executed, eviction events, Plausible analytics
- [ ] Feedback log filed for Feedback Incentives bucket
- [ ] Phase 4.5 sponsor-depth re-audit run within 48h of deadline
- [ ] Phase 4.7 communication-pack checklist green

## 12. Out of Scope (so judges can't accuse scope-creep)

- EURC denomination
- Goal-based portfolio interfaces (that's RFB 04 territory, not RFB 06)
- Tax-loss harvesting (RFB 04 again)
- Multisig agent identity (V2)
- Pyth oracle integration (V2)
- HL → HyperCore inner bridge for real perp opening (V2; V1 demonstrates exposure intent + CCTP V2 hop)
- Statistical degradation tests (V1 uses simple rank-decay; V2 adds Sharpe t-stat threshold)

---

## Appendix A — Verified facts

| Claim | Source | Verified |
|---|---|---|
| Arc testnet chain ID 5042002 | arc-node.thecanteenapp.com | 2026-05-17 |
| CCTP V2 supports HyperEVM, Arc, Solana, Arbitrum | Circle CCTP docs | 2026-05-17 |
| CCTP V2 does NOT support BNB Chain | Circle CCTP docs | 2026-05-17 |
| Hyperliquid `clearinghouseState` returns positions for any wallet, public, no auth | Hyperliquid GitBook | 2026-05-17 |
| Drift exposes positions via `dlob.drift.trade` and EventSubscriber, no native leaderboard | Drift v2-teacher docs | 2026-05-17 |

## Appendix B — Watchlist source URLs (V1)

- Hyperliquid: top traders curated from hyperdash.info/leaderboard (public)
- Drift: top makers from `https://dlob.drift.trade/topMakers`
- GMX: top traders curated from gmx.house leaderboard (public)
- Watchlist file committed at `data/whales-hl.json`, `data/whales-drift.json`, `data/whales-gmx.json` with source + last-verified date per entry.
