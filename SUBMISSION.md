# Agora Agents Hackathon: Submission Answers (WhaleIndex)

Copy each block into the matching form field. Fields marked [YOU] need your own info.

---

## Email
[YOU] Use the account you want the confirmation mailed to.

## Project Name
WhaleIndex

## GitHub Handle
Yonkoo11 (repo: https://github.com/Yonkoo11/whaleindex)

## Discord Handle
[YOU]

## Telegram Handle
[YOU]

## Twitter / X Profile
[YOU]

## Number of Team Members
1 (Solo)

## Team Members Names
[YOU]

## Problem Statement
Copy traders on perp DEXs can see what the big whales hold, but they cannot act on it safely or verifiably. They either mirror trades by hand, which is slow, emotional, and easy to front-run, or they trust a black-box copy-trading bot that never shows its reasoning. Nobody can hold an automated strategy accountable for the calls it makes, and especially not for the call to sit still and do nothing. WhaleIndex makes every one of those decisions auditable.

## Project Description
WhaleIndex is a USDC-denominated index token on Arc testnet that mirrors the top Hyperliquid whale perp positions. A four-agent pipeline runs the strategy: a Scorer ranks whales, an Allocator proposes weightings, a Risk agent vetoes anything outside threshold, and a Coordinator makes the final call. The signature feature is on-chain provenance. Every rebalance decision, including a decision not to trade, is published as a hashed JSON document with its CID anchored on chain, so anyone can audit exactly why the agent did what it did.

Tech: Solidity 0.8.24 with Foundry and OpenZeppelin v5 contracts (NAVOracle, IndexToken with buy and redeem at NAV, RebalanceExecutor, WhaleAttestation slash-bond), a Python multi-agent orchestrator with an optional Anthropic reasoner, and a vanilla JS plus ethers.js frontend hosted on GitHub Pages wired to live Arc RPC. Circle CCTP routing and a USYC park vault for idle capital are wired but mocked on testnet (see the feedback note below).

The live demo right now shows a real no-trade decision: both currently active whales are long, the Risk agent vetoed all three allocation proposals, and the Coordinator held. That decision to hold is published with its full audit trail, which is the whole point of the project.

## Traction
[YOU, add real numbers] The live read-only dashboard is public and seeded with 11 real Hyperliquid whale addresses pulled from the leaderboard. Add any testers, repo stars, or social activity here.

## Project Source Code
https://github.com/Yonkoo11/whaleindex

## Project Live
https://yonkoo11.github.io/whaleindex

## Project Video Demo
[YOU, record a Loom or YouTube link under 3 minutes]

## (Arc OSS) Apply checkbox
Yes, check it. The repo is already open source and stays that way.

## (Arc OSS) Why choose your project / what primitives are you exposing
WhaleIndex exposes four primitives other Arc builders can lift directly:

1. On-chain decision provenance: a reusable pattern for hashing any agent or strategy decision into a JSON doc, anchoring its CID on chain, and publishing the full audit trail. Any agentic project that wants to be auditable can drop this in.

2. NAV oracle plus index-token buy and redeem at NAV: a clean IndexToken that mints and burns against a freshness-gated NAV oracle. Reusable for any tokenized basket on Arc.

3. WhaleAttestation slash-bond contract: bond an actor, slash with an on-chain evidence CID. A general accountability primitive, not specific to whales.

4. A published decision to do nothing as a first-class artifact, not a silent no-op. Most agents only log when they act. This one proves its inaction too.

Compared to the example code out there for Arc builders, we add the provenance-anchoring flow and the multi-agent veto pipeline, plus a CCTP router and USYC park-vault wiring pattern for idle capital.

## Circle / Arc Feedback
What worked: Arc testnet's fast finality made the buy and settle flow feel close to instant, which is the right substrate for an index that rebalances and settles on chain. CCTP is the natural fit for moving USDC across chains.

Where it can improve: native USYC and full CCTP were not available to us on Arc testnet, so we mocked both and disclosed that in the UI rather than ship something untrue. The public RPC caps getLogs at 10k blocks, which forced us to chunk every event scan into 9k-block windows. A higher cap or a hosted indexer would remove a lot of frontend complexity. Chain-param docs were thin (chainId 5042002, native USDC at 18 decimals instead of the usual 6 tripped us up), so a single canonical params page would help new builders a lot.

## General Feedback
[YOU, optional]
