# Design Progress: whaleindex

started: 2026-05-25
style_config: ~/.claude/style.config.md (no project override)
color_mode: dark-only
flags: none
build_target: full product (landing + live dashboard + buyer flow)

phase_0: completed

phase_1: in_progress
state_design_output: ai/state-design.md

phase_1.5: completed
comparables: [Hyperdash, Dune Analytics, Etherscan, Linear, Stripe Dashboard]
research_output: ai/design-research.md
research_thesis: "Not a trading terminal — a proof-of-reasoning ledger with a buy button. Whitespace: no competitor designs 'audit the agent'. Crimson Pro for authority moments is a category differentiator."

phase_2: completed
proposals: [proposal-1.html (The Ledger), proposal-2.html (The Thesis), proposal-3.html (The Pipeline)]
dna_codes: [DNA-G-S-M-D-X, DNA-S-T-C-N-E, DNA-B-T-I-M-S]

phase_3: completed
selected: "hybrid: Proposal 3 (The Pipeline) as base + Proposal 2's Crimson Pro thesis hero on landing. Proposal 1's dense decision-ledger becomes the expandable full-record detail view."
selection_rationale: "P3 makes the 4-agent chain the hero = our 'audit the agent' whitespace + best for agentic/innovation judging. P2's serif thesis is ownable authority in a sans/mono category. Combine the signature visual with the persuasion voice."

phase_4: completed
audit_result: pass
issues_fixed: 2 (settlement-cell wrapping on held cycle; NAV total-vs-per-share pill label)
production_target: docs/index.html — hybrid built + wired to live Arc RPC + decision-latest.json + attestation + wallet buyer flow

phase_5: completed (ran ui-revamp + frontend-design qa skills for real this round)
qa_result: APPROVED (one documented type-scale exception + one untested write path)
ui_revamp_audit: "15 violations -> 0 (fixed: 2 linear easings, 12 unguarded hover rules, scattered radii). Independently re-verified 0."
qa_automated: "0 emojis · 0 transition:all · 0 gradient text · 1 !important (reduced-motion block, legit) · colors from tokens · DM Sans+Crimson Pro+JetBrains Mono"
qa_typography: "FIXED — removed all sub-12px text (was 10px/11px). No text below 12px. Reading prose 14-16px, 12px reserved for uppercase tracked labels, 13px dense mono data."
qa_type_exception: "Hard gate #3 wants most-used size >=14px; most-used is 13px (dense mono data). Judged an intentional data-UI choice (matches Linear's 13px + research brief 'weight not size' + style config dense-data intent), NOT broken type. Documented, not silently passed."
qa_slop: "FIXED — stripped 15 prose em dashes (AI-slop tell flagged by user) -> commas/periods/semicolons. 0 slop words (delve/vibrant/seamless/etc). Placeholder '—' glyphs kept (not parenthetical prose)."
qa_caveat: "Buyer WRITE path (connect/approve/buy/redeem) wired + partially validated by read-only sim (buy() reachable, USDC is std 6-dec ERC20, reverts as expected on no-allowance) but NEVER live-executed. NAV oracle currently STALE, which can block a real buy until refreshed. Read path verified live."
pushed_to_live: "NO — ui-revamp + qa polish commits are local only; live site (yonkoo11.github.io/whaleindex) still shows pre-polish hybrid from commit 227ae32."

phase_5: pending
qa_result:

## Critique findings carried into design (2026-05-25)
- Flagship "agent reasoning" section: all allocation docs on disk are demo synthetic (multi_agent_audit empty). User will supply real whale addresses to seed a genuine run.
- "Bonded whales" section: 0 real bonds, 1 demo slash — UI must not look broken in empty/seed state.
- Buyer flow does NOT exist yet (read-only site today). Full-product scope adds it — net-new wallet wiring.
- PRD oversells 3 venues; only Hyperliquid is real. UI copy must match README honesty, not PRD.
- CCTP + USYC mocked (documented Arc-platform limitation; fair to disclose in UI).
