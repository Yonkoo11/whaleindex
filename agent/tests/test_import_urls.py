"""Bulk-import-from-URLs CLI subcommand tests.

Uses a temp watchlist file + tmp input file so we don't touch the live
data/whales-hl.json. --skip-refresh avoids HL HTTP in CI.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent.whale_schema import WATCHLIST_PATH, load_watchlist


def _run_curator(argv: list[str], tmp_watchlist: Path) -> int:
    """Invoke the curator main() with WATCHLIST_PATH patched to a tmp file."""
    import agent.whale_curator as cur
    # Patch the module's two import paths that touch the watchlist.
    with patch.object(cur, "WATCHLIST_PATH", tmp_watchlist), \
         patch("agent.whale_schema.WATCHLIST_PATH", tmp_watchlist), \
         patch.object(sys, "argv", ["whale_curator"] + argv):
        return cur.main()


def _write(content: str) -> Path:
    p = Path(tempfile.mkdtemp()) / "input.txt"
    p.write_text(content)
    return p


def _tmp_watchlist() -> Path:
    return Path(tempfile.mkdtemp()) / "wl.json"


def test_import_extracts_addresses_from_urls() -> None:
    wl = _tmp_watchlist()
    src = _write("""
# top whales 2026-05-24
https://hyperdash.info/trader/0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd
https://hyperdash.info/trader/0xb01f6c44d28a0a3a1f10c5fde50e80c9b2c19d6f
""")
    rc = _run_curator(["import-urls", str(src), "--skip-refresh"], wl)
    assert rc == 0
    entries = load_watchlist(wl)
    assert len(entries) == 2
    wallets_lower = {e.wallet.lower() for e in entries}
    assert "0xfef0a25ee2ce15e8b5dd8e5dd6f0e29e6f76eebd" in wallets_lower
    assert "0xb01f6c44d28a0a3a1f10c5fde50e80c9b2c19d6f" in wallets_lower


def test_import_skips_duplicates() -> None:
    wl = _tmp_watchlist()
    src = _write("""
0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd
0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd
""")
    rc = _run_curator(["import-urls", str(src), "--skip-refresh"], wl)
    assert rc == 0  # added at least one
    entries = load_watchlist(wl)
    assert len(entries) == 1  # duplicate skipped


def test_import_skips_lines_without_address() -> None:
    wl = _tmp_watchlist()
    src = _write("""
not an address
some prose about whales
https://example.com/something-without-address
""")
    rc = _run_curator(["import-urls", str(src), "--skip-refresh"], wl)
    # No addresses found -> return 1 (added=0)
    assert rc == 1
    assert not wl.exists() or len(load_watchlist(wl)) == 0


def test_import_uses_label_prefix() -> None:
    wl = _tmp_watchlist()
    src = _write("0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd")
    rc = _run_curator(["import-urls", str(src), "--skip-refresh",
                       "--label-prefix", "Top Sharpe"], wl)
    assert rc == 0
    entries = load_watchlist(wl)
    assert "Top Sharpe" in entries[0].label


def test_import_inline_address_no_url() -> None:
    """Lines can be a bare address with an inline note (no URL)."""
    wl = _tmp_watchlist()
    src = _write("0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd  pulled from asxn.xyz")
    rc = _run_curator(["import-urls", str(src), "--skip-refresh"], wl)
    assert rc == 0
    entries = load_watchlist(wl)
    # Source is empty because the line didn't start with http
    assert entries[0].sources == []


def test_import_carries_tags_and_notes() -> None:
    wl = _tmp_watchlist()
    src = _write("https://hyperdash.info/trader/0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd")
    rc = _run_curator([
        "import-urls", str(src), "--skip-refresh",
        "--tags", "high-conviction,verified",
        "--notes", "from Sharpe top-3",
    ], wl)
    assert rc == 0
    e = load_watchlist(wl)[0]
    assert "high-conviction" in e.tags
    assert "verified" in e.tags
    assert e.notes == "from Sharpe top-3"
