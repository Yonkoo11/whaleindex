"""
Watchlist curation CLI.

Adding a whale is a one-line operation. The tool validates the address (basic
EVM format), optionally fetches their current position count + 30d realised
PnL from Hyperliquid, and writes the V2 watchlist with stable ordering.

Subcommands
-----------
    add <address> --label <name> [--source URL] [--tags tag1,tag2] [--notes "..."]
    list                                # pretty-print current watchlist
    validate                            # check every entry: format, HL activity
    refresh-metrics                     # re-fetch metrics for all entries
    refresh-metrics <address>           # re-fetch metrics for one entry
    remove <address>                    # drop one entry
    migrate                             # rewrite the file in V2 layout (no-op if already V2)

Usage
-----
    python -m agent.whale_curator add 0xABC... --label "Top Sharpe #1" \\
        --source https://hyperdash.info/trader/0xABC... \\
        --tags high-conviction,verified
    python -m agent.whale_curator refresh-metrics
    python -m agent.whale_curator list

Design notes
------------
- Metric refresh is opt-in. `add` accepts `--skip-refresh` for offline curation
  (when HL's API is unreachable or rate-limited).
- All HTTP calls have explicit timeouts and surface errors with the wallet
  in question. No silent failures.
- The CLI is the only writer; allocation_engine + selection_engine remain
  read-only on the watchlist.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.whale_schema import (
    SourceRef,
    WhaleEntry,
    WhaleMetrics,
    load_watchlist,
    save_watchlist,
    WATCHLIST_PATH,
    _utc_now_iso,
    _utc_today,
)
from agent.leaderboard_reader import (
    fetch_clearinghouse_state,
    fetch_metrics_window,
    parse_positions,
)

EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _checksum_or_lower(addr: str) -> str:
    """Return the address in checksummed form if possible, else lowercase."""
    if not EVM_ADDRESS_RE.match(addr):
        raise ValueError(f"Not an EVM address: {addr}")
    try:
        from eth_utils import to_checksum_address  # type: ignore
        return to_checksum_address(addr)
    except Exception:
        return addr.lower()


async def _fetch_metrics(wallet: str, window_days: int = 30) -> WhaleMetrics:
    """Fetch current position count + extended trading metrics from Hyperliquid."""
    async with httpx.AsyncClient() as client:
        state = await fetch_clearinghouse_state(client, wallet)
        metrics = await fetch_metrics_window(client, wallet, window_days)
    positions = parse_positions(wallet, state)
    return WhaleMetrics(
        pnl_30d_usd=metrics.pnl_usd,
        position_count_current=len(positions),
        last_metrics_refresh=_utc_now_iso(),
        sharpe_30d=metrics.sharpe,
        max_drawdown_pct=metrics.max_drawdown_pct,
        win_rate=metrics.win_rate,
        fill_count_30d=metrics.fill_count,
        volume_30d_usd=metrics.volume_usd,
    )


# --- subcommand impls -------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    entries = load_watchlist(WATCHLIST_PATH)
    if not entries:
        print("(watchlist is empty)")
        return 0
    print(f"{len(entries)} whales:")
    for e in entries:
        tags = (", ".join(e.tags)) if e.tags else "—"
        last_pnl = (f"${e.metrics.pnl_30d_usd:>+12,.0f}"
                    if e.metrics.last_metrics_refresh else "(no metrics)")
        print(f"  {e.wallet}  {e.label[:24]:24s}  pnl_30d={last_pnl}  pos={e.metrics.position_count_current:>2}  tags={tags}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    addr = _checksum_or_lower(args.address)
    entries = load_watchlist(WATCHLIST_PATH) if WATCHLIST_PATH.exists() else []

    if any(e.wallet.lower() == addr.lower() for e in entries):
        print(f"already present: {addr}", file=sys.stderr)
        return 2

    sources = [SourceRef(url=args.source, captured_at=_utc_today())] if args.source else []
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    entry = WhaleEntry(
        wallet=addr,
        label=args.label or "",
        added_at=_utc_today(),
        added_by=args.added_by or "",
        sources=sources,
        tags=tags,
        notes=args.notes or "",
    )

    if not args.skip_refresh:
        try:
            entry.metrics = asyncio.run(_fetch_metrics(addr, args.window_days))
            print(f"  metrics: pnl_30d=${entry.metrics.pnl_30d_usd:+,.2f}  "
                  f"positions={entry.metrics.position_count_current}")
        except Exception as e:
            print(f"  WARN: metric fetch failed ({e}); entry added without metrics", file=sys.stderr)

    entries.append(entry)
    save_watchlist(entries, WATCHLIST_PATH)
    print(f"added {addr} ({entry.label or '(no label)'})")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    addr = _checksum_or_lower(args.address)
    entries = load_watchlist(WATCHLIST_PATH)
    kept = [e for e in entries if e.wallet.lower() != addr.lower()]
    if len(kept) == len(entries):
        print(f"not found: {addr}", file=sys.stderr)
        return 2
    save_watchlist(kept, WATCHLIST_PATH)
    print(f"removed {addr}")
    return 0


def cmd_refresh_metrics(args: argparse.Namespace) -> int:
    entries = load_watchlist(WATCHLIST_PATH)
    targets = entries
    if args.address:
        addr = _checksum_or_lower(args.address)
        targets = [e for e in entries if e.wallet.lower() == addr.lower()]
        if not targets:
            print(f"not found: {addr}", file=sys.stderr)
            return 2

    async def _run():
        async with httpx.AsyncClient() as client:
            for e in targets:
                try:
                    state = await fetch_clearinghouse_state(client, e.wallet)
                    m = await fetch_metrics_window(client, e.wallet, args.window_days)
                    positions = parse_positions(e.wallet, state)
                    e.metrics = WhaleMetrics(
                        pnl_30d_usd=m.pnl_usd,
                        position_count_current=len(positions),
                        last_metrics_refresh=_utc_now_iso(),
                        sharpe_30d=m.sharpe,
                        max_drawdown_pct=m.max_drawdown_pct,
                        win_rate=m.win_rate,
                        fill_count_30d=m.fill_count,
                        volume_30d_usd=m.volume_usd,
                    )
                    print(f"  {e.wallet}  pnl_30d=${m.pnl_usd:+,.2f}  sharpe={m.sharpe:+.2f}  "
                          f"win_rate={m.win_rate*100:.0f}%  maxDD={m.max_drawdown_pct*100:.1f}%  "
                          f"fills={m.fill_count}  positions={len(positions)}")
                except Exception as ex:
                    print(f"  {e.wallet}  REFRESH FAILED: {ex}", file=sys.stderr)

    asyncio.run(_run())
    save_watchlist(entries, WATCHLIST_PATH)
    print(f"refreshed {len(targets)} whales")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    entries = load_watchlist(WATCHLIST_PATH)
    bad = []
    for e in entries:
        if not EVM_ADDRESS_RE.match(e.wallet):
            bad.append((e.wallet, "malformed address"))
            continue
        if not e.label:
            bad.append((e.wallet, "no label"))
        if not e.sources:
            bad.append((e.wallet, "no source URL"))
        if not e.metrics.last_metrics_refresh:
            bad.append((e.wallet, "no metrics ever refreshed"))

    if bad:
        print(f"{len(bad)} issues:")
        for wallet, issue in bad:
            print(f"  {wallet}  {issue}")
        return 1
    print(f"validated {len(entries)} whales: all OK")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """Load + save: forces V1 → V2 conversion (or no-op if already V2)."""
    entries = load_watchlist(WATCHLIST_PATH)
    save_watchlist(entries, WATCHLIST_PATH)
    print(f"migrated {len(entries)} whales to v2 layout at {WATCHLIST_PATH}")
    return 0


# Matches 0x-prefixed EVM addresses anywhere in a line. Used by import-urls
# to extract a wallet from a Hyperdash trader URL like:
#   https://hyperdash.info/trader/0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd
_ADDR_IN_LINE_RE = re.compile(r"0x[a-fA-F0-9]{40}")


def cmd_import_urls(args: argparse.Namespace) -> int:
    """
    Bulk-add whales from a text file containing Hyperdash URLs (one per line).

    Each line is parsed for an EVM address. Blank lines + lines beginning
    with '#' are skipped (so curators can annotate the file). When an
    address is found, the whole line becomes the source URL and the label
    is auto-derived from the URL's slug (or 'HL whale N' as a fallback).

    Default behavior is conservative: skip duplicates, skip lines without
    an address, refresh metrics for every successful add (unless
    --skip-refresh). Pass --label-prefix to control the auto-label.

    Example file (data/whales-import.txt):
        # top-10 by 30d Sharpe captured 2026-05-24
        https://hyperdash.info/trader/0xFef0a25EE2cE15E8B5DD8E5DD6F0e29e6f76EeBd
        https://hyperdash.info/trader/0xb01f6c44d28a0a3a1f10c5fde50e80c9b2c19d6f
        # below this line, addresses captured from asxn.xyz instead
        0xCcF3d1aCF799bAe67F6e354d685295557cF64761  some inline note

    Usage:
        python -m agent.whale_curator import-urls data/whales-import.txt
        python -m agent.whale_curator import-urls list.txt --skip-refresh --label-prefix "Top Sharpe"
    """
    path = Path(args.path)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 2

    existing = load_watchlist(WATCHLIST_PATH) if WATCHLIST_PATH.exists() else []
    existing_lower = {e.wallet.lower() for e in existing}

    added = 0
    skipped_dup = 0
    skipped_no_addr = 0
    failed = 0

    raw_lines = path.read_text().splitlines()
    next_idx = len(existing) + 1

    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ADDR_IN_LINE_RE.search(line)
        if not m:
            skipped_no_addr += 1
            continue
        addr = _checksum_or_lower(m.group(0))
        if addr.lower() in existing_lower:
            skipped_dup += 1
            continue

        source_url = line if line.startswith("http") else ""
        label = args.label_prefix + f" {next_idx}" if args.label_prefix else f"HL whale {next_idx}"

        entry = WhaleEntry(
            wallet=addr,
            label=label,
            added_at=_utc_today(),
            added_by=args.added_by or "",
            sources=[SourceRef(url=source_url, captured_at=_utc_today())] if source_url else [],
            tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
            notes=args.notes or "",
        )

        if not args.skip_refresh:
            try:
                entry.metrics = asyncio.run(_fetch_metrics(addr, args.window_days))
                print(f"  + {addr}  pnl_30d=${entry.metrics.pnl_30d_usd:+,.0f}  "
                      f"sharpe={entry.metrics.sharpe_30d:+.2f}  "
                      f"win={entry.metrics.win_rate*100:.0f}%  "
                      f"fills={entry.metrics.fill_count_30d}")
            except Exception as e:
                print(f"  + {addr}  (metric fetch failed: {e})", file=sys.stderr)
                failed += 1
        else:
            print(f"  + {addr}  (skipped metric refresh)")

        existing.append(entry)
        existing_lower.add(addr.lower())
        added += 1
        next_idx += 1

    save_watchlist(existing, WATCHLIST_PATH)
    print()
    print(f"summary: added={added}  duplicates_skipped={skipped_dup}  "
          f"no_address_skipped={skipped_no_addr}  metric_failures={failed}")
    print(f"now watching: {len(existing)} whales total")
    return 0 if added > 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="WhaleIndex watchlist curator")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a whale to the watchlist")
    p_add.add_argument("address")
    p_add.add_argument("--label", default="", help="human-readable name")
    p_add.add_argument("--source", default="", help="source URL (e.g. Hyperdash profile)")
    p_add.add_argument("--tags", default="", help="comma-separated tags")
    p_add.add_argument("--notes", default="", help="free-form notes")
    p_add.add_argument("--added-by", default="", help="who added it (defaults empty)")
    p_add.add_argument("--skip-refresh", action="store_true", help="don't hit HL API")
    p_add.add_argument("--window-days", type=int, default=30)
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove", help="remove a whale from the watchlist")
    p_rm.add_argument("address")
    p_rm.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="print current watchlist")
    p_list.set_defaults(func=cmd_list)

    p_val = sub.add_parser("validate", help="report data-quality issues")
    p_val.set_defaults(func=cmd_validate)

    p_ref = sub.add_parser("refresh-metrics", help="re-fetch HL metrics for all or one")
    p_ref.add_argument("address", nargs="?", default=None)
    p_ref.add_argument("--window-days", type=int, default=30)
    p_ref.set_defaults(func=cmd_refresh_metrics)

    p_mig = sub.add_parser("migrate", help="rewrite the file in V2 layout")
    p_mig.set_defaults(func=cmd_migrate)

    p_imp = sub.add_parser("import-urls", help="bulk-add whales from a text file of Hyperdash URLs or addresses")
    p_imp.add_argument("path", help="path to a text file: one URL or address per line, '#' for comments")
    p_imp.add_argument("--label-prefix", default="", help="auto-label prefix (e.g. 'Top Sharpe'); falls back to 'HL whale N'")
    p_imp.add_argument("--tags", default="", help="comma-separated tags applied to every imported entry")
    p_imp.add_argument("--notes", default="", help="free-form notes applied to every imported entry")
    p_imp.add_argument("--added-by", default="", help="who added it (defaults empty)")
    p_imp.add_argument("--skip-refresh", action="store_true", help="don't hit HL API per row")
    p_imp.add_argument("--window-days", type=int, default=30)
    p_imp.set_defaults(func=cmd_import_urls)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
