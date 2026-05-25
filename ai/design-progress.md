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

phase_5: completed
qa_result: APPROVED (with caveat)
qa_automated: "0 emojis · 0 transition:all · 0 gradient text · DM Sans+Crimson Pro+JetBrains Mono loaded · prefers-reduced-motion honored · tabular-nums x19 · no missing element ids"
qa_caveat: "Buyer WRITE path (connect/approve/buy/redeem) is wired but NOT live-executed — needs a funded browser wallet on Arc to verify. Read path (NAV, decision, attestation, contracts) verified live via local render against real Arc RPC."

phase_5: pending
qa_result:

## Critique findings carried into design (2026-05-25)
- Flagship "agent reasoning" section: all allocation docs on disk are demo synthetic (multi_agent_audit empty). User will supply real whale addresses to seed a genuine run.
- "Bonded whales" section: 0 real bonds, 1 demo slash — UI must not look broken in empty/seed state.
- Buyer flow does NOT exist yet (read-only site today). Full-product scope adds it — net-new wallet wiring.
- PRD oversells 3 venues; only Hyperliquid is real. UI copy must match README honesty, not PRD.
- CCTP + USYC mocked (documented Arc-platform limitation; fair to disclose in UI).
