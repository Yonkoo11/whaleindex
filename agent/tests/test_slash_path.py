"""Tests for the slash-aware selection_engine path (V3 WhaleAttestation wiring).

Uses an in-memory mock for the bonded-check + a temp baseline file so we
don't touch the live data/whale-rankings.json.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from agent.selection_engine import (
    WhaleScore,
    evaluate,
    pending_slashes,
    decay_severity_to_slash_bps,
)


def _tmp_rankings() -> Path:
    return Path(tempfile.mkdtemp()) / "rankings.json"


# --- decay_severity_to_slash_bps -------------------------------------------

def test_slash_bps_zero_for_tiny_decay() -> None:
    assert decay_severity_to_slash_bps(0) == 0
    assert decay_severity_to_slash_bps(1) == 0


def test_slash_bps_scales_with_decay() -> None:
    assert decay_severity_to_slash_bps(2) == 500     # 5%
    assert decay_severity_to_slash_bps(3) == 500
    assert decay_severity_to_slash_bps(4) == 1500    # 15%
    assert decay_severity_to_slash_bps(5) == 1500
    assert decay_severity_to_slash_bps(6) == 3000    # 30%
    assert decay_severity_to_slash_bps(10) == 3000
    assert decay_severity_to_slash_bps(11) == 5000   # cap
    assert decay_severity_to_slash_bps(100) == 5000


def test_slash_bps_respects_max_cap() -> None:
    # If contract's max is 3000 (30%), we never exceed it.
    assert decay_severity_to_slash_bps(11, max_slash_bps=3000) == 3000
    assert decay_severity_to_slash_bps(5, max_slash_bps=1000) == 1000  # clamped


# --- evaluate() with is_bonded_fn ------------------------------------------

def test_bonded_whale_with_decay_becomes_slash_pending() -> None:
    """A bonded whale crossing the decay threshold should be tagged for slash."""
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    # Seed a baseline where 0xA is rank 1, 0xB is rank 2, 0xC is rank 3.
    # Then today 0xA crashes to rank 3 (decay = 2 places past threshold).
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        # First run: seed baseline.
        evaluate([
            WhaleScore("0xA", score=100.0),
            WhaleScore("0xB", score=50.0),
            WhaleScore("0xC", score=10.0),
        ], decay_threshold=1, update_baseline=True)

        # Second run: 0xA crashed to last place (rank 3, prior was 1, decay=2).
        # 0xA is bonded, 0xB is not. Expect 0xA -> slash_pending, 0xB -> keep.
        bonded = {"0xA"}
        decisions = evaluate(
            [
                WhaleScore("0xA", score=5.0),    # now worst
                WhaleScore("0xB", score=100.0),  # now best
                WhaleScore("0xC", score=50.0),
            ],
            decay_threshold=1,
            update_baseline=False,
            is_bonded_fn=lambda w: w in bonded,
        )

    by_wallet = {d.wallet: d for d in decisions}
    a = by_wallet["0xA"]
    assert a.verdict == "slash_pending", f"got {a.verdict}: {a.reason}"
    assert a.slash_bps == 500  # decay=2 → 5%
    assert a.decay_places == 2


def test_unbonded_whale_with_decay_stays_evict_decay() -> None:
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        evaluate([
            WhaleScore("0xA", score=100.0),
            WhaleScore("0xB", score=50.0),
            WhaleScore("0xC", score=10.0),
        ], decay_threshold=1, update_baseline=True)

        decisions = evaluate(
            [
                WhaleScore("0xA", score=5.0),
                WhaleScore("0xB", score=100.0),
                WhaleScore("0xC", score=50.0),
            ],
            decay_threshold=1,
            update_baseline=False,
            is_bonded_fn=lambda w: False,  # nobody is bonded
        )

    by_wallet = {d.wallet: d for d in decisions}
    assert by_wallet["0xA"].verdict == "evict_decay"
    assert by_wallet["0xA"].slash_bps == 0


def test_is_bonded_adapter_failure_falls_back_to_evict_decay() -> None:
    """An exception from the adapter must not crash the pipeline."""
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        evaluate([
            WhaleScore("0xA", score=100.0),
            WhaleScore("0xB", score=50.0),
            WhaleScore("0xC", score=10.0),
        ], decay_threshold=1, update_baseline=True)

        def adapter_explodes(_w: str) -> bool:
            raise RuntimeError("RPC down")

        decisions = evaluate(
            [
                WhaleScore("0xA", score=5.0),
                WhaleScore("0xB", score=100.0),
                WhaleScore("0xC", score=50.0),
            ],
            decay_threshold=1,
            update_baseline=False,
            is_bonded_fn=adapter_explodes,
        )

    by_wallet = {d.wallet: d for d in decisions}
    # 0xA crossed threshold but adapter failed → falls back to evict_decay.
    assert by_wallet["0xA"].verdict == "evict_decay"
    assert "is_bonded check failed" in by_wallet["0xA"].reason


def test_pending_slashes_filters_correctly() -> None:
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        evaluate([
            WhaleScore("0xA", score=100.0),
            WhaleScore("0xB", score=50.0),
            WhaleScore("0xC", score=10.0),
        ], decay_threshold=1, update_baseline=True)

        decisions = evaluate(
            [
                WhaleScore("0xA", score=5.0),     # decay 2 → slash 500
                WhaleScore("0xB", score=100.0),   # keep
                WhaleScore("0xC", score=50.0),    # keep
            ],
            decay_threshold=1,
            update_baseline=False,
            is_bonded_fn=lambda w: w == "0xA",
        )

    s = pending_slashes(decisions)
    assert len(s) == 1
    assert s[0].wallet == "0xA"
    assert s[0].slash_bps == 500


def test_no_bonded_fn_means_no_slash_pending() -> None:
    """When is_bonded_fn is None, behavior matches the V2 path exactly."""
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        evaluate([
            WhaleScore("0xA", score=100.0),
            WhaleScore("0xB", score=50.0),
        ], decay_threshold=1, update_baseline=True)

        decisions = evaluate(
            [
                WhaleScore("0xA", score=5.0),
                WhaleScore("0xB", score=100.0),
            ],
            decay_threshold=1,
            update_baseline=False,
        )

    assert all(d.verdict != "slash_pending" for d in decisions)
    assert all(d.slash_bps == 0 for d in decisions)


def test_severe_decay_caps_at_max_slash_bps() -> None:
    rankings = _tmp_rankings()
    rankings.parent.mkdir(parents=True, exist_ok=True)
    with patch("agent.selection_engine.RANKINGS_PATH", rankings):
        # 12 whales, 0xA at rank 1 initially, then crashes to rank 12 (decay=11).
        seed = [WhaleScore(f"0x{chr(65+i)}{chr(65+i)}", score=100.0 - i)
                for i in range(12)]
        evaluate(seed, decay_threshold=1, update_baseline=True)

        # Flip 0xAA from best to worst — decay = 11 places.
        crashed = [WhaleScore(f"0x{chr(65+i)}{chr(65+i)}", score=float(i)) for i in range(12)]
        crashed[0] = WhaleScore("0xAA", score=-100.0)  # worst now
        # but actually we need 0xAA to be at end of sorted-by-score, so:
        crashed = sorted(crashed, key=lambda s: -s.score)
        # ensure 0xAA is at the bottom:
        crashed = [s for s in crashed if s.wallet != "0xAA"] + [WhaleScore("0xAA", score=-100.0)]

        decisions = evaluate(
            crashed,
            decay_threshold=1,
            update_baseline=False,
            is_bonded_fn=lambda w: w == "0xAA",
        )

    by_wallet = {d.wallet: d for d in decisions}
    a = by_wallet["0xAA"]
    assert a.verdict == "slash_pending"
    # Decay >= 11 → max_slash_bps = 5000
    assert a.slash_bps == 5000
