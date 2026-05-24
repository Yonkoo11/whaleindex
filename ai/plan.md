# WhaleIndex V1 — Senior Build Plan

**Authored:** 2026-05-23
**Constraint:** time-unconstrained, build to a senior Arc developer's quality bar
**Supersedes:** the 10-hour priority list at the bottom of the prior critique

---

## 0. Honest current state (verified 2026-05-23)

What works:
- 8 contracts deployed on Arc testnet (chain 5042002). Bytecode verified. Ownership wired.
- One signed rebalance settled in 0.78s on Arc. Tx `0x7dc114…c97cd69`.
- 28 forge tests pass.
- Local anvil end-to-end smoke test green.

What does not work:
- The live URL is broken for any non-developer (empty Arc config at `docs/index.html:98`).
- All Circle integrations are mocked (USDC, USYC, TokenMessenger). Sponsor depth currently scores ~0/5 for the rubric's "Circle tool usage" criterion.
- `agent/main.py` prints a JSON plan; it does not sign or submit. The "agentic" loop is three disconnected scripts (`leaderboard_reader`, `selection_engine`, `allocation_engine`, `contract_client`).
- `selection_engine` operates on hardcoded synthetic PnL scores (`selection_engine.py:183-185`). The real fill-fetcher does not exist.
- Whale watchlist is three placeholder addresses (`data/whales-hl.json`).
- No Gateway integration. No Paymaster. No App Kit. No Unified Balance widget.
- No NAV bounds check, no pause, no agent-identity separate from deployer.
- Frontend is one static HTML file, not the Next.js + App Kit stack claimed in the README.
- Documentation rot: `CLAUDE.md` says Aster, `README.md` says GMX/Drift, `memory.md` says HL-only. Pick one.

The 0.78s settlement is real, but it proves mock infrastructure executes on Arc, not that the product is what the README claims it is.

---

## 1. End state — what V1 of WhaleIndex should be

**The product:** A USDC-denominated index token on Arc that mirrors a curated basket of Hyperliquid whale wallets. Idle USDC parks in USYC for yield. Buyers acquire shares via a Paymaster-sponsored flow — no native gas needed. An off-chain agent decides allocations and signs rebalance calls; on-chain provenance ties every rebalance to a content-hashed allocation decision.

**The Arc differentiators the product visibly demonstrates:**
1. USDC-as-gas — buyer never touches native token
2. Sub-second deterministic finality — rebalances are visible to the holder before they can blink
3. Stable per-tx cost (~$0.001) — the index can rebalance frequently without yield drag

**Sponsor depth targets the V1 hits:**
| Primitive | Current | V1 target | Mechanism |
|---|---|---|---|
| Arc L1 | 5/5 | 5/5 | all contracts on Arc, no other chain for state |
| USDC | 0/5 | 5/5 | native USDC `0x3600…0000` everywhere |
| Gateway | 0/5 | 4/5 | GatewayWallet for buyer unified balance, GatewayMinter for cross-chain receive |
| CCTP V2 | partial | 4/5 | real TokenMessengerV2 for outbound burn-and-mint |
| USYC | 0/5 | 4/5 | Teller mint/redeem, allowlist requested |
| Paymaster | 0/5 | 4/5 | sponsored `buy()` and `redeem()` via Circle Paymaster |
| Contracts | 3/5 | 4/5 | three coordinated contracts + factory + audit prep |
| Wallets | 2/5 | 4/5 | separate operator identity, policy-bounded |

---

## 2. Architectural decisions (with rationale)

### 2.1 Atomic deploy factory

**Decision:** Replace `Deploy.s.sol`'s "deploy then transfer ownership" pattern with a single `WhaleIndexFactory` that wires every contract atomically.

**Rationale:** Today's deploy missed `NAVOracle.transferOwnership`. The pattern itself is the bug — every Ownable contract is one transfer away from misconfiguration. A factory makes the deploy atomic: either all contracts are wired correctly or the deploy reverts.

**Acceptance:** Deploy.s.sol becomes ~30 lines, calls `factory.deploy(...)`, returns the 8 addresses in one tx. No post-deploy ownership transfers anywhere.

### 2.2 NAV bounds (oracle safety)

**Decision:** Add a per-rebalance NAV-delta bound to `NAVOracle.updateNAV`. Reject any update where `|newNav - nav| / nav > MAX_DELTA_BPS` (initial 500 bps = 5%) or where `newNav` exceeds an absolute MAX_NAV ceiling.

**Rationale:** `NAVOracle.sol:25` accepts any uint256 today. A bug or compromise in the agent could mint shares at 10^24x prices, draining holders. Bounds are standard oracle hygiene.

**Acceptance:** Forge fuzz test that asserts no `updateNAV` succeeds outside the bounds.

### 2.3 Pausable

**Decision:** OpenZeppelin `Pausable` on IndexToken (buy/redeem) and RebalanceExecutor (rebalance). Owner-only `pause()` and `unpause()`.

**Rationale:** If the agent goes wrong, the only current stop is `transferOwnership` — slow and irreversible. Pause is the standard kill-switch.

**Acceptance:** Forge test: paused → all entry points revert; unpaused → resume.

### 2.4 On-chain allocation provenance

**Decision:** Add `event AllocationDecided(bytes32 indexed cid, address[] whales, uint256[] weightsBps, uint64 reportedAt)` to RebalanceExecutor. Require the agent to submit a 32-byte content hash (`cid`) committing to the off-chain allocation document. Hash anchors to IPFS / a public gist, judges can verify the agent's reasoning.

**Rationale:** Today, on-chain artifacts are `Routed(amount, domain)` and `NAVUpdated(nav)`. Neither says *why*. For the 30% agentic judging criterion, the provenance gap is fatal. CID provenance also gives traction storytelling: "this rebalance was driven by these 8 whales' Sharpe ratios."

**Acceptance:** Every rebalance() emits AllocationDecided with the CID submitted by the agent. Frontend resolves the CID to a readable doc.

### 2.5 Operator identity ≠ deployer

**Decision:** Two-wallet model. Deployer holds the upgrade key (currently unused; reserved for emergency). Operator is a separate wallet that signs rebalances. Policy bounds (`maxSingleMove`, `dailyCap`) enforce the operator's reach.

**Rationale:** Memory.md targets "agent identity with policy: max move, daily cap, allowed venues" at 4/5. Today operator == deployer == single key. Splitting them is one redeploy + key generation.

**Acceptance:** Operator key generated, never co-located with deployer key. Deployer can only `pause()` and `transferOwnership`; cannot rebalance.

### 2.6 Real Gateway integration (buyer side)

**Decision:** Buyer's `buy()` flow accepts deposits through `GatewayWallet` (`0x0077777…19B9`). Buyer's USDC across chains shows as one unified balance in the App Kit widget; depositing into the index draws from that balance.

**Rationale:** Gateway's unified-balance UX is Arc's headline buyer experience. The flow eliminates "bridge first, then buy" friction. Hitting 4/5 Gateway depth requires this — a non-Gateway buy() is just an ERC20 transfer.

**Acceptance:** `/buy` page shows App Kit's Unified Balance widget. Buyer with USDC on any supported chain can mint WHALE shares in one click. Frontend uses `GatewayMinter` for cross-chain receive if buyer's source chain is not Arc.

### 2.7 Real CCTP V2 (rebalance side)

**Decision:** Swap `MockTokenMessengerV2` for real `TokenMessengerV2` (`0x8FE6B999…42DAA`). `min_finality_threshold` becomes a function of destination domain (currently hardcoded 0 in smoke test).

**Rationale:** CCTP is what actually moves USDC cross-chain during a rebalance. Mock = no burn = no real Circle integration evidence.

**Acceptance:** Rebalance tx emits a real `DepositForBurn` event on Arc. Off-chain attestation verifies the message hash via Circle's IRIS API. Destination-chain mint script lands USDC on Arbitrum testnet (verified by a follow-up Etherscan tx).

### 2.8 Real USYC integration (yield)

**Decision:** USYCParkVault wraps the real USYC Teller (`0x9fdF…105A`) instead of the mock. Park = `teller.mint(usdc)`. Unpark = `teller.redeem(usyc)`.

**Rationale:** Idle USDC sitting in the index pays no yield. USYC pays a treasury-backed yield. This is the "yield on idle" promise. Mock USYC = no yield = no story for "performance vs raw leader average" (the RFB 06 traction metric).

**Acceptance:** Park tx mints real USYC. Unpark redeems back to USDC. Allowlist request submitted via the USYC portal; if pending, document the gate and fall back to mock with an honest banner.

### 2.9 Real Paymaster (buyer gas)

**Decision:** Integrate Circle Paymaster so `buy()` and `redeem()` are sponsored — buyer pays USDC for shares, no native gas required. The Paymaster verifies a permit signature and pays gas in USDC on the buyer's behalf.

**Rationale:** Arc's premise is "USDC-as-gas." Without Paymaster, the buyer still needs USDC as gas explicitly — friction that breaks the pitch.

**Acceptance:** /buy page completes a buy with the buyer holding only USDC (no native gas in wallet). Plausible analytics tracks completion rate.

### 2.10 Frontend: Next.js + App Kit

**Decision:** Migrate from `docs/index.html` (single static file) to a Next.js app with App Kit components. Pages: `/` (live NAV + last rebalance + Arc-vs-others comparison), `/buy` (Unified Balance widget + buy flow), `/history` (rebalance event timeline), `/whales` (current basket + each whale's recent PnL).

**Rationale:** Stack table in README and CLAUDE.md claim Next.js + App Kit. The actual frontend is one static HTML file. The gap is visible to any judge who clicks "view source." Migrating is also the path to the buyer flow (Unified Balance + Paymaster need React-side SDKs).

**Acceptance:** All four pages render. Live URL points to the Next.js build (still GitHub Pages, exported static). Mobile responsive (tested at 375×667).

### 2.11 Real agentic loop

**Decision:** One orchestrator (`agent/orchestrator.py`) that runs:
```
fetch_positions(whales) → fetch_pnl_window(whales, 30d) → rank → decay_filter →
   compute_allocations(survivors) → sign_attestation(EIP-712, cid) →
   pin_to_ipfs(allocation_doc) → send_rebalance(cid, args) → log_outcome
```

Cadence: every 24h, configurable. Triggered by macOS launchd in development, by a $5/month VM in production.

Real fill-fetcher: `leaderboard_reader.fetch_pnl_window(wallet, window_days)` against Hyperliquid `userFillsByTime`. Real PnL feeds `selection_engine`, replacing the synthetic scores at `selection_engine.py:183-185`.

**Rationale:** Today the four agent modules don't talk to each other. The orchestrator is the agentic story.

**Acceptance:** One command (`python -m agent.orchestrator --network arc-testnet`) reads HL data → produces a rebalance → submits a signed tx → emits provenance on chain. Cron job runs daily.

### 2.12 Curated whale watchlist

**Decision:** Replace 3 placeholders with 10-15 curated wallets sourced from Hyperdash leaderboard top-30 by 30-day Sharpe. Manual curation (Hyperdash blocks WebFetch). Each wallet annotated with source URL + last-verified date + notes.

**Rationale:** Three placeholders is a credibility tell. Ten real wallets is a product.

**Acceptance:** `data/whales-hl.json` has ≥10 real wallets. Annotated. Visible on `/whales` page.

### 2.13 Static analysis pass

**Decision:** Run Slither + Aderyn + Halmos before claiming the contracts are review-ready. Document findings, fix or accept with rationale.

**Rationale:** The product is custody-adjacent. Even a hackathon submission benefits from a clean static-analysis bill.

**Acceptance:** `ai/audit/` directory with Slither + Aderyn output. All medium/high findings either fixed or explicitly accepted in writing.

### 2.14 Arcscan verification

**Decision:** All deployed contracts verified on `testnet.arcscan.app`. Source uploaded, compiler version + optimizer settings declared, ABI public.

**Rationale:** Trust signal. Judges look at Arcscan. "Unverified contract" is a red flag.

**Acceptance:** All 8 contracts show verified-source badges on Arcscan.

### 2.15 Documentation reconciliation

**Decision:** Single source of truth: `ai/memory.md` for current state, `README.md` for what works today, `PRD.md` for the V1 design. `CLAUDE.md` is operating instructions only — no architecture or scope claims.

**Rationale:** Three files disagree on the venue list. Pick one truth.

**Acceptance:** Grep for "Aster" returns only `README.md:55` (the deliberate kill rationale). All "HL + Aster" references in `CLAUDE.md` updated to "HL with Drift/GMX planned for V2."

---

## 3. Build sequence (dependency-ordered)

Each step has its own acceptance test. No step is "done" until the test passes against live Arc testnet (or, for off-chain steps, against the real data source).

### Phase A — foundations (real contracts)

1. **Write `WhaleIndexFactory.sol`** — atomic deploy. Tests: factory.deploy reverts on partial wiring, returns 8 addresses on success, ownership correct.
2. **Add Pausable + NAV bounds + AllocationDecided event** to existing contracts. Tests: bounds rejection (fuzz), pause/unpause, event emission.
3. **Generate operator key.** Separate from deployer. Stored in `~/.zshenv` as `OPERATOR_PRIVATE_KEY`. Deployer constructs factory; operator owns the executor's policy.
4. **Redeploy via factory against Arc.** Real Circle addresses: USDC `0x3600…0000`, TokenMessengerV2 `0x8FE6B999…42DAA`. USYC still mock pending Teller allowlist. Verify on Arcscan.
5. **Update `deployments/arc-testnet.json`** with V1 addresses.
6. **Forge test suite expanded** to cover the new bounds, pause, event. Invariant test: NAV never moves > MAX_DELTA_BPS in one block.

### Phase B — agentic loop (real data)

7. **Build `leaderboard_reader.fetch_pnl_window()`** against HL `userFillsByTime`. Returns 30-day realised PnL per wallet.
8. **Curate `data/whales-hl.json`** to 10-15 real wallets. Manual; pull from Hyperdash; annotate.
9. **Build `agent/orchestrator.py`** running the full pipeline. Add EIP-712 attestation signing for the CID.
10. **Pin allocation docs to IPFS** (web3.storage, free tier). CID surfaces in AllocationDecided event.
11. **launchd cron** in `~/Library/LaunchAgents` for daily run. Idempotent against the same allocation snapshot.

### Phase C — buyer flow (Gateway + Paymaster + App Kit)

12. **Scaffold Next.js app** under `frontend/`. Static export target (GitHub Pages compatible).
13. **Wire App Kit `<UnifiedBalance>`** on `/buy`. Buyer's USDC across chains shows as one balance.
14. **Build `/buy` flow** — buyer signs permit, Paymaster pays gas, contract mints WHALE shares.
15. **Build `/redeem` flow** — symmetric.
16. **Build `/history`** — paginated rebalance timeline, each row links to Arcscan + IPFS allocation doc.
17. **Build `/whales`** — current basket, per-whale 30d PnL, last-evicted timeline.

### Phase D — product polish (per build-order rule: only after Phase C done)

18. **Headline component on `/`** — "Tracking N whales. Last rebalance T mins ago at $C, settled in Lms. NAV $X."
19. **Arc-vs-others comparison card** — show the same rebalance would cost Y on Ethereum L1 / Z on Arbitrum L2.
20. **Mobile responsive QA** — test at 375x667 (iPhone SE).
21. **Trust signals** — Arcscan badges, GitHub link, last-deploy date, contract addresses with copy buttons.

### Phase E — audit prep

22. **Slither** scan → fix or document findings.
23. **Aderyn** scan → fix or document.
24. **Halmos** symbolic — prove `nav` cannot exceed MAX_NAV.
25. **Verify contracts on Arcscan.** All 8 (or however many V1 has) sources uploaded.
26. **`SECURITY.md`** updated with reporting channel, scope, severity tiers.
27. **`ai/audit/`** captures all tool outputs + decisions.

### Phase F — submission

28. **Reconcile docs** (CLAUDE.md ↔ README.md ↔ memory.md ↔ PRD.md). Single source.
29. **README rewrite** — what works today, what doesn't, how to reproduce, screenshots from live URL.
30. **Demo video** — 90 seconds, narrated screen capture against the live URL.
31. **Submission form** filled. Traction report filled.

---

## 4. Risks and how to handle them

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| USYC Teller allowlist denied or slow | medium | medium | Fall back to MockUSYC for V1 demo. Honest banner. Resubmit allowlist for V2. |
| Arc testnet RPC instability (saw "server unreachable" today) | medium | low | Retry logic in orchestrator. Cache last successful response. |
| HL endpoint rate-limit / shape change | medium | medium | Local cache of position snapshots. Document exact endpoint version. |
| Paymaster on Arc testnet not yet operational | unknown | medium | Verify endpoint live before depending on it. Document gap if not. |
| App Kit / Unified Balance widget docs incomplete | medium | low | Read context-arc samples directory first; copy from working sample. |
| GitHub Pages doesn't support some Next.js features needed for App Kit | low | medium | Static export with `next export`. Verify before scaffolding. |

---

## 5. Acceptance test for V1 (the "is it done" check)

A judge, never having seen the repo, can:

1. Open the live URL on their phone (no MetaMask plugin required for read).
2. Within 5 seconds, understand: this is a USDC index that mirrors whale wallets, currently NAV $X, last rebalanced T mins ago.
3. See "0.4s settlement on Arc — would be 12s and $4 on Ethereum L1" comparison.
4. Open `/whales`, see 10+ real wallets with PnL, click into any → Hyperdash profile.
5. Open `/buy`, connect a wallet with only USDC (no native gas), buy $10 of shares, watch the share count update — all without seeing a "switch network" or "approve gas" dialog. (Paymaster + Unified Balance + USDC-as-gas, all three Arc differentiators delivered in one flow.)
6. Open `/history`, click any rebalance → see the IPFS doc with the agent's reasoning, click the tx hash → see it on Arcscan, see the AllocationDecided event with the matching CID.
7. Open the GitHub repo, run two commands, get the same product running locally.

If all seven check, V1 ships.

---

## 6. Anti-scope (V2, not V1)

- Aster / Drift / GMX (multi-venue) — V2. README's "HL + Drift + GMX" claim is aspirational.
- Owner-attested whale opt-in / slash-bond — V2.
- Risk-adjusted Sharpe ranking (currently raw PnL) — V2.
- Tax-loss harvesting — V2.
- Goal-based interfaces — V2.
- Mainnet — V2.

---

## 7. Hours estimate (informational, not a constraint)

| Phase | Hours |
|---|---|
| A — foundations | 12-16 |
| B — agentic loop | 10-14 |
| C — buyer flow | 16-24 |
| D — product polish | 6-10 |
| E — audit prep | 6-10 |
| F — submission | 4-6 |
| **Total** | **54-80 hours** |

User said ignore time. Estimating only so the build can be sequenced into sittable sessions.
