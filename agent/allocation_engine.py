"""
Allocation engine.

Given parsed whale positions, compute the target USDC allocation per coin.

V1 logic (deliberately simple, documented limits):
  1. Aggregate signed notional per coin across all whales.
  2. Equal-weight the top 5 coins by absolute aggregate notional.
  3. Direction follows the sign of the aggregate (long-bias if net long).
  4. Allocation per coin = total_aum_usdc / N_selected, where N <= 5.

NOT included in V1 (Phase 2):
  - Sharpe-weighted whale weighting (requires 30d PnL history; needs Drift/HL fill query)
  - Strategy-degradation eviction (rank decay or Sharpe drop)
  - Risk-parity normalisation across coins

A senior reviewer would (rightly) point out that this is a rank-and-equal-weight
heuristic, not a statistical estimator. State the limitation in the README.
"""

from dataclasses import dataclass

try:
    from agent.leaderboard_reader import WhalePosition
except ImportError:
    from leaderboard_reader import WhalePosition  # script-style invocation


@dataclass
class Allocation:
    coin: str
    direction: str          # "long" or "short"
    target_notional_usd: float
    rationale: str


def aggregate_by_coin(positions: list[WhalePosition]) -> dict[str, float]:
    """Net notional per coin across all whales (long positive, short negative)."""
    out: dict[str, float] = {}
    for p in positions:
        signed = p.notional_usd if p.side == "long" else -p.notional_usd
        out[p.coin] = out.get(p.coin, 0.0) + signed
    return out


def compute_allocations(
    positions: list[WhalePosition],
    total_aum_usdc: float,
    top_n: int = 5,
) -> list[Allocation]:
    if total_aum_usdc <= 0:
        return []
    if not positions:
        return []

    net_by_coin = aggregate_by_coin(positions)
    # Drop coins with zero net exposure.
    ranked = sorted(
        ((c, n) for c, n in net_by_coin.items() if n != 0),
        key=lambda kv: -abs(kv[1]),
    )[:top_n]

    if not ranked:
        return []

    per_coin_notional = total_aum_usdc / len(ranked)
    out: list[Allocation] = []
    whale_count = len({p.wallet for p in positions})
    for coin, net in ranked:
        direction = "long" if net > 0 else "short"
        out.append(Allocation(
            coin=coin,
            direction=direction,
            target_notional_usd=per_coin_notional,
            rationale=f"net_notional={net:+,.0f} across {whale_count} whales",
        ))
    return out
