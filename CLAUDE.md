# WhaleIndex — CLAUDE.md

## User Profile (READ FIRST)

The user is a vibecoder with zero coding background, also a medical intern. **Talk in plain English. No dev jargon.** Say "save point" not "commit", "publish" not "push", "version" not "branch". Summarize terminal output in one sentence; never paste raw error messages. Describe what changed by what the user sees in the live app, not by what files were edited. Auto-save after every task (`git add` + `git commit`); never ask. Fix failing tests silently. Use `/compact` proactively, never ask permission.

## SECURITY — KEYS NEVER IN REPO OR CONTEXT

The deployer + operator + ARC RPC keys live ONLY in `~/.zshenv`. Hard rules:

- **NEVER read `~/.zshenv`, `~/.zshrc`, `~/.bashrc`, `~/.netrc`, SSH keys, or any shell-rc file.** Not `Read`, not `cat`, not `head`, not `grep`. Project hook will block.
- **NEVER print, echo, or log key values.** `echo $DEPLOYER_PRIVATE_KEY`, `print(os.getenv("KEY"))`, `vm.toString(privateKey)` are all banned.
- **NEVER commit `.env`** — gitignored; verify `git diff --cached` before every save point.
- **NEVER add a key value to any file, including this one.** Reference env vars by name only.
- **Foundry deploy uses `vm.envUint("DEPLOYER_PRIVATE_KEY")`** — reads process env at runtime, not from disk. Safe pattern.
- **Python agent uses `os.getenv("OPERATOR_PRIVATE_KEY")`** — same pattern.
- **If a key ever appears in chat or output, stop immediately and tell the user to rotate.**

Full security playbook: `SECURITY.md`. Read it before any deploy or signing work.

---

## Phase 1 Gate — PASSED 2026-05-23

Single source of truth on Phase 1 lives in `ai/memory.md`. Brief restatement:

**Core Action:** Agent reads Hyperliquid leaderboard live → outputs whale allocation
JSON → rebalance executor settles a USDC move on Arc testnet → on-chain NAV updates
→ AllocationDecided event anchors the on-chain rebalance to the off-chain reasoning doc.

**Success Test (binary):** USDC move settles in <2 seconds AND NAV updates correctly.
Verified 2026-05-23 (V2 contracts): tx `0x959e0abb...82596816`, 1.08s settlement.
Verified again 2026-05-24 via orchestrator: tx `0xa8e89e38...d0ee`, 1.13s settlement
with full provenance link to docs/allocations/<cid>.json.

**Venues actually built:** Hyperliquid only. Drift + GMX deliberately deferred to V2
(noted in README:55, contradicting earlier text in this file that referenced Aster).
Aster is dropped entirely — BNB-only, not on CCTP V2.

**NOT Phase 1:** real USYC (Teller allowlist pending), real Gateway (frontend SDK,
Phase C), real CCTP cross-chain mint (contract callers gated on Arc, requires Circle
support), buyer flow (frontend rewrite, Phase C), demo video (Phase F).

Sponsor primitive marketed as "Paymaster" in older drafts is wrong for Arc — Arc has
no Paymaster (Circle Paymaster supports Arbitrum/Base/etc, not Arc). Arc uses USDC
as the native gas token, which delivers the same UX without a Paymaster contract.
Read `deployments/arc-testnet.json._meta.known_limitations` for the live constraints.

---

## Build Order (USER-ENFORCED, NO SKIPPING)

1. **Phase 1: Core action** — defined above
2. **Phase 2: Data flows** — USYC + multi-venue + buyer mint-redeem + Paymaster
3. **Phase 3: Product complete** — landing page, history view, README, LICENSE
4. **Phase 4: Visual polish** — `/design whaleindex` → `/landing whaleindex` → `/demo-video`

**No CSS before Phase 4. No landing polish before Phase 3.** This rule is non-negotiable.

---

## Sponsor Depth Targets (must hit ≥4/5 by deadline)

| Primitive | V1 target | Acceptance test (Phase 4.5 audit) |
|---|---|---|
| Arc L1 | 5/5 | Contract deployed on Arc testnet, all txs land |
| USDC | 5/5 | All settlement denominated in USDC, no native token surfaced |
| Gateway | 5/5 | Rebalance triggers Gateway move <2s, Unified Balance widget on buy page |
| USYC | 4/5 | Idle USDC auto-routes to USYC, yield accrues in NAV |
| Paymaster | 4/5 | Buyer without Arc gas completes purchase via USDC fee |
| Contracts | 4/5 | Three contracts coordinated (Index + Executor + Reader) |
| Wallets | 4/5 | Agent identity with policy: max move, daily cap, allowed venues |

Full plan: `ai/sponsor-integration.md`. Run Phase 4.5 within 48h of deadline to verify these.

---

## RFB Mapping (after full RFB content review)

- **Primary: RFB 06 Social Trading Intelligence.** Hits all 5 of "What AI decides" — which whales to follow, allocation per whale, when to stop (degradation detection), multi-signal portfolio (HL+Aster+Polynomial), signal quality. Example-build analog: SmartMirror.
- **Secondary: RFB 04 Adaptive Portfolio Manager.** Cross-venue rebalancing + USYC parking from this RFB. Does NOT do goal-based or tax-loss-harvesting; don't pitch as RFB 04 primary.
- **Traction metrics to track (per RFB 06):** leaders tracked, AUM, performance vs raw leader average (risk-adjusted), follower retention.

## Hackathon Context

- **Window:** 2026-05-11 → 2026-05-25
- **Submission:** https://forms.gle/hFPM2t4Jt1zGfqzM7
- **Apply:** https://luma.com/7i50p2r9 (passphrase: `SITEx1313`)
- **Canteen Discord:** https://discord.gg/TGnyfKh23V
- **Arc builder Discord:** https://discord.com/invite/buildonarc (mention "Canteen + Agora" in onboarding)
- **ARC CLI:** `uv tool install git+https://github.com/the-canteen-dev/ARC-cli`
- **Arc docs:** https://arc-node.thecanteenapp.com/
- **Circle docs:** https://developers.circle.com
- **Judging:** 30% agentic / 30% traction / 20% Circle tool usage / 20% innovation

---

## Required Tech (must use)

- **Settlement:** Arc (Canteen-hosted testnet)
- **Cross-chain USDC:** Circle Gateway SDK
- **Yield:** Circle USYC
- **Gas UX:** Circle Paymaster (so the user never sees native gas)
- **Contracts:** Foundry + OpenZeppelin
- **Agent:** Python asyncio + httpx
- **Frontend:** Next.js + App Kit Unified Balance, hosted on GitHub Pages
- **Hosting:** GitHub Pages only — never Netlify/Vercel (per global rule)

---

## Research Base Link

Primary research:
- `~/Projects/IDEAS-SUMMARY.md` Quick-Pick AI/Agent section
- `~/Projects/hackathon-winners/ARCHETYPES.md` A5 + B7
- `~/Projects/hackathon-winners/DATABASE.csv` (Urani, APY-LO, OpenFund, Latinum, MCPay)
- agora.thecanteenapp.com Research item #05 (HL whale migration index)

---

## Build Rules

- Auto-save after every task. Never ask.
- Fix failing tests silently. Never explain test frameworks.
- Test the live URL after every meaningful change — open the page, click the buyer flow, verify the rebalance receipt shows up. Compile success is not evidence the product works.
- Use plain English in user-facing output. No dev jargon. No emojis unless asked.
- Distinguish: designed vs built vs tested vs proven. Don't conflate.
- Every completion claim must include: What I Did / Confidence Level.
- Default to action, not confirmation. If the answer is obviously yes, just do it.
