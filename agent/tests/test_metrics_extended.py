"""B2: extended-metric computation + extended-mode scorer tests.

The metric computation is a PURE function (`_compute_metrics_from_fills`)
that takes a list of HL-fill-shaped dicts. We test it offline with synthetic
fills — no HL HTTP dependency.
"""

from __future__ import annotations

import math

from agent.leaderboard_reader import (
    WindowMetrics,
    WhalePosition,
    _compute_metrics_from_fills,
)
from agent.agents.scorer import ScorerAgent


def _fill(time_ms: int, pnl: float, sz: float = 1.0, px: float = 50_000.0) -> dict:
    return {"time": time_ms, "closedPnl": str(pnl), "sz": str(sz), "px": str(px)}


# --- _compute_metrics_from_fills -------------------------------------------

def test_empty_fills_returns_zeros() -> None:
    m = _compute_metrics_from_fills([], window_days=30)
    assert m.pnl_usd == 0.0
    assert m.sharpe == 0.0
    assert m.max_drawdown_pct == 0.0
    assert m.win_rate == 0.0
    assert m.fill_count == 0
    assert m.volume_usd == 0.0


def test_pnl_is_sum_of_closed_pnl() -> None:
    fills = [
        _fill(1_700_000_000_000, 100.0),
        _fill(1_700_086_400_000, -30.0),
        _fill(1_700_172_800_000, 50.0),
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert m.pnl_usd == 120.0
    assert m.fill_count == 3


def test_win_rate_counts_positive_pnl() -> None:
    fills = [
        _fill(1, 10.0),
        _fill(2, -5.0),
        _fill(3, 20.0),
        _fill(4, 0.0),  # zero is NOT a win
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    # 2 wins out of 4 = 50%
    assert m.win_rate == 0.5


def test_max_drawdown_runs_against_cumulative_peak() -> None:
    # Cumulative: 100, 200 (peak), 150, 80 (max dd from 200 = 120/200 = 60%), 100
    fills = [
        _fill(1, 100.0),
        _fill(2, 100.0),
        _fill(3, -50.0),
        _fill(4, -70.0),
        _fill(5, 20.0),
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert abs(m.max_drawdown_pct - 0.6) < 1e-3


def test_drawdown_zero_when_pnl_only_positive() -> None:
    fills = [_fill(i, 50.0) for i in range(1, 6)]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert m.max_drawdown_pct == 0.0


def test_sharpe_zero_with_constant_daily_pnl() -> None:
    # Same pnl every day -> std=0 -> Sharpe=0.
    fills = [
        _fill(int(d * 86_400 * 1000), 10.0) for d in range(1, 8)
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert m.sharpe == 0.0


def test_sharpe_positive_when_avg_positive_with_variance() -> None:
    # Day 1: +20, Day 2: +5, Day 3: +15 -> positive mean, positive variance -> positive Sharpe.
    fills = [
        _fill(86_400_000, 20.0),
        _fill(172_800_000, 5.0),
        _fill(259_200_000, 15.0),
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert m.sharpe > 0
    # Sanity: should be roughly (mean / std) * sqrt(252).
    mean = (20 + 5 + 15) / 3
    var = ((20 - mean) ** 2 + (5 - mean) ** 2 + (15 - mean) ** 2) / 2
    expected = (mean / math.sqrt(var)) * math.sqrt(252)
    assert abs(m.sharpe - round(expected, 3)) < 0.01


def test_volume_uses_abs_size_times_price() -> None:
    fills = [
        _fill(1, 0.0, sz=2.0, px=50_000.0),  # 100K
        _fill(2, 0.0, sz=-1.0, px=50_000.0), # abs -> 50K
    ]
    m = _compute_metrics_from_fills(fills, window_days=30)
    assert m.volume_usd == 150_000.0


# --- ScorerAgent extended mode --------------------------------------------

def _pos(wallet: str, coin: str) -> WhalePosition:
    return WhalePosition(
        wallet=wallet, coin=coin, side="long", size=1.0,
        entry_price=50_000.0, leverage=5, notional_usd=5000.0,
        account_value=50_000.0, fetched_at=1,
    )


def test_extended_scorer_uses_sharpe() -> None:
    wallets = ["0xHIGH", "0xMID", "0xLOW"]
    positions = [_pos(w, "BTC") for w in wallets]
    metrics = {
        "0xHIGH": WindowMetrics(pnl_usd=1000.0, sharpe=3.0, max_drawdown_pct=0.05,
                                 win_rate=0.7, fill_count=10, volume_usd=10000, window_days=30),
        "0xMID":  WindowMetrics(pnl_usd=500.0,  sharpe=1.0, max_drawdown_pct=0.20,
                                 win_rate=0.5, fill_count=10, volume_usd=10000, window_days=30),
        "0xLOW":  WindowMetrics(pnl_usd=100.0,  sharpe=0.1, max_drawdown_pct=0.40,
                                 win_rate=0.3, fill_count=10, volume_usd=10000, window_days=30),
    }
    out = ScorerAgent().score(wallets, positions, metrics_by_wallet=metrics)
    # HIGH has best PnL + best Sharpe + lowest drawdown + best win-rate -> top.
    assert out[0].wallet == "0xHIGH"
    assert out[-1].wallet == "0xLOW"


def test_extended_scorer_components_populated() -> None:
    wallets = ["0xA", "0xB"]
    positions = [_pos("0xA", "BTC")]
    metrics = {
        "0xA": WindowMetrics(pnl_usd=100, sharpe=2.0, max_drawdown_pct=0.1,
                              win_rate=0.6, fill_count=5, volume_usd=1000, window_days=30),
        "0xB": WindowMetrics(pnl_usd=50,  sharpe=1.0, max_drawdown_pct=0.2,
                              win_rate=0.4, fill_count=5, volume_usd=1000, window_days=30),
    }
    out = ScorerAgent().score(wallets, positions, metrics_by_wallet=metrics)
    top = out[0]
    # All extended components populated (non-default).
    assert top.components.sharpe > 0
    assert top.components.drawdown > 0
    assert top.components.win_rate > 0
    # Raw values preserved for the audit doc.
    assert top.raw_sharpe in (1.0, 2.0)


def test_extended_scorer_drawdown_inverted_correctly() -> None:
    """Lower drawdown must score higher on the drawdown component."""
    wallets = ["0xLOWDD", "0xHIGHDD"]
    positions = [_pos(w, "BTC") for w in wallets]
    # Same PnL, Sharpe, win-rate; only drawdown differs.
    metrics = {
        "0xLOWDD":  WindowMetrics(pnl_usd=100, sharpe=1.0, max_drawdown_pct=0.05,
                                   win_rate=0.5, fill_count=10, volume_usd=1000, window_days=30),
        "0xHIGHDD": WindowMetrics(pnl_usd=100, sharpe=1.0, max_drawdown_pct=0.50,
                                   win_rate=0.5, fill_count=10, volume_usd=1000, window_days=30),
    }
    out = ScorerAgent().score(wallets, positions, metrics_by_wallet=metrics)
    by_wallet = {s.wallet: s for s in out}
    assert by_wallet["0xLOWDD"].components.drawdown > by_wallet["0xHIGHDD"].components.drawdown


def test_simple_mode_still_works_backward_compat() -> None:
    """The old `score(wallets, positions, pnl_window)` path must keep working."""
    wallets = ["0xA", "0xB"]
    positions = [_pos("0xA", "BTC")]
    pnl_window = {"0xA": 1000.0, "0xB": -500.0}
    out = ScorerAgent().score(wallets, positions, pnl_window=pnl_window)
    assert out[0].wallet == "0xA"
    assert out[-1].wallet == "0xB"
    # Extended components default to 0 in simple mode.
    assert out[0].components.sharpe == 0.0
