# WhaleIndex — State Design (data architecture for UI)

Scope: full product = (1) landing hero, (2) live read-only dashboard, (3) buyer flow (connect / buy / redeem / holdings).
Color mode: dark-only. All numbers tabular-nums.

---

## 1. Top-level app states

| State | Trigger | UI consequence |
|---|---|---|
| `boot` | first paint | skeletons everywhere, hero shows shimmer |
| `rpc_ok` | provider responds | data fills in, refresh badge counts down |
| `rpc_fail` | both primary+fallback RPC dead | inline error band, retry button, rest of page frozen-but-visible |
| `wallet_disconnected` | default | buyer flow shows "Connect wallet" CTA; dashboard fully usable |
| `wallet_wrong_network` | connected, chainId ≠ 5042002 | "Switch to Arc Testnet" button (auto-switch attempt per global rule) |
| `wallet_connected` | connected + right chain | holdings panel populates; buy/redeem enabled |

Dashboard (read) NEVER depends on wallet. Buyer flow is the only wallet-gated surface.

---

## 2. Read entities (no wallet needed)

### 2.1 Protocol state — `NAVOracle` + `IndexToken`
- `nav` (uint256, 6dp USDC), `isFresh` (bool), `updatedAt` (unix), `maxDeltaBps`
- `sharePrice` (6dp), `totalSupply` (18dp WHALE)
- States: `loading` → `fresh` (green) | `stale` (amber, show last-update) | `never` (no update yet)
- Edge: `totalSupply == 0` → "no shares minted yet (treasury-seeded testnet)" empty copy, not "0".

### 2.2 Latest rebalance — `RebalanceExecutor.AllocationDecided` + tx receipt
- `cid` (bytes32), `whaleCount`, `reportedAt`, `txHash`, `blockTimestamp`
- derived: `settlementSec` (block.ts − reportedAt), `gasUsdc` (gasUsed×gasPrice, 18dp native), `ageSec`
- optional `Routed` event in same tx → `routedAmount`, `destinationDomain`; else "off-chain CCTP" label
- States: `loading` → `has_rebalance` | `none_in_window` (searched ~24h, nothing) → honest empty.

### 2.3 Reasoning doc — fetched from `allocations/<cid>.json`
- `decision.chosen_proposal`, `decision.coordinator_reasoning`, `decision.human_reasoning`
- `decision.multi_agent_audit.{scorer.scores[], allocator.proposals[], risk.verdicts[]}`
- States: `loading` → `rich` (real audit) | `thin` (demo doc, audit empty — show "demo run" pill) | `unreachable` (CID not on Pages yet).
- **Critical for design:** must look intentional whether audit is rich OR empty. A "demo run" badge distinguishes synthetic from real, never hides it.

### 2.4 Attestation — `WhaleAttestation`
- per-wallet `bondAmount`, `isBonded`; events `Bonded`, `Slashed(wallet, amount, slashBps, evidenceCid)`
- derived: `totalBonded`, `bondedCount`, `slashCount`, `totalSlashed`, `latestSlash`
- States: `loading` → `has_bonds` | `no_bonds` (0 staked — "no whales bonded yet" honest empty, NOT "$0") ; slashes: `none` (positive framing: "every bonded whale stayed within threshold") | `has_slashes`.
- Edge to avoid looking broken: if `bondedCount==0 && slashCount>0` (current demo reality) → label the slash as "demo/test slash" explicitly.

### 2.5 Verified contracts — static from deployment json
- name → address → Arcscan link + copy button. Includes real-CCTP reference address with note.

---

## 3. Write entities (wallet-gated buyer flow) — NET NEW

### 3.1 User position — `IndexToken.balanceOf` + `USDC.balanceOf`
- `whaleBalance` (18dp), `usdcBalance` (6dp), derived `positionValueUsdc = whaleBalance × sharePrice`
- States: `loading` → `has_position` | `no_position` (connected but 0 WHALE — show "You don't hold WHALE yet").

### 3.2 Buy flow state machine (USDC → WHALE)
```
idle
 → input_amount        (validate: >0, ≤ usdcBalance; show est. shares = amount/sharePrice)
 → checking_allowance
 → needs_approval ─→ approving ─→ approved
 → buying            (IndexToken.buy / mint)
 → confirming        (wait receipt, show settlement timer — Arc sub-second is the flex)
 → success           (show shares received + tx link + new position) → auto-return to idle after 4s
 → error             (revert reason inline near button; keep amount; retry)
```
- Disable button during approving/buying/confirming. Inline feedback near trigger, NOT toast.
- Optimistic: show "settling on Arc…" with live ms counter; Arc finality makes this feel instant.

### 3.3 Redeem flow state machine (WHALE → USDC)
- Mirror of buy: `input_amount` (≤ whaleBalance, est. USDC = shares×sharePrice) → buying becomes `redeeming` → success shows USDC returned.
- Shared component with buy; mode toggle (Buy / Redeem segmented control).

### 3.4 Connection sub-states
- `connect` (button) → `connecting` (spinner) → `wrong_network` (auto-switch attempt → fallback button) → `connected` (show short addr + balance + disconnect).
- Auto network switch to chain 5042002 per global rule.

---

## 4. Global refresh model
- Read entities auto-refresh every 15s; manual refresh button; "updated Ns ago · next in Ms" indicator.
- Write actions trigger an immediate read-refresh on success (don't wait for the 15s tick).
- All event scans chunked (9k-block windows, ~24h lookback) — public RPC caps getLogs at 10k.

---

## 5. Surfaces → which states each must design for

| Surface | Loading | Empty | Error | Live |
|---|---|---|---|---|
| Hero status line | shimmer | "no rebalance yet" | (inherits rpc_fail band) | full story line |
| Latest rebalance | skeleton ×3 | "none in ~24h window" | read-failed note | amount/latency/cost |
| Agent reasoning | "loading doc…" | "demo run" pill OR "no run yet" | "doc not reachable yet" | 4-agent trace |
| Bonded whales | skeleton | "no whales bonded yet" | read-failed | totals + table |
| Holdings (wallet) | skeleton | "you don't hold WHALE yet" | read-failed | balance + value |
| Buy/Redeem | n/a | "connect wallet" gate | revert reason inline | amount→confirm→success |
| Contracts | "loading…" | n/a | n/a | addr list + copy |

Every empty state must read as intentional and honest (distinguish demo vs real), never as a bug.
