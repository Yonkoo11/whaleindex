# WhaleIndex

**A USDC-denominated index on Arc that mirrors top Hyperliquid whales, with on-chain provenance for every rebalance decision.** An off-chain agent reads each whale's positions + 30-day realised PnL, applies a rank-decay filter, computes allocations, publishes a canonical JSON reasoning document, hashes it, and submits a rebalance whose on-chain event is anchored to that hash. Anyone can click from the tx on Arcscan to the agent's reasoning.

Built for the [Agora Agents Hackathon](https://agora.thecanteenapp.com) (Canteen × Circle × Arc, 2026-05-11 → 2026-05-25). Targets **RFB 06 — Social Trading Intelligence** primary, RFB 04 (Adaptive Portfolio Manager) secondary.

## What works today (verified live on Arc testnet)

| Capability | Evidence | Status |
|---|---|---|
| Contracts deployed + verified on Arcscan | 7/7 verified, source public ([NAVOracle](https://testnet.arcscan.app/address/0xcba2b630051527cbebdc9212611a059c080b9e1c) · [IndexToken](https://testnet.arcscan.app/address/0x68a8809e118e6c778d199e0dc7586ac88589b708) · [RebalanceExecutor](https://testnet.arcscan.app/address/0x2096b1fcad5d3d4303f1ac3daba4116c73b0d282) · [CCTPRouter](https://testnet.arcscan.app/address/0xc74efa01142f7ba9e6b96c5c0841dca0ab744e34) · [USYCParkVault](https://testnet.arcscan.app/address/0xe8682ca1ce90a6be3bd91a01bf3e39c19543521a) · [MockUSYC](https://testnet.arcscan.app/address/0x86df318ff4356682da819516bd05b9873f3b8f07) · [MockTokenMessenger](https://testnet.arcscan.app/address/0x60612ad24e730abf256ccfdd77dd0f431b20a079)) | **Live** |
| Real native USDC (`0x3600…0000`) as settlement currency | All buy / redeem / rebalance flows touch real USDC | **Live** |
| Sub-second settlement on Arc | Rebalance tx [`0xa8e89e38…d0ee`](https://testnet.arcscan.app/tx/0xa8e89e389f7328e044808483aca8d225cf699907c5b0bc20d28689465a4dd0ee) settled in **1.13s** | **Live** |
| On-chain → off-chain provenance | `AllocationDecided(cid)` event in the tx anchors to [allocation doc on GitHub Pages](https://yonkoo11.github.io/whaleindex/allocations/7a5223a765443641047f85eef730c73bab50550398ac50085d3167101a5bc66b.json); CID = keccak256 of the canonical JSON | **Live** |
| Full agentic loop in one command | `agent/orchestrator.py`: watchlist → positions+PnL → rank-decay → allocations → publish doc → sign + submit | **Live** |
| Safety primitives | Pausable on IndexToken + RebalanceExecutor; NAV bounded ±50% per update; rebalance requires non-zero CID | **Live, 47/47 tests** |
| Operator policy enforced on-chain | `maxSingleMove` (500 USDC) + `dailyCap` (10,000 USDC) | **Live** |
| Agent identity separable from deployer | Two-key setup supported (operator ≠ deployer); single-key default for now | **Live, configurable** |

## What's deferred to V2 (and why)

| Capability | Blocker | Workaround in V1 |
|---|---|---|
| Real CCTP V2 burn-and-mint from contracts | Arc testnet's CCTP TokenMessenger silently rejects contract callers (EOA works; verified via dedicated probe). Likely `tx.origin` gate or undocumented allowlist. | `MockTokenMessengerV2` in the deploy. On-chain Routed + NAVUpdated events still emit. Real USDC moves through the rest of the flow. |
| Real Circle USYC | Teller (`0x9fdF…105A`) requires wallet allowlisting via Circle support ticket. | `MockUSYC` for park / unpark. Idle USDC sits at-cost. |
| Circle Paymaster | Not deployed on Arc (supported: Arbitrum, Avalanche, Base, Ethereum, Optimism, Polygon, Unichain). | **Not needed.** Arc uses USDC as the native gas token — Paymaster's "no native required" UX is built into the chain. |
| Frontend (Next.js + App Kit + Unified Balance widget) | Phase C work, separate session. | Static `docs/index.html` reads NAV + last rebalance from RPC; arc-testnet URL config landed but visual polish + buyer flow deferred. |
| Multi-venue (Drift, GMX) | Phase 2 by design. | Hyperliquid only. Aster deliberately dropped (BNB-only, not on CCTP V2). |
| Curated real whale watchlist | Hyperdash blocks WebFetch; manual curation needed by operator. | 3 placeholder addresses in `data/whales-hl.json`. Orchestrator gracefully exits with 0 allocations when whales have no positions. `--demo-allocation` flag injects a synthetic 1-coin allocation so the submit path is testable without curation. |

Read `deployments/arc-testnet.json._meta.known_limitations` for the operational details.

## Architecture

```
Off-chain (Python)
  agent/leaderboard_reader.py   reads each whale's clearinghouseState + 30d realised PnL
  agent/selection_engine.py     rank-decay eviction (drops whales whose rank fell >N places)
  agent/allocation_engine.py    net-notional-weighted top-N coin allocation
  agent/orchestrator.py         single entry point: data → decision → publish doc → sign + submit
  agent/contract_client.py      typed signing client around RebalanceExecutor
  data/whales-hl.json           curated whale watchlist (source-annotated)
  data/orchestrator-history.jsonl   one row per rebalance run

On-chain (Solidity 0.8.24, Arc testnet chain 5042002)
  src/IndexToken.sol            ERC-20, USDC mint / redeem at NAV, Pausable
  src/NAVOracle.sol             owner-updated NAV, 60s freshness window, ±50% per-update bound
  src/CCTPRouter.sol            wraps CCTP V2 TokenMessenger.depositForBurn (mock for V1)
  src/USYCParkVault.sol         wraps USYC for idle USDC yield (mock for V1)
  src/RebalanceExecutor.sol     spending policy + rebalance entry; emits AllocationDecided(cid)
  src/probes/CCTPProbe.sol      diagnostic probe used to isolate the Arc CCTP contract-caller gate

Off-chain reasoning provenance
  docs/allocations/<cid>.json   the JSON the agent committed to; CID = keccak256(canonical_json)
                                publicly resolvable at https://yonkoo11.github.io/whaleindex/allocations/<cid>.json
```

## Sponsor integration depth (post-V2 deploy)

| Primitive | Score | What's live | What unlocks ≥4/5 |
|---|---|---|---|
| **Arc L1** | 5/5 | All state on Arc, deterministic finality demonstrated (1.13s settlement) | already there |
| **USDC** | 5/5 | Native USDC (`0x3600…0000`) is the settlement currency end-to-end | already there |
| **Contracts** | 4/5 | 7 verified contracts, Pausable, NAV bounds, on-chain provenance event | atomic factory refactor (Phase E) |
| **Wallets** | 3/5 | On-chain policy (`maxSingleMove`, `dailyCap`); operator identity separable | EIP-712 attestations on the CID (Phase B refinement) |
| **CCTP V2** | 2/5 | Code path correct against real V2 interface, mock deployment | Circle ticket to allow contract callers on Arc, or off-chain operator-EOA signing |
| **Gateway** | 0/5 | Real Arc Gateway addresses recorded as `canonical_arc_addresses_referenced_but_not_called` | frontend rewrite with `@circle-fin/app-kit` (Phase C) |
| **USYC** | 0/5 | Mock USYC deployed; real Teller addr referenced | Teller allowlist via Circle support |
| **Paymaster** | n/a | Not on Arc; replaced with "USDC-as-gas (Arc native)" | n/a — already delivered by chain |

## Why Arc?

Three properties Arc has that nothing else combines:

1. **USDC is the asset, the gas, and the settlement medium simultaneously.** No NAV-to-gas-token slippage. The index ERC-20 NAV cannot desync from its denomination because the chain's economic unit IS its denomination. The "Paymaster pattern" (pay gas in USDC, not native ETH) is built into the chain — no extra contract needed.
2. **Sub-second deterministic finality.** Settlement of rebalance is bound by Arc's finality, not the destination chain's. Two live txs at 0.78s and 1.13s settlement (see "What works today" table).
3. **CCTP V2 lists Arc as a supported chain** (domain 26). Source-chain Standard transfers are supported (Fast disabled for Arc-as-source today). The destination-side mint is the long pole; the source-side burn is one tx.

## Reproduce this

```bash
# 1. Contracts: build + test
cd contracts
forge install
forge build
forge test                          # 47 tests pass

# 2. Off-chain agent: install + run pipeline against Arc
cd ..
pip install -r agent/requirements.txt
python3 -m agent.orchestrator --network arc-testnet --dry-run --demo-allocation \
        --aum-usdc 0.5 --new-nav-usdc 1500000
# Outputs: published allocation doc + CID, dry-run skips submission.

# 3. Deploy to Arc testnet (re-deploy with real USDC + real CCTP later when Circle approves)
export DEPLOYER_PRIVATE_KEY=0x...
./scripts/deployer-address.sh                       # shows derived address + Arc balance
# fund the address at https://faucet.circle.com (Arc Testnet)
./scripts/deploy-arc-v2.sh                          # real USDC, mock CCTP (V2 limitation)

# 4. Verify all V2 contracts on Arcscan
./scripts/verify-arcscan.sh

# 5. Live end-to-end submission against Arc
./scripts/orchestrate-arc.sh --demo-allocation --aum-usdc 0.3 --new-nav-usdc 1500000
```

## Repo layout

```
PRD.md                                  full product requirements document
CLAUDE.md                               build rules; defers Phase 1 truth to ai/memory.md
README.md                               this file
LICENSE                                 MIT
ai/memory.md                            project context, Phase 1 evidence, lessons learned
ai/plan.md                              senior V1 build plan, 31 dependency-ordered steps
ai/sponsor-integration.md               sponsor depth audit (older; this README is now authoritative)
ai/luma-application.md                  Luma application answers
contracts/                              Foundry project (Solidity 0.8.24, OZ v5)
contracts/src/                          core stack: IndexToken, NAVOracle, RebalanceExecutor, CCTPRouter, USYCParkVault
contracts/src/mocks/                    MockUSDC, MockUSYC, MockTokenMessengerV2
contracts/src/probes/                   CCTPProbe — diagnostic, not a production dependency
agent/                                  Python pipeline (orchestrator + 4 supporting modules)
data/whales-hl.json                     curated whale watchlist (currently placeholders)
data/orchestrator-history.jsonl         append-only history of every rebalance run
deployments/arc-testnet.json            live deployment addresses + verification links + known limitations
docs/index.html                         minimal NAV viewer (static)
docs/allocations/                       content-hashed allocation reasoning docs (one per rebalance)
scripts/                                deploy / smoke / orchestrate / verify wrappers
```

## License

MIT. Use it, fork it, mirror it. If WhaleIndex ships and grows, attribution is appreciated, not required.
