
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
