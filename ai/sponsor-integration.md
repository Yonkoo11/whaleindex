# Sponsor Integration Depth — WhaleIndex on Arc

**Hackathon:** Agora Agents Hackathon (Canteen × Circle × Arc), 2026-05-11 → 2026-05-25
**Sole sponsor:** Circle / Arc (settlement layer is the entire event)
**Track prizes pursued:** Grand prizes ($10K / $7.5K / $5K) + Standout cohort + Feedback incentive + Easter eggs
**Judges (per page):** backgrounds from Stellar, Coinbase, Arc/Circle, Protocol Labs

---

## Sponsor surface area enumerated (from agora.thecanteenapp.com + developers.circle.com)

| Primitive | Surface |
|---|---|
| Arc L1 | Sub-second deterministic finality, ~$0.01 USDC fees, EVM-compatible, USDC native gas |
| Gateway | Unified USDC balance across chains, sub-500ms cross-chain transfers, Nanopayments down to $0.000001 |
| CCTP | Cross-chain USDC transfers between supported chains, native burn-mint |
| Wallets | Embedded wallets with automated key management for autonomous agents |
| Contracts | Build/manage smart contracts on Arc |
| Paymaster | Transaction fees in USDC (no native gas token for downstream UX) |
| USYC | Tokenized money market fund (yield on idle USDC) |
| USDC / EURC | Settlement currency, also fiat-pegged stablecoins |
| App Kit | Drop-in components: Bridge, Swap, Send, Unified Balance |

---

## Depth audit — WhaleIndex planned integration

| Primitive | V1 plan | Depth | Load-bearing? |
|---|---|---|---|
| Arc L1 | Index ERC-20 NAV contract + rebalance agent identity contract deployed on Arc testnet | 5/5 | YES — entire product runs on Arc |
| USDC | Settlement currency for index NAV, rebalance moves, USYC parking, buyer purchases | 5/5 | YES — remove and nothing settles |
| Gateway | Cross-chain USDC moves on rebalance (HL/Aster/Polynomial venue accounts on supported chains), Unified Balance widget for buyer experience | 5/5 | YES — without Gateway the rebalance can't execute cross-venue |
| USYC | Idle USDC parks in USYC between rebalances; yield on uninvested NAV becomes part of holder return | 4/5 | YES — without it idle NAV bleeds and the value prop collapses |
| Paymaster | Buyer pays USDC-denominated gas when buying index token; no native gas to source | 4/5 | YES — required for retail buyer UX |
| Contracts | ERC-20 index + Rebalance executor + Score reader (oracle pattern) | 4/5 | YES — three contracts coordinate |
| Wallets | Rebalance agent identity with policy: max single move, daily cap, allowed venues | 4/5 | YES — agent custody needs policy guardrails |
| CCTP | Cold-path moves (multi-million USDC) between major chains when daily rebalance > threshold | 3/5 | Optional — Gateway handles most flows but CCTP is the right rail for big moves |
| App Kit (Unified Balance) | Buyer flow component on landing page | 3/5 | Helpful — replaces hand-rolled UI for `/buy` page |

**Overall: 5/5** — multiple primitives load-bearing, every named integration is reachable in V1 build window.

---

## P0 wins (commit for V1, must ship before submission)

| # | Win | Acceptance test |
|---|---|---|
| 1 | Deploy Index ERC-20 on Arc testnet | Token shows on Arc explorer, `totalSupply()` returns >0 |
| 2 | Multi-agent leaderboard reader produces rebalance proposal JSON | Reads HL leaderboard live, outputs top-10 wallet allocation diff |
| 3 | Rebalance executor calls Gateway USDC move | Gateway tx settles in <2s, USDC arrives on target venue, NAV updates on Arc |
| 4 | USYC parking integration | Idle USDC > threshold auto-routes to USYC; yield accrues in NAV calc |
| 5 | Paymaster wired to buyer purchase flow | User without native Arc gas can buy index token via USDC payment |
| 6 | UI shows pre-rebalance NAV, post-rebalance NAV, cost in cents, latency in ms | Screenshot-shareable "rebalanced HL→Aster, $0.03, 600ms" |
| 7 | USDC denominates everything in the UI and contract | No native token surfaced anywhere user-facing |

## P1 wins (V2 stretch, ship if time)

| # | Win | Acceptance test |
|---|---|---|
| 8 | CCTP cold-path large-move routing | When rebalance > $X threshold, route via CCTP instead of Gateway |
| 9 | Wallets SDK for agent custody with policy | Spending caps enforced in-SDK, not just in app code |
| 10 | EURC denomination option for European buyers | `/buy?currency=EURC` flow lands EURC-denominated position |
| 11 | Publish rebalance signal as Polymarket V2 builder feed (Candidate B layer-on) | One pick posted, one fill received, builder fee on Arc |

## P2 (intentional cuts)

- ERC-3643 / transfer-restriction primitives — wrong audience (institutional RWA, not retail copy-traders)
- Multi-currency NAV (basket of stablecoins) — adds attack surface, V2 conversation
- Slash-bonded leaderboard mechanism (research note #06) — needs governance design, V3 conversation

---

## Side-bounty triage

The event has no separate side bounties listed beyond:
- **Feedback Incentives ($500 shared)** — Circle wants developer-experience friction notes. Triage: 4/4 yes. Document every rough edge we hit (Arc CLI install, testnet RPC behavior, Gateway sandbox availability, USYC mint flow on testnet) in `ai/feedback-log.md` and submit at deadline.
- **Easter Eggs ($2K shared)** — Discord puzzles + content creation challenges. Triage: 2/4 yes. Skip unless we find one that fits the live build flow.

---

## Pre-submission verification (Phase 4.5 will re-run this)

Within 48h of 2026-05-25 deadline:
- [ ] Open live demo URL → walk through buyer flow → confirm Paymaster lands USDC tx
- [ ] Trigger one rebalance manually → confirm Gateway settles in <2s, NAV updates, USYC adjusts
- [ ] Inspect contract source on Arc explorer → confirm USDC + Gateway + USYC addresses match Circle's official deployments
- [ ] Confirm GitHub repo public + README with reproduce instructions + LICENSE (MIT or Apache 2.0)
- [ ] Confirm Loom video ≤ 3 min, screen-recorded, no slides masquerading as demo
- [ ] Confirm at least 5 real users hit `/buy` page during the window (Plausible or similar analytics)
- [ ] Confirm feedback log submitted to feedback-incentive channel

If any sponsor depth drops below 4/5 by Phase 4.5, pull a P2 polish task to free time and restore depth before submission.
