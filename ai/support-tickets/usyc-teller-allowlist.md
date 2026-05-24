# USYC Teller — Allowlist request for WhaleIndex on Arc Testnet

**Submit at:** https://usyc.dev.hashnote.com/ (look for a Support / Contact link, or open a ticket through the portal)
**Alternative:** Email Hashnote support / Circle USYC support, mentioning Arc Testnet integration

---

## Subject

Allowlist request — WhaleIndex protocol on Arc Testnet for USYC mint/redeem

## Body

Hi USYC team,

We're requesting allowlist access on Arc Testnet so we can integrate USYC into our protocol's idle-cash management.

### Project

**WhaleIndex** — a USDC-denominated index on Arc Testnet that mirrors top Hyperliquid whale traders. Built for the [Agora Agents Hackathon](https://agora.thecanteenapp.com) (Canteen × Circle × Arc, May 2026).

Public repo: https://github.com/Yonkoo11/whaleindex
Phase 1 evidence: rebalance tx `0xa8e89e389f7328e044808483aca8d225cf699907c5b0bc20d28689465a4dd0ee` settled in 1.13s on Arc Testnet.

### Use case for USYC

Between rebalance cycles, idle USDC sits in our `USYCParkVault` contract. We want to deposit that idle USDC into USYC via the Teller (`0x9fdF14c5B14173D74C08Af27AebFf39240dC105A`) to earn the underlying yield, then redeem back to USDC at the next rebalance cycle.

This delivers the "yield on idle cash" leg of our index design and addresses RFB 06's traction metric of "performance vs raw leader average (risk-adjusted)" — without USYC, an index that holds USDC has a permanent yield drag vs the trader benchmarks.

### Addresses to allowlist

The contract that will be calling Teller `mint` / `redeem`:

- **USYCParkVault:** `0xE8682ca1cE90A6be3BD91A01Bf3e39c19543521A`
- **Source:** https://testnet.arcscan.app/address/0xe8682ca1ce90a6be3bd91a01bf3e39c19543521a (verified)

Owner / operator wallet (for the initial bootstrap mint, if a wallet allowlist is also required):

- **Operator:** `0xf9946775891a24462cD4ec885d0D4E2675C84355`

### Expected flow

```
RebalanceExecutor.rebalance(...)
  └─ USYCParkVault.park(usdcAmount)
        └─ teller.mint(usdcAmount)         # USDC -> USYC
```

Reverse on unpark.

### Volume / scale

Testnet-only for now. Per-call sizes during testing: 0.1 – 1 USDC. We're not asking for a production allowlist.

### Ask

1. Approve `0xE8682ca1cE90A6be3BD91A01Bf3e39c19543521A` (and `0xf9946775891a24462cD4ec885d0D4E2675C84355` if a wallet allowlist applies separately) for testnet USYC mint/redeem on Arc Testnet.
2. If the process requires KYC even for testnet: please point us to the right form so we can complete it.
3. Documentation of the Teller's exact mint / redeem function signatures would also help — the Teller proxy at `0x9fdF14c5B14173D74C08Af27AebFf39240dC105A` doesn't expose the standard `paused()` / `minimumDepositAmount()` introspection that we tried.

Once allowlisted, we'll redeploy `USYCParkVault` against the real USYC instead of the mock we're using today (`0x86df318Ff4356682Da819516bd05B9873f3b8F07`).

Thanks,
@Yonkoo11 — WhaleIndex
GitHub: https://github.com/Yonkoo11/whaleindex
