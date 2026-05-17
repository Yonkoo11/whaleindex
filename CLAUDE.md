# WhaleIndex — CLAUDE.md

## User Profile (READ FIRST)

The user is a vibecoder with zero coding background, also a medical intern. **Talk in plain English. No dev jargon.** Say "save point" not "commit", "publish" not "push", "version" not "branch". Summarize terminal output in one sentence; never paste raw error messages. Describe what changed by what the user sees in the live app, not by what files were edited. Auto-save after every task (`git add` + `git commit`); never ask. Fix failing tests silently. Use `/compact` proactively, never ask permission.

---

## Phase 1 Gate (BLOCKING — DO NOT START PHASE 2 UNTIL PASSED)

**Core Action:** Multi-agent reads HL + Aster public leaderboards live → outputs top-10 whale allocation delta JSON → rebalance executor calls Gateway USDC move on Arc testnet → on-chain NAV updates → UI shows pre/post NAV + cost in cents + latency in ms.

**Success Test (binary):** Gateway move settles in <2 seconds AND NAV updates correctly. Both yes → passed.

**Min Tech:**
- 1 Solidity contract: Index ERC-20 with `rebalance(allocation[])` + `nav()`
- 1 leaderboard-reader agent (Python)
- 1 rebalance executor that signs Gateway move
- 1 minimal UI page (NAV + last rebalance receipt)
- Deploy on Arc testnet

**NOT Phase 1:** USYC, Paymaster, CCTP, multi-venue (Aster + Polynomial), buyer flow, landing page polish, demo video.

See `ai/memory.md` for full context.

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
