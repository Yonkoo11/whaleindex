## Design Research Brief

> Competitive design research for WhaleIndex — a dark-mode, USDC-denominated DeFi index token on Arc testnet that mirrors top Hyperliquid whale perp positions, with on-chain provenance (every rebalance decision published as hashed, chain-anchored JSON reasoning). This brief drives 3 design proposals. Date: 2026-05-25.

### Product Category
On-chain financial instrument with a **read-heavy "audit the machine" surface**. WhaleIndex sits at the intersection of three product genres:
1. **Crypto analytics dashboard** (Hyperdash, Dune) — live numbers, position tables, NAV.
2. **Block-explorer / provenance UX** (Etherscan) — verify a hash, trust a claim, inspect the chain.
3. **Fintech trust + buyer flow** (Stripe) — move real money with calm confidence.

The honest framing: this is **not** a trading terminal (no order book, no leverage knobs). It is a *proof-of-reasoning ledger with a buy button*. The design job is to make an autonomous agent's decisions feel auditable and trustworthy, not to make a casino feel exciting. Linear is the craft north-star for how a dense, serious tool can feel calm.

### Comparables Studied
1. **Hyperdash** (crypto, direct competitor) — Hyperliquid whale-tracking terminal.
2. **Dune Analytics** (crypto, data density) — community on-chain dashboards.
3. **Etherscan** (block explorer, **provenance core story**) — contract verification + tx inspection.
4. **Linear** (NON-crypto, dashboard craft north-star) — project tracker, best-in-class dark UI.
5. **Stripe Dashboard** (fintech trust + financial number rendering) — payments operator console.

---

### Per-comparable findings

#### 1. Hyperdash — the direct competitor (study to differ, not to copy)
- **Layout:** Dense multi-panel terminal. Left rail = navigation/asset filter; center = the live data object (whale leaderboard, position table, long/short ratio); persistent top strip of summary stats (total whale positioning, 24h net change). New "Enhanced Whale Tracking" view (Mar 2026) lets users filter net long/short change per asset (ETH/SOL/HYPE) over a 24h window — i.e. *time-windowed deltas* are the headline unit.
- **Color:** Near-black base (not pure #000), single green/teal accent for positive/long, red for short. Color is *semantic* (direction of position), not decorative.
- **Typography:** Mono for all numbers, tight tracking, heavy reliance on tabular alignment in tables.
- **Signature interaction:** Real-time auto-updating rows with directional color flash on change; click a whale → drill into that wallet's positions.
- **Hierarchy:** Number-first. The position size and PnL are the largest elements; labels are demoted to small uppercase gray.
- **Empty/loading states:** Skeleton rows in the table shape (terminal expectation: keep the grid, fill the cells).
- **STEAL THIS:** The **24h net-delta strip** — a horizontal row of "net change" pills above the main table. For WhaleIndex this becomes the *rebalance delta strip*: "Since last rebalance: +2 positions, −1, NAV +1.3%". Render deltas in mono with a leading +/− and color, `font-variant-numeric: tabular-nums`, value 600 weight, label 12px uppercase `letter-spacing: 0.04em` gray.

#### 2. Dune Analytics — data density done as a grid of widgets
- **Layout:** Free-form **widget grid** — resizable tiles, each tile is one visualization (counter, time-series, table) or a markdown text block. Dashboards mix prose and data in the same canvas. This is the model for "explain a number next to the number."
- **Color:** Dark gray canvas (explicitly *not* #000), restrained palette, one categorical color ramp for series. Chart ink is the only saturated color; chrome stays neutral.
- **Typography:** Sans for labels/prose, mono leanings for query/result cells. Big counter numbers are the visual anchors of a dashboard.
- **Signature interaction:** The **counter widget** — a single huge number with a tiny label, used as a KPI headline. And inline markdown text widgets that annotate why a chart matters.
- **Hierarchy:** Counters at top (the answer), charts in the middle (the trend), raw query table at the bottom (the proof). This "answer → trend → proof" descent is exactly WhaleIndex's NAV → reasoning → on-chain hash flow.
- **Empty/loading states:** Per-widget spinners; a widget can load independently so the dashboard renders progressively rather than blocking on the slowest query.
- **STEAL THIS:** **Independent per-widget loading.** Each dashboard card (NAV, latest rebalance, reasoning trace, attestation, chain-cost compare, contracts) fetches and resolves on its own. Never block the whole dashboard on the slowest call (the chain-anchor read will be slowest). Card-level skeleton → content with a 150ms ease-out cross-fade.

#### 3. Etherscan — provenance UX, our core story
- **Layout:** Header summary block (the entity: address/tx/contract + at-a-glance facts) → **tabbed detail** (Overview / Internal Txns / **Contract** / Events / Analytics). The Contract tab splits into **Code / Read Contract / Write Contract** sub-tabs. Information cascades from "what is this" → "prove it" → "interact."
- **Color:** Light by default, but the *verification semantics* are what matter: a **green check badge** = exact-match verified source; a **yellow/amber badge** = similar-match (partial trust); no badge = unverified bytecode only. The badge color *is* the trust level. Verified state unlocks the Read/Write tabs (verification literally gates capability, a powerful trust signal).
- **Typography:** Mono for all hashes, addresses, hex; sans for labels. Hashes are truncated middle (`0x1f4e…a9c2`) with a click-to-copy affordance.
- **Signature interaction:** **Click-to-copy on every hash/address** with a transient "Copied" confirmation; one-click jump from a hash to its detail page. Provenance is navigable, not just displayed.
- **Hierarchy:** Status first (success/fail, verified/not), then the immutable identifiers (hash, block, timestamp), then the decoded human-readable payload, then raw input data last (collapsed).
- **Empty/loading states:** "Awaiting confirmation" pending state for unconfirmed txns; gray placeholder for not-yet-indexed data. Honest about chain latency rather than faking instant.
- **STEAL THIS:** The **green-check verification badge + reveal pattern**. WhaleIndex's reasoning JSON should carry a green check that means "hash on this page === hash anchored on-chain at block N." Make it a real recomputed check, not a static asset. Badge: `#00d4aa` check glyph, `font-size: 13px`, with a hover tooltip showing `sha256(reasoning.json) === 0x… (block 1,284,019)`. The check is the whole product in one glyph.

#### 4. Linear — the craft north-star (non-crypto)
- **Layout:** Persistent left sidebar (workspace nav), main content as a calm single-column-with-detail-panel. No card-grid clutter; uses **rows + a slide-in right detail panel** instead of modals. Generous but consistent spacing (~8px base unit, multiples: 4/8/12/16/24/32).
- **Color:** **LCH color space** for theme generation — perceptually uniform, so accent and neutrals stay balanced across the dark canvas. Deep charcoal base (not black), *muted* text colors (the secondary text is genuinely low-contrast on purpose), and deliberately minimal "chrome" (they reduced how much blue tint appears in UI surfaces for a neutral, timeless feel). Borders are near-invisible: ~`rgba(255,255,255,0.06–0.09)` hairlines, not boxes.
- **Typography:** **Inter Display for headings** (more expressive), **Inter for body**, with tight negative tracking — `-0.022em` (≈ -0.22px display, -0.11px body). The negative letter-spacing is what makes it feel precise and engineered.
- **Signature interaction:** **Command-K palette** (keyboard-first), instant optimistic UI (actions apply immediately, sync in background), and buttery 150–200ms ease-out micro-transitions on hover/focus/panel-slide. Nothing ever janks or blocks.
- **Hierarchy:** Achieved through *weight and color, not size* — most text is one of two sizes, differentiated by 500 vs 400 weight and full-vs-muted color. Restraint creates the calm.
- **Empty/loading states:** Purposeful empty states with a single clear next action and a quiet illustration/icon; skeletons match final layout exactly so there's zero layout shift.
- **STEAL THIS:** **Hairline borders + weight-based hierarchy + negative tracking.** Replace boxy cards with `1px solid rgba(255,255,255,0.07)` dividers and `letter-spacing: -0.011em` on body, `-0.022em` on headings (DM Sans tolerates this well). Differentiate by weight (400 muted / 600 full-contrast), not font size. This is how WhaleIndex avoids the "identical card grid" anti-pattern while staying dense.

#### 5. Stripe Dashboard — fintech trust + financial number rendering
- **Layout:** KPI cards top (stacked metric cards: gross volume, successful payments, new customers), each with a contextual **sparkline** trend; below them sortable/searchable transaction tables; clicking any row opens a **right side panel** with full detail (not a route change, not a modal). Same panel pattern as Linear.
- **Color:** Light-default, restrained. Trust comes from **consistency and whitespace**, not color. Trend badges are small and semantic (green up / red down). They use exactly **6 type sizes/weights** total across the whole dashboard — extreme typographic discipline.
- **Typography:** Tabular numerals everywhere financial; currency amounts get a slightly de-emphasized symbol and decimal, emphasized integer part. Numbers right-align in tables.
- **Signature interaction:** **Sparklines next to KPIs** (tiny inline trend, no axes) and the slide-in transaction detail panel. Inline field validation on the checkout side fires on blur (not on every keystroke) to avoid nagging; success confirmation is a calm checkmark, not confetti.
- **Hierarchy:** Money first and biggest, trend second (small badge + sparkline), metadata (date, id, method) demoted to muted mono. "When the revenue section feels right, the rest of the dashboard becomes easier to trust."
- **Empty/loading states:** Skeleton KPI cards and skeleton table rows; zero-state for a new account shows the metric at $0.00 with the structure intact (never a blank screen) — honest, structured emptiness.
- **STEAL THIS:** **KPI card with inline sparkline + de-emphasized currency formatting.** NAV card: `$1.0432` where the `$` and trailing decimals are `opacity: 0.6` and the integer is full-contrast 600 weight, mono, tabular-nums; a 40px-tall axis-less sparkline of NAV-since-inception sits to the right. Trend pill: `+1.3%` in `#00d4aa` at 12px. Validate buy-amount input **on blur**, not per keystroke.

---

### Common Patterns (table stakes — must include)
1. **Near-black, never pure-black base.** Every serious dark dashboard uses deep charcoal (≈ `#0a0c0d`–`#101314`), not `#000`. Pure black causes halation on OLED and kills depth.
2. **Tabular mono for all financial numbers.** Non-negotiable; already in our constraints (JetBrains Mono, `font-variant-numeric: tabular-nums`). Numbers right-align in tables.
3. **Single semantic accent + green/red for direction.** One brand accent for interactive/positive; red reserved strictly for loss/short/error. No third decorative color.
4. **Summary strip on top, detail below.** Answer → trend → proof descent (Dune/Stripe/Etherscan all do it).
5. **Right slide-in detail panel, not modals** (Linear + Stripe). For drilling into a rebalance or a whale.
6. **Layout-matched skeletons, per-widget loading** (Dune + Stripe). No spinners-on-blank; no layout shift.
7. **Click-to-copy hashes/addresses, truncated middle** with transient "Copied" toast (Etherscan).
8. **150–200ms ease-out transitions** on hover/focus/panel — already our constraint, and it's universal among the craft leaders.

### Differentiation Opportunities (where WhaleIndex can stand out)
None of the trading comparables (Hyperdash, Dune, even Etherscan) make **"audit the agent's reasoning"** a first-class, designed surface. This is the white space.
1. **The Reasoning Trace as the hero, not a footnote.** Hyperdash shows *what* whales did. WhaleIndex shows *why our agent did what it did* — including **deciding NOT to trade**. Design a dedicated "Decision Record" component: a timestamped JSON reasoning doc rendered human-readably (Scorer → Allocator → Risk → Coordinator as a 4-step pipeline), each step collapsible, with the raw JSON one click away and its hash anchored on-chain. A "no-trade" decision should look just as substantial as a trade — that's the trust differentiator.
2. **Recompute-the-hash-in-the-browser provenance.** Go beyond Etherscan's static green badge: actually `sha256` the displayed reasoning JSON client-side and assert it equals the on-chain anchored hash, showing the live match. "Don't trust us, your browser just checked." No comparable does live client-side verification as a UX moment.
3. **Multi-agent pipeline visualization.** The Scorer→Allocator→Risk→Coordinator chain is unique. Render it as a horizontal **provenance pipeline** (4 nodes, connecting hairlines, each node showing its input/output and confidence), echoing a call-graph but for decisions. This is a signature visual nobody in DeFi has.
4. **Crimson Pro for trust/authority moments.** The serif is a differentiator in a category that is 100% sans/mono. Use it surgically: the landing hero thesis statement, section headers on the "how provenance works" explainer, and the attestation/bonded-whale statement. Serif = "we stand behind this claim." Never use it for data.
5. **Chain cost/latency comparison as a confidence flex.** Arc testnet cost/latency vs alternatives is a real, ownable data viz — a small honest bar/row compare that says "this is why we anchor here." Nobody else surfaces their infra economics as a trust signal.
6. **The "no-trade" empty-ish state is a feature.** When the agent decides not to rebalance, that's not an empty state — it's a *positive* signal of discipline. Design it to feel intentional and reassuring, not like missing data.

### Design Constraints (data density, real-time, mobile)
- **Data density:** High but read-only. No order entry. Favor Linear-style weight/color hierarchy over Hyperdash terminal-cramming. Whitespace is allowed because we're not packing a trading screen.
- **Real-time updates:** NAV and latest-rebalance are the live elements. Use directional color-flash on change (Hyperdash) but **subtle** — a 200ms ease-out background tint fade, not a flash. Anchor/verification reads are slow (chain latency) → per-widget independent loading (Dune), and be Etherscan-honest about "awaiting confirmation."
- **Mobile:** Buyer flow (connect → buy/redeem → holdings) must be fully mobile-usable — this is where real money moves. Dashboard can degrade gracefully: collapse the 4-step agent pipeline to a vertical stack, KPI strip to a 2-col grid, tables to stacked rows. 14px body minimum holds on mobile.
- **Three distinct surfaces, one system:** Landing (persuasion, can use Crimson Pro + more air), Dashboard (proof, dense, mono-heavy), Buyer flow (Stripe-calm, trust-forward). Shared tokens, different density.
- **Number formatting:** USD/USDC amounts use de-emphasized symbol/decimals (Stripe); percentages get +/− and semantic color; hashes truncate middle with copy.

### Anti-patterns (seen in comparables, must avoid)
1. **Pure-black background (`#000`).** Causes OLED halation, flattens depth. Use deep charcoal. (Avoided by all 5.)
2. **Identical card grid / "everything is a box with a border-radius."** The generic SaaS-template look our constraints ban. Hyperdash and lesser Dune dashboards fall into wall-to-wall cards. Use hairline dividers and weight hierarchy (Linear) instead.
3. **Color as decoration.** Color must be semantic (direction, status, verification). The moment teal appears just to "look DeFi," it's noise.
4. **Spinner-on-blank-screen loading.** Blocks on slowest fetch, causes layout shift. Anti-pattern vs Dune's per-widget + Stripe's structured-zero approach.
5. **Per-keystroke input validation** in the buyer flow — nags the user. Validate on blur (Stripe).
6. **Confetti / celebratory success animation** on a financial action. Reads as unserious for real money. Calm checkmark only (Stripe).
7. **Hiding chain latency behind fake instant UI.** Dishonest for a provenance product. Be Etherscan-honest: "awaiting confirmation."
8. **Decorative gradients / gradient text** — explicitly banned by our constraints, and notably absent from every craft leader here. Linear deliberately *reduced* chrome/tint.
9. **Static "verified" badge with no real check.** A green badge that isn't backed by an actual recomputed hash is exactly the trust theater our product exists to destroy.

### Stolen Elements (specific patterns to adopt)
1. **Etherscan green-check verification badge → live client-side recompute** *(from Etherscan #3).* A green `#00d4aa` check glyph (13px) next to each rebalance reasoning doc. On render, browser computes `sha256(reasoning.json)` and asserts equality with the on-chain anchored hash; tooltip on hover shows `sha256 === 0x1f4e…a9c2 · block 1,284,019`. Yellow/amber state if not-yet-anchored (pending), gray if unanchored. Badge gates nothing visually but is the single most important trust glyph in the product. Transition: badge fades in 150ms ease-out once the check resolves.

2. **Stripe KPI card with inline sparkline + de-emphasized currency** *(from Stripe #5).* NAV headline: integer part full-contrast JetBrains Mono 600 weight, `$` and trailing decimals at `opacity: 0.6`, all `tabular-nums`. A 40px-tall, axis-less sparkline of NAV-since-inception to the right. A `+1.3%` trend pill in accent (or red on loss), 12px, `letter-spacing: 0.02em`. Card uses a `1px solid rgba(255,255,255,0.07)` hairline, no heavy shadow. Mirror this exact treatment for the redeem/holdings values.

3. **Linear hairline-divider + weight-based hierarchy + negative tracking** *(from Linear #4).* Drop boxy cards in favor of `1px rgba(255,255,255,0.07)` dividers between sections; charcoal base `#0c0e0f`; body DM Sans 14px / 400 weight at `letter-spacing: -0.011em` in muted `rgba(255,255,255,0.62)`; headings DM Sans 600 at `-0.022em` full-contrast. All hover/focus/panel transitions `150ms ease-out` (panel slide `200ms`). Differentiate elements by **weight + opacity, not font size** — this keeps the dense dashboard calm and dodges the identical-card-grid ban.

4. **Dune per-widget independent loading + answer→trend→proof descent** *(from Dune #2).* Each dashboard module (NAV, latest rebalance, reasoning trace, attestation, chain-cost compare, verified contracts) fetches independently with a layout-matched skeleton; the slow on-chain anchor read never blocks NAV from painting. Each module resolves skeleton→content with a 150ms ease-out cross-fade. Order modules top-to-bottom as answer (NAV) → trend (rebalance history) → proof (reasoning JSON + hash + contracts).

5. **Hyperdash net-delta strip → "since last rebalance" strip** *(from Hyperdash #1).* A horizontal row of mono delta pills above the holdings table: `+2 positions opened`, `−1 closed`, `NAV +1.3%`, `last rebalance 4h ago`. Each value JetBrains Mono 600 tabular-nums with leading +/− and semantic color; labels 12px uppercase `letter-spacing: 0.04em` muted. On a no-trade decision the strip reads `0 changes · agent held · reasoning anchored ✓` — turning the quiet moment into a confidence signal.

6. **Multi-agent provenance pipeline** *(WhaleIndex original, informed by Etherscan tab cascade + Slither-style call graph).* Horizontal 4-node pipeline: Scorer → Allocator → Risk → Coordinator, connected by hairlines, each node a small panel showing input/output summary + a confidence value (mono). Clicking a node slides in a right detail panel (Linear/Stripe pattern) with that agent's full reasoning. This is the signature visual no DeFi comparable has.
