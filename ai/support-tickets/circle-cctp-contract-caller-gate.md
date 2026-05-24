# Circle CCTP V2 — Contract-caller gate on Arc Testnet

**Submit to:** https://support.usdc.circle.com/ (Developer category → CCTP)
**Or DM:** @CircleDevs on X / Circle Discord #cctp

---

## Subject

Arc Testnet CCTP V2 `depositForBurn` silently reverts when called from a contract (EOA works)

## Body

Hi Circle CCTP team,

We're building **WhaleIndex** — a USDC-denominated index on Arc that mirrors top Hyperliquid whales. The product is on Arc Testnet (chain `5042002`) and uses CCTP V2 to route USDC from Arc to destination chains (initially Arbitrum, domain 3) during rebalances.

We're hitting what looks like an undocumented restriction: **contract-side `depositForBurn` calls revert with no error data**, while the identical call from an EOA succeeds.

### Setup

- **Deployer / operator EOA:** `0xf9946775891a24462cD4ec885d0D4E2675C84355`
- **Real TokenMessengerV2 on Arc Testnet:** `0x8FE6B999Dc680CcFDD5Bf7EB0974218be2542DAA`
- **Real native USDC ERC-20 interface:** `0x3600000000000000000000000000000000000000`
- **Local TokenMinter:** `0xb43db544E2c27092c107639Ad201b3dEfAbcF192`

### What works (EOA caller)

Direct `depositForBurn` from our deployer EOA, burning 0.1 USDC to Arbitrum (domain 3) with `maxFee = 50000`, `minFinalityThreshold = 2000` (Standard), `destinationCaller = bytes32(0)`:

- **Tx:** `0x24f2b089c31786f4e1658cf2a0f06009250f262a26dd3329205a25011c2cf95a`
- **Status:** SUCCESS — DepositForBurn event emitted, MessageSent on the transmitter, USDC burned.

### What fails (contract caller — same params)

Same `depositForBurn` call from a contract context, with the contract holding sufficient USDC balance + having approved the messenger:

- **Diagnostic probe contract:** `0xe4F6a70ab9eB591d557011c5A71A8bb8E3B913F6` (source: [CCTPProbe.sol](https://github.com/Yonkoo11/whaleindex/blob/master/contracts/src/probes/CCTPProbe.sol))
- **Failed tx (CCTPProbe.probe):** `0xa8e89e38…` and many earlier attempts
- **Failure mode:** `execution reverted` with **no error data** (no Error(string) selector, no custom error data).

### Isolated test sequence

Verified each step in isolation against the probe contract:

1. **Contract approve works:** `CCTPProbe.justApprove(usdc, messenger, 50000)` succeeded. Resulting `allowance(probe, messenger) = 50000`.
2. **Contract depositForBurn fails:** `CCTPProbe.justBurn(...)` with the probe holding USDC + having an approval to the messenger reverts silently.
3. **Allowance check is reached:** When the probe's allowance to the messenger is zero, we get a clean `"ERC20: transfer amount exceeds allowance"` error. When the allowance is set, depositForBurn proceeds and reverts somewhere internal with empty data.

### Hypothesis

A `msg.sender == tx.origin` check inside `depositForBurn`, or an undocumented contract allowlist on the TokenMessenger / TokenMinter. Every Circle Arc-related CCTP sample we found uses EOAs (TypeScript clients), never on-chain contracts as the source-side caller.

### Ask

1. Is contract-side `depositForBurn` supported on Arc Testnet today? If not, is it planned?
2. If a contract allowlist exists: how do we apply? Our RebalanceExecutor is at `0x2096B1FCad5d3d4303f1Ac3DABA4116c73B0D282` ([verified source](https://testnet.arcscan.app/address/0x2096b1fcad5d3d4303f1ac3daba4116c73b0d282)).
3. If the gate is `tx.origin == msg.sender`: please document it in the Arc CCTP page so future builders aren't surprised.
4. Alternative: is there a designated relayer / forwarder pattern (similar to ERC-2771) we should use instead?

### What we'd ship once unblocked

- Real CCTP V2 cross-chain settlement on every rebalance (currently using MockTokenMessenger as a stand-in so the rest of the flow demos end-to-end).
- Full sponsor depth credit for CCTP V2 in the Agora Agents Hackathon (Canteen × Circle × Arc).

Happy to provide any additional reproduction artifacts or screen-share a debugging session.

Thanks,
@Yonkoo11 — WhaleIndex
Repo: https://github.com/Yonkoo11/whaleindex
