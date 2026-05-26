# WhaleIndex — Demo Video Plan

Target: under 3 minutes (form caps at 3). Goal: 2:30.
Judging weights it touches: agentic (30%), traction (30%), Circle usage (20%), innovation (20%).
Hosting: YouTube unlisted or Loom link pasted into the "Project Video Demo" field.

## Format decision
This is a live, polished web app with genuinely live on-chain data, so the demo is a
real screen walkthrough of https://yonkoo11.github.io/whaleindex, not an abstract
animation. Real product footage reads as traction; a motion-graphics explainer reads
as a pitch. We show the actual site doing actual things on Arc testnet.

Two ways to make it, pick one:
- **Option A (recommended): you screen-record it.** Most authentic, your own voice. I give
  you the exact script + on-screen shot list below. ~20 min to record with QuickTime
  (Cmd-Shift-5 on Mac), one or two takes.
- **Option B: I build it.** I capture the real site states with the browser tool, generate
  voiceover with ElevenLabs, add captions, and assemble in Remotion. No recording needed
  from you. Slightly less "human", but hands-off.

Either way the frames are real site footage. No fake numbers, no stock imagery.

## Honesty rules for this video (non-negotiable)
- No invented user counts or returns. If we show traction it is the real on-chain holder
  and the real published decision.
- Say plainly that CCTP cross-chain and USYC are mocked on testnet. One honest sentence
  beats a judge catching it.
- Do not call it production-ready or claim it is audited. It is a working testnet build.

---

## Script (voiceover) with shot list and timecodes

Total ~410 words at a calm pace lands near 2:30.

### 0:00–0:15 — Hook
VO: "Copy-trading bots tell you what to buy. None of them tell you why. You are trusting
a black box with your money. WhaleIndex is the opposite of a black box."
SHOT: Land on the hero. The headline reads "Every decision this index makes, including the
decision to do nothing, is published, hashed, and anchored on-chain." Hold on it.

### 0:15–0:40 — What it is
VO: "WhaleIndex is an index token on Arc testnet, priced in USDC, that mirrors the top
Hyperliquid whale positions. A pipeline of four agents decides every cycle. A Scorer ranks
the whales, an Allocator drafts weightings, a Risk agent can veto, and a Coordinator makes
the final call."
SHOT: Scroll slowly down to the Decision Pipeline. Let the four agent cards land on screen
one at a time.

### 0:40–1:15 — The differentiator: it published a decision to do nothing
VO: "Here is what makes it different. This cycle, the agents looked at the whales and chose
not to trade. Both active whales were long, so the Risk agent vetoed all three proposals,
and the Coordinator held. Most bots would hide that. WhaleIndex publishes it. The decision
to do nothing is a first-class record with the full reasoning attached."
SHOT: Hover the "3 vetoed by Risk" and "Coordinator: HELD" chips. Scroll to the Risk card
showing the veto reasons (directional bias 100%, concentration 98.2%).

### 1:15–1:45 — Verify it yourself
VO: "And you do not have to take my word for it. Every cycle is hashed into a document and
anchored on-chain. Open the full record and you can read exactly what each agent saw and
decided. Don't trust the agent. Verify it."
SHOT: Click into "Full record" / expand a published decision. Show the content hash and the
agent-by-agent audit trail.

### 1:45–2:15 — Buy and redeem, live on Arc
VO: "It is a real product, not a slideshow. Connect a wallet and you can buy or redeem index
shares at the on-chain NAV, settled on Arc in about a second, with USDC as the gas token so
you never touch a separate fee coin."
SHOT: Click Connect wallet, approve the Arc network switch, type an amount in Buy, show the
estimated shares, submit, show the success state and the new holding. (If self-recording,
this is the money shot. Use a testnet wallet funded from faucet.circle.com.)

### 2:15–2:35 — Circle stack + honest close
VO: "Under the hood: Arc for settlement, USDC for everything, CCTP for cross-chain routing
and USYC for idle yield, both mocked on testnet until Circle allowlists us, plus a staking
bond that slashes a whale if it misbehaves. WhaleIndex is a proof-of-reasoning ledger with a
buy button. That is the whole idea."
SHOT: Scroll the verified-contracts list and the attestation section. End back on the hero
headline.

---

## Pronunciation guide (for ElevenLabs if Option B)
- WhaleIndex -> "Whale Index"
- NAV -> say "nav" (rhymes with "have"), not N-A-V
- USDC -> "U S D C"
- CCTP -> "C C T P"
- USYC -> "U S Y C"
- Arc -> "Arc"
- Hyperliquid -> "Hyper-liquid"

## Pre-record checklist
- [ ] Live site loads, oracle shows "fresh", holder shows 1 WHALE
- [ ] Testnet wallet funded with a little USDC for the live buy (faucet.circle.com)
- [ ] Browser zoom 100%, hide bookmarks bar, 1280x800 or 1920x1080 capture
- [ ] Close notifications / do-not-disturb on
- [ ] Captions: turn on auto-captions in YouTube or burn them in (form asks for subtitles)

## If Option B (I build it), assets I produce
1. Real frame captures of each shot above (browser tool, 1280x800).
2. ElevenLabs voiceover track from the script.
3. Remotion project sequencing frames + VO + burned-in captions + subtle motion.
4. Rendered MP4 under 3 minutes, ready to upload.
