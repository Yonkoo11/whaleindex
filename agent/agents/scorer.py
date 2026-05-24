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

from agent.leaderboard_reader import WhalePosition, WindowMetrics


@dataclass
class ScoreComponents:
    pnl: float                    # 0-100
    position_quality: float       # 0-100
    recency: float                # 0-100
    # Extended (B2) — only populated when WindowMetrics provided. Default 0.0
    # so the JSON shape stays stable across the simple/extended modes.
    sharpe: float = 0.0
    drawdown: float = 0.0
    win_rate: float = 0.0


@dataclass
class WhaleScore:
    wallet: str
    score: float                  # 0-100, composite
    components: ScoreComponents
    reasoning: str                # one-line, human-readable

    raw_pnl_usd: float = 0.0
    raw_position_count: int = 0
    raw_sharpe: float = 0.0
    raw_drawdown_pct: float = 0.0
    raw_win_rate: float = 0.0


@dataclass
class ScorerAgent:
    """Stateless. Could be a function, but a class makes the agent contract explicit.

    Two weight schedules:
      - simple (PnL + position_quality + recency, weights summing to 1.0).
        Used when only a `pnl_window` dict is provided.
      - extended (adds sharpe, drawdown, win_rate). Used when a
        `metrics_by_wallet: dict[str, WindowMetrics]` is provided.

    Extended weights default: pnl 30 / sharpe 25 / drawdown 15 / win_rate 10 /
                             position_quality 10 / recency 10.
    """
    pnl_weight: float = 0.60
    position_quality_weight: float = 0.25
    recency_weight: float = 0.15
    position_quality_cap: int = 5

    # Extended-mode weights. Used iff `metrics_by_wallet` is passed to score().
    ext_pnl_weight: float = 0.30
    ext_sharpe_weight: float = 0.25
    ext_drawdown_weight: float = 0.15
    ext_win_rate_weight: float = 0.10
    ext_position_quality_weight: float = 0.10
    ext_recency_weight: float = 0.10

    def __post_init__(self) -> None:
        s = self.pnl_weight + self.position_quality_weight + self.recency_weight
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"ScorerAgent simple-mode weights must sum to 1.0 (got {s})")
        s_ext = (
            self.ext_pnl_weight + self.ext_sharpe_weight + self.ext_drawdown_weight
            + self.ext_win_rate_weight + self.ext_position_quality_weight + self.ext_recency_weight
        )
        if abs(s_ext - 1.0) > 1e-6:
            raise ValueError(f"ScorerAgent extended-mode weights must sum to 1.0 (got {s_ext})")

    def score(
        self,
        wallets: list[str],
        positions: list[WhalePosition],
        pnl_window: dict[str, float] | None = None,
        metrics_by_wallet: dict[str, WindowMetrics] | None = None,
    ) -> list[WhaleScore]:
        """
        Score every wallet 0-100.

        Modes:
          metrics_by_wallet provided -> EXTENDED scoring (richer composite).
          metrics_by_wallet None     -> SIMPLE scoring from pnl_window.

        Backward-compat: passing only pnl_window keeps the V1 contract.
        """
        if metrics_by_wallet is not None:
            return self._score_extended(wallets, positions, metrics_by_wallet)
        if pnl_window is None:
            pnl_window = {}
        return self._score_simple(wallets, positions, pnl_window)

    # --- simple (PnL-only) -------------------------------------------------

    def _score_simple(
        self,
        wallets: list[str],
        positions: list[WhalePosition],
        pnl_window: dict[str, float],
    ) -> list[WhaleScore]:
        pos_count = _count_positions_per_wallet(wallets, positions)
        n = len(wallets)
        if n == 0:
            return []

        pnl_ranked = sorted(wallets, key=lambda w: pnl_window.get(w, 0.0))
        nonzero_pnls = sum(1 for w in wallets if pnl_window.get(w, 0.0) != 0.0)
        if nonzero_pnls < 2:
            pnl_comp = {w: 50.0 for w in wallets}
        else:
            pnl_comp = {w: (rank / (n - 1)) * 100.0 if n > 1 else 50.0
                        for rank, w in enumerate(pnl_ranked)}

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
                components=ScoreComponents(
                    pnl=round(pnl_c, 2),
                    position_quality=round(pq, 2),
                    recency=round(recency, 2),
                ),
                reasoning=reasoning,
                raw_pnl_usd=pnl_val,
                raw_position_count=pos,
            ))
        return sorted(out, key=lambda s: -s.score)

    # --- extended (PnL + Sharpe + drawdown + win-rate) ---------------------

    def _score_extended(
        self,
        wallets: list[str],
        positions: list[WhalePosition],
        metrics_by_wallet: dict[str, WindowMetrics],
    ) -> list[WhaleScore]:
        pos_count = _count_positions_per_wallet(wallets, positions)
        n = len(wallets)
        if n == 0:
            return []

        # Rank-normalised PnL component.
        def rank_norm(values: list[float], reverse: bool = False) -> list[float]:
            if n < 2:
                return [50.0] * n
            ordered = sorted(range(n), key=lambda i: values[i], reverse=reverse)
            ranks = [0.0] * n
            for rank, idx in enumerate(ordered):
                ranks[idx] = (rank / (n - 1)) * 100.0
            return ranks

        pnl_vals = [metrics_by_wallet.get(w, _zero_metrics()).pnl_usd for w in wallets]
        sharpe_vals = [metrics_by_wallet.get(w, _zero_metrics()).sharpe for w in wallets]
        # Lower drawdown is better — invert by passing reverse=True so the LOWEST drawdown gets rank 0,
        # which after normalisation puts the worst drawdown at 100. We want the OPPOSITE: low drawdown -> high score.
        # So we rank ascending (low first) and then invert: score = 100 - rank_norm.
        dd_vals = [metrics_by_wallet.get(w, _zero_metrics()).max_drawdown_pct for w in wallets]
        dd_ranks = rank_norm(dd_vals, reverse=False)  # 0 = best (lowest dd)
        dd_comp = [100.0 - r for r in dd_ranks]       # invert -> 100 = best

        pnl_comp = rank_norm(pnl_vals, reverse=False)
        sharpe_comp = rank_norm(sharpe_vals, reverse=False)

        out: list[WhaleScore] = []
        for i, w in enumerate(wallets):
            m = metrics_by_wallet.get(w, _zero_metrics())
            pos = pos_count.get(w, 0)
            pq = min(pos, self.position_quality_cap) / self.position_quality_cap * 100.0
            recency = 100.0 if pos > 0 else 0.0
            wr_comp = m.win_rate * 100.0  # already 0-1

            composite = (
                self.ext_pnl_weight * pnl_comp[i]
                + self.ext_sharpe_weight * sharpe_comp[i]
                + self.ext_drawdown_weight * dd_comp[i]
                + self.ext_win_rate_weight * wr_comp
                + self.ext_position_quality_weight * pq
                + self.ext_recency_weight * recency
            )
            reasoning = (
                f"pnl=${m.pnl_usd:+,.0f} ({pnl_comp[i]:.0f}/100), "
                f"sharpe={m.sharpe:+.2f} ({sharpe_comp[i]:.0f}/100), "
                f"maxDD={m.max_drawdown_pct*100:.1f}% ({dd_comp[i]:.0f}/100), "
                f"win_rate={m.win_rate*100:.0f}% ({wr_comp:.0f}/100), "
                f"open_positions={pos} ({pq:.0f}/100), "
                f"active_now={'yes' if pos > 0 else 'no'} ({recency:.0f}/100)"
            )
            out.append(WhaleScore(
                wallet=w,
                score=round(composite, 2),
                components=ScoreComponents(
                    pnl=round(pnl_comp[i], 2),
                    position_quality=round(pq, 2),
                    recency=round(recency, 2),
                    sharpe=round(sharpe_comp[i], 2),
                    drawdown=round(dd_comp[i], 2),
                    win_rate=round(wr_comp, 2),
                ),
                reasoning=reasoning,
                raw_pnl_usd=m.pnl_usd,
                raw_position_count=pos,
                raw_sharpe=m.sharpe,
                raw_drawdown_pct=m.max_drawdown_pct,
                raw_win_rate=m.win_rate,
            ))
        return sorted(out, key=lambda s: -s.score)


def _zero_metrics() -> WindowMetrics:
    return WindowMetrics(
        pnl_usd=0.0, sharpe=0.0, max_drawdown_pct=0.0,
        win_rate=0.0, fill_count=0, volume_usd=0.0, window_days=0,
    )


def _count_positions_per_wallet(
    wallets: Iterable[str],
    positions: list[WhalePosition],
) -> dict[str, int]:
    counts = {w: 0 for w in wallets}
    for p in positions:
        if p.wallet in counts:
            counts[p.wallet] += 1
    return counts
