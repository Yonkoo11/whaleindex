"""Schema roundtrip + backward-compat tests for the watchlist."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agent.whale_schema import (
    SourceRef,
    WhaleEntry,
    WhaleMetrics,
    load_watchlist,
    save_watchlist,
    watchlist_as_legacy_dicts,
)


def _tmp_path() -> Path:
    return Path(tempfile.mkdtemp()) / "whales.json"


def test_v1_flat_array_loads() -> None:
    """Old V1 layout (flat array of dicts) loads transparently."""
    path = _tmp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([
        {
            "wallet": "0xCcF3d1aCF799bAe67F6e354d685295557cF64761",
            "label": "HL whale 2",
            "source": "https://hyperdash.info/leaderboard",
            "last_verified": "2026-05-17",
            "_notes": "Placeholder",
        },
    ]))
    entries = load_watchlist(path)
    assert len(entries) == 1
    e = entries[0]
    assert e.wallet == "0xCcF3d1aCF799bAe67F6e354d685295557cF64761"
    assert e.label == "HL whale 2"
    assert len(e.sources) == 1
    assert e.sources[0].url == "https://hyperdash.info/leaderboard"
    assert e.sources[0].captured_at == "2026-05-17"
    assert e.notes == "Placeholder"


def test_v2_dict_layout_loads() -> None:
    path = _tmp_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "version": 2,
        "snapshot_at": "2026-05-24T00:00:00Z",
        "whales": [
            {
                "wallet": "0xCcF3d1aCF799bAe67F6e354d685295557cF64761",
                "label": "Top Sharpe #1",
                "added_at": "2026-05-24",
                "added_by": "yonko",
                "sources": [{"url": "https://hyperdash.info/x", "captured_at": "2026-05-24"}],
                "tags": ["high-conviction", "verified"],
                "notes": "Pulled from Hyperdash top-30.",
                "metrics": {
                    "pnl_30d_usd": 123456.78,
                    "position_count_current": 5,
                    "last_metrics_refresh": "2026-05-24T00:00:00Z",
                },
            },
        ],
    }))
    entries = load_watchlist(path)
    assert len(entries) == 1
    e = entries[0]
    assert e.label == "Top Sharpe #1"
    assert e.tags == ["high-conviction", "verified"]
    assert e.metrics.pnl_30d_usd == 123456.78
    assert e.metrics.position_count_current == 5


def test_save_then_load_roundtrip_preserves_everything() -> None:
    path = _tmp_path()
    original = [
        WhaleEntry(
            wallet="0xCcF3d1aCF799bAe67F6e354d685295557cF64761",
            label="trader-A",
            added_at="2026-05-20",
            added_by="yonko",
            sources=[SourceRef(url="https://hyperdash.info/A", captured_at="2026-05-20")],
            tags=["A"],
            notes="note-A",
            metrics=WhaleMetrics(pnl_30d_usd=100.0, position_count_current=2,
                                 last_metrics_refresh="2026-05-21T00:00:00Z"),
        ),
        WhaleEntry(
            wallet="0x9A89e02b0b6F1aaF6c5dC8B69D6e7Ad1eF1Cf671",
            label="trader-B",
            added_at="2026-05-18",
            added_by="yonko",
            sources=[],
            tags=[],
            notes="",
            metrics=WhaleMetrics(),
        ),
    ]
    save_watchlist(original, path)
    reloaded = load_watchlist(path)
    assert len(reloaded) == 2
    # Stable sort by (added_at, wallet) — trader-B (2026-05-18) ranks first.
    assert reloaded[0].label == "trader-B"
    assert reloaded[1].label == "trader-A"
    # All fields preserved on the more-populated entry.
    a = reloaded[1]
    assert a.tags == ["A"]
    assert a.notes == "note-A"
    assert a.metrics.pnl_30d_usd == 100.0
    assert a.sources[0].url == "https://hyperdash.info/A"


def test_legacy_dicts_shim_preserves_existing_consumers() -> None:
    """leaderboard_reader.load_watchlist returns these; existing callers grep ['wallet']."""
    entries = [
        WhaleEntry(
            wallet="0xCcF3d1aCF799bAe67F6e354d685295557cF64761",
            label="X",
            added_at="2026-05-20",
            sources=[SourceRef(url="https://h.io/x", captured_at="2026-05-20")],
            notes="hello",
        ),
    ]
    legacy = watchlist_as_legacy_dicts(entries)
    assert legacy[0]["wallet"] == "0xCcF3d1aCF799bAe67F6e354d685295557cF64761"
    assert legacy[0]["label"] == "X"
    assert legacy[0]["source"] == "https://h.io/x"
    assert legacy[0]["last_verified"] == "2026-05-20"
    assert legacy[0]["_notes"] == "hello"


def test_save_is_idempotent_with_stable_order() -> None:
    """Save → load → save again should produce the same `whales` array (modulo snapshot_at)."""
    path = _tmp_path()
    original = [
        WhaleEntry(wallet="0xCcF3d1aCF799bAe67F6e354d685295557cF64761", label="Z", added_at="2026-05-20"),
        WhaleEntry(wallet="0x9A89e02b0b6F1aaF6c5dC8B69D6e7Ad1eF1Cf671", label="A", added_at="2026-05-20"),
    ]
    save_watchlist(original, path)
    first_payload = json.loads(path.read_text())
    save_watchlist(load_watchlist(path), path)
    second_payload = json.loads(path.read_text())
    # snapshot_at differs by timestamp but the whales array must be identical.
    assert first_payload["whales"] == second_payload["whales"]
    # And sort order by wallet (both same added_at) keeps 0x9A before 0xCc.
    assert first_payload["whales"][0]["wallet"].startswith("0x9A")
    assert first_payload["whales"][1]["wallet"].startswith("0xCc")
