"""
ScorerAgent — ranks whales by a composite score.

Inputs:
  - whale_positions: list[WhalePosition]   current open positions per wallet
  - pnl_window:     dict[wallet, float]   30d realised PnL per wallet (USD)

Output:
  list[WhaleScore]  one per wallet in the watchlist, ordered by score desc.

Composite score (0-100, higher = better):
  - 60%  PnL component: rank-normalised 30d realised PnL.
  - 25%  Position-quality component: more positions = more conviction, capped.
  - 15%  Recency component: 1.0 if the wallet has any open position right now,
         0.0 otherwise (proxy for "still trading").

Score components are exposed in the output so the audit doc shows the math.

Notes:
  - This is a deterministic ranking, not a statistical estimator. A v2 scorer
    would use Sharpe or a t-stat on PnL — see ai/plan.md Phase B step.
  - When fewer than 2 whales have nonzero PnL, rank-normalisation degenerates;
    we fall back to a flat 50.0 PnL component (neither rewarded nor punished).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from agent.leaderboard_reader import WhalePosition


@dataclass
class ScoreComponents:
    pnl: float           # 0-100
    position_quality: float  # 0-100
    recency: float       # 0-100


@dataclass
class WhaleScore:
    wallet: str
    score: float         # 0-100, composite
    components: ScoreComponents
    reasoning: str       # one-line, human-readable

    raw_pnl_usd: float = 0.0
    raw_position_count: int = 0


@dataclass
class ScorerAgent:
    """Stateless. Could be a function, but a class makes the agent contract explicit."""
    pnl_weight: float = 0.60
    position_quality_weight: float = 0.25
    recency_weight: float = 0.15
    position_quality_cap: int = 5  # positions above this contribute the same as 5

    def __post_init__(self) -> None:
        s = self.pnl_weight + self.position_quality_weight + self.recency_weight
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"ScorerAgent weights must sum to 1.0 (got {s})")

    def score(
        self,
        wallets: list[str],
        positions: list[WhalePosition],
        pnl_window: dict[str, float],
    ) -> list[WhaleScore]:
        pos_count = _count_positions_per_wallet(wallets, positions)

        # PnL component: rank-normalised across the watchlist. Best -> 100, worst -> 0.
        pnl_ranked = sorted(wallets, key=lambda w: pnl_window.get(w, 0.0))
        n = len(pnl_ranked)
        nonzero_pnls = sum(1 for w in wallets if pnl_window.get(w, 0.0) != 0.0)

        if n == 0:
            return []
        if nonzero_pnls < 2:
            # Not enough signal; PnL component is neutral.
            pnl_comp = {w: 50.0 for w in wallets}
        else:
            pnl_comp = {}
            for rank, w in enumerate(pnl_ranked):
                pnl_comp[w] = (rank / (n - 1)) * 100.0 if n > 1 else 50.0

        out: list[WhaleScore] = []
        for w in wallets:
            pos = pos_count.get(w, 0)
            pq = min(pos, self.position_quality_cap) / self.position_quality_cap * 100.0
            recency = 100.0 if pos > 0 else 0.0
            pnl_c = pnl_comp[w]
            composite = (
                self.pnl_weight * pnl_c
                + self.position_quality_weight * pq
                + self.recency_weight * recency
            )

            pnl_val = pnl_window.get(w, 0.0)
            reasoning = (
                f"pnl_30d=${pnl_val:+,.0f} ({pnl_c:.0f}/100), "
                f"open_positions={pos} ({pq:.0f}/100), "
                f"active_now={'yes' if pos > 0 else 'no'} ({recency:.0f}/100)"
            )
            out.append(WhaleScore(
                wallet=w,
                score=round(composite, 2),
                components=ScoreComponents(pnl=round(pnl_c, 2), position_quality=round(pq, 2), recency=round(recency, 2)),
                reasoning=reasoning,
                raw_pnl_usd=pnl_val,
                raw_position_count=pos,
            ))

        return sorted(out, key=lambda s: -s.score)


def _count_positions_per_wallet(
    wallets: Iterable[str],
    positions: list[WhalePosition],
) -> dict[str, int]:
    counts = {w: 0 for w in wallets}
    for p in positions:
        if p.wallet in counts:
            counts[p.wallet] += 1
    return counts
