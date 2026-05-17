# WhaleIndex

**Cross-venue whale index on Arc.** One USDC-denominated token that mirrors a basket of top perp traders across Hyperliquid, Drift, and GMX, with idle USDC parked in USYC for yield and Paymaster-sponsored buy / redeem so holders never touch native gas.

Built for the [Agora Agents Hackathon](https://agora.thecanteenapp.com) (Canteen × Circle × Arc, 2026-05-11 → 2026-05-25). Targets **RFB 06 — Social Trading Intelligence** as the primary fit, with RFB 04 (Adaptive Portfolio Manager) as a secondary lens.

## What it does

1. An off-chain multi-agent reads each whale in a curated watchlist via public APIs:
   - Hyperliquid `clearinghouseState` (POST `api.hyperliquid.xyz/info`)
   - Drift `dlob.drift.trade`
   - GMX subgraph
2. Aggregates net signed notional per coin across whales.
3. Selects the top-N coins, weights them, decides direction.
4. Calls `RebalanceExecutor.rebalance(...)` on Arc, which:
   - Pulls USDC from `IndexToken` treasury
   - Parks a configurable slice in `USYCParkVault` (yield on idle USDC)
   - Routes the remainder via `CCTPRouter` (Circle CCTP V2 `depositForBurn`)
   - Updates `NAVOracle` with the new operator-signed NAV
5. The frontend reads NAV from chain and renders the position state plus a per-rebalance receipt.

## Architecture

```
Off-chain (Python)
  agent/leaderboard_reader.py  reads each whale's clearinghouseState in parallel
  agent/allocation_engine.py   computes net-notional-weighted allocation across top coins
  agent/main.py                orchestrator, prints (and Phase 2 submits) the rebalance plan
  data/whales-hl.json          curated whale watchlist with source URLs per entry

On-chain (Solidity 0.8.24, Arc testnet chain 5042002)
  src/IndexToken.sol           ERC-20, USDC mint/redeem at NAV, owner withdraws for rebalance
  src/NAVOracle.sol            owner-updated NAV with 60s freshness window (Pyth in V2)
  src/CCTPRouter.sol           wraps Circle CCTP V2 TokenMessenger.depositForBurn
  src/USYCParkVault.sol        wraps Circle USYC for idle USDC yield
  src/RebalanceExecutor.sol    enforces on-chain spending policy, orchestrates the rebalance
  src/interfaces/              Circle CCTP V2 / USYC / Paymaster interfaces
  src/mocks/                   MockUSDC, MockUSYC, MockTokenMessengerV2 for testing + initial testnet deploy
```

## Sponsor integration

Every Circle primitive is load-bearing — remove one and a documented user path breaks.

| Primitive | Where | Load-bearing |
|---|---|---|
| **Arc L1** (chain 5042002) | All contracts deploy here, all NAV state lives here | YES |
| **USDC** | Settlement currency, denomination of NAV, Paymaster gas | YES |
| **CCTP V2** | `CCTPRouter` routes USDC Arc → Arbitrum / Solana / HyperEVM for venue collateral | YES |
| **USYC** | `USYCParkVault` parks idle USDC for yield between rebalances | YES |
| **Paymaster** | Sponsored `buy()` and `redeem()` so holders never source ARC gas | YES |
| **Wallets SDK** | Agent identity with on-chain `Policy { maxSingleMove, dailyCap }` | YES |
| **App Kit** | Unified Balance + Buy widget on the landing page | helpful |

CCTP V2 supported domains verified 2026-05-17 from Circle docs. Arc, HyperEVM, Solana, Arbitrum all reachable. BNB Chain is **not** on V2, which is why Aster (BNB-only) is dropped from the venue list.

## Why Arc?

Three properties Arc has that nothing else combines:

1. **USDC is the asset, the gas, and the settlement medium simultaneously.** No NAV-to-gas-token slippage. The index ERC-20 NAV cannot desync from its denomination because the chain's economic unit IS its denomination.
2. **Sub-second deterministic finality.** Settlement of mint / redeem is bound by Arc's finality, not the destination chain's. Holders see their share balance update in the same block as their USDC payment.
3. **CCTP V2 lists Arc as a supported chain.** Routing USDC Arc ↔ Solana ↔ Arbitrum ↔ HyperEVM is a single primitive, not a 3-bridge contortion.

These properties stack with Paymaster (gas in USDC, not native ARC) and USYC (yield on idle without leaving the protocol). Try replicating this on any other chain — you'll have a 4-token dance just to keep the index quote stable.

## Phase 1 Gate (binary)

A multi-agent run reads at least one whale's positions via the public Hyperliquid API → computes a non-empty rebalance plan → `RebalanceExecutor.rebalance(...)` lands on Arc testnet → `CCTPRouter` emits `Routed` with a real `depositForBurn` event → `NAVOracle.NAVUpdated` fires with the new NAV → frontend reads NAV from chain and displays it.

## Reproduce this

```bash
# 1. Contracts
cd contracts
forge install
forge build
forge test                                       # 28 tests pass

# 2. Off-chain agent
cd ../agent
pip install -r requirements.txt
python3 main.py                                  # prints the live rebalance plan as JSON

# 3. Deploy to Arc testnet
cd ../contracts
export DEPLOYER_PRIVATE_KEY=0x...
export OPERATOR_ADDRESS=0x...
forge script script/Deploy.s.sol \
  --rpc-url https://rpc.testnet.arc-node.thecanteenapp.com/v1/$ARC_KEY \
  --broadcast
```

## Known limits (honest)

- **NAV is operator-signed in V1.** Replace with Pyth pull oracle in V2 when Arc has Pyth support published.
- **Watchlist is curated, not learned.** RFB 06's "signal quality filtering" is satisfied by manual curation with public source URLs per entry; Phase 2 adds rank-decay degradation eviction.
- **Allocation is rank-and-equal-weight.** Not a Sharpe-weighted statistical estimator. Phase 2 adds rolling 30d Sharpe per whale.
- **HyperEVM doesn't auto-bridge to HyperCore.** USDC arrives on HyperEVM; opening real Hyperliquid perp positions still requires HL's internal bridge. V1 demonstrates the intent + CCTP V2 hop; V2 wires the HL internal bridge.
- **CCTP V2 finality is ~10-20s typical**, not 600ms. Demo language is "minutes, not blocks", never sub-second for the cross-chain hop.

## Repo layout

```
PRD.md                    full product requirements document
CLAUDE.md                 build rules + sponsor depth targets + RFB mapping
LICENSE                   MIT
README.md                 this file
ai/memory.md              project context, Phase 1 Gate, fatal flaws, distribution plan
ai/sponsor-integration.md sponsor depth audit + P0/P1/P2 wins
ai/luma-application.md    Luma application answers
.ralph/@fix_plan.md       27-task fix plan with binary acceptance tests
contracts/                Foundry project (Solidity 0.8.24, OpenZeppelin v5)
agent/                    Python off-chain reader + allocator
data/whales-hl.json       curated whale watchlist
```

## License

MIT. Use it, fork it, mirror it. If WhaleIndex becomes a thing, attribution is appreciated, not required.
