
## 2026-05-26 (later) — Demo video built + share-price display bug fixed

### What Changed (Plain English)
- The 1 minute 43 second demo video is made. It's a narrated walkthrough of the live
  site: the thesis, the four-agent pipeline, the Risk agent's real veto, the full record,
  the buy panel with a real $1.00 price and a correct 25-share estimate, and the Circle stack.
  Voiceover only, no background music. Captions are burned in. It's on the live site at
  /whaleindex-demo.mp4 and copied for the submission.
- Fixed the "$0.0000" price bug. The page was reading an on-chain price that rounds to whole
  dollars; now it computes the exact price from the live NAV and share supply, so the top-bar
  pill, the NAV card, the position value, and the buy estimate all read $1.0000 correctly.

### How the video was built (reproducible in video-build/)
- gen-voice.mjs: ElevenLabs voiceover (voice Adam) from segments.json -> per-segment mp3 +
  word-timed captions.srt + timeline.json. Key read from env, never printed.
- assemble-audio.sh: stitches the clips into out/vo.mp3 (102.3s).
- record.mjs: puppeteer-core scripted screencast of the site, paced to the VO timeline,
  with a read-only injected wallet (forwards to live Arc RPC, shows the real holder's real
  balances, cannot sign, never submits a tx) and an in-page synced caption bar.
- build-final.sh: muxes screencast + voiceover -> out/whaleindex-demo.mp4 (1280x800, 7.2MB).
- node_modules/ and out/ are gitignored; scripts + captions.srt are kept.

### Open items
- Video is hosted on Pages (.mp4 link). For a nicer player, upload to YouTube Unlisted.
- Recording was captured against a local copy with the price fix; after this publish the live
  site has the same fix, so the live demo and the video now match.

## 2026-05-26 — V4 redeploy: public Buy/Redeem now live + submission + video plan

### What Changed (Plain English)
- The live site's Buy and Redeem buttons now actually work. Before, they failed because the
  price feed went stale after 60 seconds. I redeployed the contracts so the price feed stays
  valid for 30 days on testnet and seeded a starting price, so a judge clicking Buy any time succeeds.
- I made one real purchase to prove it: 1 USDC bought 1 index share on Arc. The dashboard shows that holder.
- Live site repointed to the new contracts and published.
- Hackathon answers written to SUBMISSION.md (no AI-slop tells). Demo video plan in ai/demo-video-plan.md.

### Live state (verified on-chain 2026-05-26)
- Stack V4. Addresses in deployments/arc-testnet.json (V3 in legacy block).
- NAVOracle 0x01235eaC: owner=executor, freshnessWindow=30 days, nav=1.00 USDC, isFresh=true.
- IndexToken 0x2415F39a: new oracle ref, not paused, totalSupply=1 WHALE.
- Real buy tx: 0x0f5d88edb8ea15060fbe86f0aa6853c5f8e03eb40e4df90bba6cacb508b670ce.
- Live site serves V4, renders "oracle fresh" + 1 WHALE, no JS errors.

### Known open items
- Cosmetic: top-bar NAV pill shows "$0.0000" with only 1 share minted (rounding/timing display bug). Not blocking.
- Real browser-wallet buy (wallet popup + signature) still not clicked end-to-end; contract buy path IS proven live (tx above).
- CCTP + USYC still mocked on testnet (Circle allowlist pending), disclosed in UI + submission.
- Demo video not made yet. Plan ready; awaiting Option A (user records) vs B (I build).
- Submission still needs from user: email, Discord/Telegram/X handles, team name, traction numbers, video link. No deadline visible on form.

## 2026-05-25 — Production homepage rebuilt (hybrid of 3 approved proposals)

### What Changed (Plain English)
- The website now opens with a calm, confident headline (in an elegant serif) that says every decision the index makes — even the decision to do nothing — is published, hashed, and anchored on chain.
- Right below the headline is a live "decision pipeline": four boxes (Scorer → Allocator → Risk → Coordinator) showing this cycle's real result. The Risk box is the only red one (it vetoed all three proposals); the Coordinator box shows HELD. Click any box and a panel slides in from the right with that agent's full detail.
- All the numbers on the page are now pulled live from the actual Arc blockchain and the agent's decision file, not typed-in placeholders. NAV per share, share supply, bonded-whale stats, and the latest rebalance settlement time all read straight from the chain and refresh every 15 seconds.
- A new "Connect wallet" button (top right) opens a slide-in panel where someone can actually buy WHALE with USDC or redeem WHALE back to USDC, on Arc Testnet. It auto-switches their wallet to the right network, shows their balances and position value, validates the amount, runs the USDC approval then the buy/redeem, shows a live millisecond settlement counter, and ends on a calm checkmark with a link to the transaction. If no wallet is installed, it politely says so and the rest of the page still works.
- There's an "Expand full record" section at the bottom: a dense table of every whale the agent scored and every reason it vetoed each proposal — the same data the browser re-hashes to prove nothing was changed.

### What is live-read-verified vs wired-but-not-executed
- LIVE-READ (will show real chain data when an RPC responds): NAV/share price/supply/maxDelta, latest AllocationDecided rebalance + settlement seconds + gas, WhaleAttestation bonded/slashed stats, verified contract addresses, the decision pipeline + ledger (from decision-latest.json).
- WIRED BUT NOT LIVE-EXECUTED: the buyer write path (connect → switch network → approve USDC → buy/redeem → settlement timer → success). This calls the real contracts via the user's wallet but I cannot execute it without a funded browser wallet, so it is NOT tested end-to-end. Code is in place and the read of sharePrice that feeds the estimate IS live.
- Content-hash check is HONEST: browser sha256(doc) does not equal the anchored cid (server uses a different canonical serialization), so the page shows BOTH the computed digest and the anchored cid plainly and does NOT fake a match.
