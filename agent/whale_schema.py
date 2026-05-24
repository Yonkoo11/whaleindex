"""
WhaleIndex watchlist schema (v2) — typed dataclasses + read/write helpers.

V2 supersedes V1 (flat array of dicts) but stays backward-compatible: the loader
accepts either layout. Writers always emit V2.

V2 file layout:

    {
      "version": 2,
      "snapshot_at": "2026-05-24T11:30:00Z",
      "whales": [
        {
          "wallet": "0x...",
          "label": "Sahil A.",
          "added_at": "2026-05-24",
          "added_by": "yonko",
          "sources": [
            {"url": "https://hyperdash.info/trader/0x...", "captured_at": "2026-05-24"}
          ],
          "tags": ["high-conviction"],
          "notes": "Top-5 by 30d Sharpe on Hyperdash.",
          "metrics": {
            "pnl_30d_usd": 12345.67,
            "position_count_current": 5,
            "last_metrics_refresh": "2026-05-24T11:30:00Z"
          }
        }
      ]
    }

Stable sort: writers always sort by `added_at` then `wallet` so a re-write
of an unchanged list is a no-op diff.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
WATCHLIST_PATH = REPO_ROOT / "data" / "whales-hl.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class SourceRef:
    url: str
    captured_at: str  # YYYY-MM-DD


@dataclass
class WhaleMetrics:
    pnl_30d_usd: float = 0.0
    position_count_current: int = 0
    last_metrics_refresh: str = ""  # ISO8601, "" = never refreshed


@dataclass
class WhaleEntry:
    wallet: str                                 # checksummed 0x address
    label: str = ""
    added_at: str = ""                          # YYYY-MM-DD
    added_by: str = ""
    sources: list[SourceRef] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    metrics: WhaleMetrics = field(default_factory=WhaleMetrics)

    # --- conversions ----------------------------------------------------

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "wallet": self.wallet,
            "label": self.label,
            "added_at": self.added_at,
            "added_by": self.added_by,
            "sources": [asdict(s) for s in self.sources],
            "tags": list(self.tags),
            "notes": self.notes,
            "metrics": asdict(self.metrics),
        }

    @classmethod
    def from_jsonable(cls, d: dict[str, Any]) -> WhaleEntry:
        """Accepts either V1 (flat dict with wallet/label/source/_notes) or V2."""
        wallet = d["wallet"]
        # V1 single-source as a string -> V2 sources list
        v1_source = d.get("source")
        v2_sources = d.get("sources")
        if v2_sources:
            sources = [SourceRef(**s) for s in v2_sources]
        elif v1_source:
            sources = [SourceRef(url=str(v1_source), captured_at=d.get("last_verified", ""))]
        else:
            sources = []

        # V1's `_notes` -> V2's `notes`
        notes = d.get("notes", d.get("_notes", ""))

        # Metrics defaults if absent (V1 didn't have them).
        m = d.get("metrics") or {}
        metrics = WhaleMetrics(
            pnl_30d_usd=float(m.get("pnl_30d_usd", 0.0)),
            position_count_current=int(m.get("position_count_current", 0)),
            last_metrics_refresh=str(m.get("last_metrics_refresh", "")),
        )

        return cls(
            wallet=wallet,
            label=str(d.get("label", "")),
            added_at=str(d.get("added_at", d.get("last_verified", ""))),
            added_by=str(d.get("added_by", "")),
            sources=sources,
            tags=list(d.get("tags", [])),
            notes=str(notes),
            metrics=metrics,
        )


# --- file load/save ---------------------------------------------------------


def load_watchlist(path: Path = WATCHLIST_PATH) -> list[WhaleEntry]:
    """
    Read the watchlist from disk. Accepts V1 (flat array) or V2 (dict with
    'whales' key) shape transparently. Returns the entries sorted by
    (added_at, wallet) for deterministic downstream behaviour.
    """
    if not path.exists():
        raise FileNotFoundError(f"Watchlist missing: {path}")
    raw = json.loads(path.read_text())

    if isinstance(raw, list):
        # V1 layout
        entries = [WhaleEntry.from_jsonable(d) for d in raw]
    elif isinstance(raw, dict) and "whales" in raw:
        # V2 layout
        entries = [WhaleEntry.from_jsonable(d) for d in raw["whales"]]
    else:
        raise ValueError(f"Unrecognised watchlist shape in {path}")

    return sorted(entries, key=lambda w: (w.added_at, w.wallet.lower()))


def save_watchlist(entries: list[WhaleEntry], path: Path = WATCHLIST_PATH) -> None:
    """Atomic-ish write of the V2 layout. Stable order."""
    entries_sorted = sorted(entries, key=lambda w: (w.added_at, w.wallet.lower()))
    payload = {
        "version": 2,
        "snapshot_at": _utc_now_iso(),
        "whales": [e.to_jsonable() for e in entries_sorted],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)


# --- ergonomic shims --------------------------------------------------------


def watchlist_wallets(entries: list[WhaleEntry]) -> list[str]:
    """Backward-compatibility helper for consumers that just want addresses."""
    return [e.wallet for e in entries]


def watchlist_as_legacy_dicts(entries: list[WhaleEntry]) -> list[dict[str, Any]]:
    """
    Render as V1 flat-dict shape for the existing `leaderboard_reader.load_watchlist`
    consumers that grep `w["wallet"]`. Used during the migration window.
    """
    return [
        {
            "wallet": e.wallet,
            "label": e.label,
            "source": (e.sources[0].url if e.sources else ""),
            "last_verified": (e.sources[0].captured_at if e.sources else e.added_at),
            "_notes": e.notes,
        }
        for e in entries
    ]
