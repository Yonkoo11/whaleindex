
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
