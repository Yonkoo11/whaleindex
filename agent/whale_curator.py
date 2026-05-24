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
    fetch_pnl_window,
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
    """Fetch current position count + 30d realised PnL from Hyperliquid."""
    async with httpx.AsyncClient() as client:
        state = await fetch_clearinghouse_state(client, wallet)
        pnl = await fetch_pnl_window(client, wallet, window_days)
    positions = parse_positions(wallet, state)
    return WhaleMetrics(
        pnl_30d_usd=float(pnl),
        position_count_current=len(positions),
        last_metrics_refresh=_utc_now_iso(),
    )


# --- subcommand impls -------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    entries = load_watchlist()
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
    entries = load_watchlist() if WATCHLIST_PATH.exists() else []

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
    save_watchlist(entries)
    print(f"added {addr} ({entry.label or '(no label)'})")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    addr = _checksum_or_lower(args.address)
    entries = load_watchlist()
    kept = [e for e in entries if e.wallet.lower() != addr.lower()]
    if len(kept) == len(entries):
        print(f"not found: {addr}", file=sys.stderr)
        return 2
    save_watchlist(kept)
    print(f"removed {addr}")
    return 0


def cmd_refresh_metrics(args: argparse.Namespace) -> int:
    entries = load_watchlist()
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
                    pnl = await fetch_pnl_window(client, e.wallet, args.window_days)
                    positions = parse_positions(e.wallet, state)
                    e.metrics = WhaleMetrics(
                        pnl_30d_usd=float(pnl),
                        position_count_current=len(positions),
                        last_metrics_refresh=_utc_now_iso(),
                    )
                    print(f"  {e.wallet}  pnl_30d=${pnl:+,.2f}  positions={len(positions)}")
                except Exception as ex:
                    print(f"  {e.wallet}  REFRESH FAILED: {ex}", file=sys.stderr)

    asyncio.run(_run())
    save_watchlist(entries)
    print(f"refreshed {len(targets)} whales")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    entries = load_watchlist()
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
    entries = load_watchlist()
    save_watchlist(entries)
    print(f"migrated {len(entries)} whales to v2 layout at {WATCHLIST_PATH}")
    return 0


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

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
