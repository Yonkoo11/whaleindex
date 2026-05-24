"""
Hyperliquid leaderboard reader.

Hyperliquid does NOT expose a public leaderboard endpoint, so we keep our own
watchlist of known whale wallets (sourced from hyperdash.info and on-chain
analytics) and query each one's live positions via the public clearinghouseState
endpoint.

Public API: POST https://api.hyperliquid.xyz/info
            body = {"type": "clearinghouseState", "user": "0x..."}

The response shape is documented at:
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
"""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
WATCHLIST_PATH = Path(__file__).parent.parent / "data" / "whales-hl.json"

# Per-venue watchlists. Each watchlist is a JSON array of {wallet, label, source, ...}.
# HL watchlist preserves the historic flat-array contract (no venue field needed).
WATCHLISTS: dict[str, Path] = {
    "hl": Path(__file__).parent.parent / "data" / "whales-hl.json",
    "drift": Path(__file__).parent.parent / "data" / "whales-drift.json",
}


@dataclass
class WhalePosition:
    wallet: str
    coin: str
    side: str            # "long" or "short"
    size: float          # absolute size in asset units (szi sign indicates direction)
    entry_price: float
    leverage: int
    notional_usd: float
    account_value: float
    fetched_at: int


async def fetch_clearinghouse_state(client: httpx.AsyncClient, wallet: str) -> dict[str, Any]:
    """Fetch the full clearinghouse state for one wallet. Returns raw API response."""
    body = {"type": "clearinghouseState", "user": wallet, "dex": ""}
    resp = await client.post(HL_INFO_URL, json=body, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def fetch_pnl_window(
    client: httpx.AsyncClient,
    wallet: str,
    window_days: int = 30,
) -> float:
    """Backward-compat shim: returns 30d realised PnL as a single float."""
    metrics = await fetch_metrics_window(client, wallet, window_days)
    return metrics.pnl_usd


@dataclass
class WindowMetrics:
    """Extended trading metrics over a rolling window.

    Computed directly from HL's userFillsByTime response:
      pnl_usd:       sum of closedPnl across all fills in the window
      sharpe:        annualised Sharpe (mean_daily_pnl / std_daily_pnl * sqrt(252)).
                     Zero if std=0 or fewer than 2 active days.
      max_drawdown_pct: peak-to-trough cumulative-PnL drawdown, expressed as a
                     fraction of the peak. Zero if no positive peak in window.
      win_rate:      fraction of fills with closedPnl > 0
      fill_count:    total fills in the window
      volume_usd:    sum of |size * px| across all fills
      window_days:   the window the metrics were computed against
    """
    pnl_usd: float
    sharpe: float
    max_drawdown_pct: float
    win_rate: float
    fill_count: int
    volume_usd: float
    window_days: int


def _compute_metrics_from_fills(fills: list[dict[str, Any]], window_days: int) -> WindowMetrics:
    """Deterministic metric computation. Pure function — testable without HL."""
    import math
    from collections import defaultdict

    if not fills:
        return WindowMetrics(
            pnl_usd=0.0, sharpe=0.0, max_drawdown_pct=0.0,
            win_rate=0.0, fill_count=0, volume_usd=0.0, window_days=window_days,
        )

    total_pnl = 0.0
    wins = 0
    volume = 0.0
    daily_pnl: dict[str, float] = defaultdict(float)
    cumulative_series: list[tuple[int, float]] = []  # (time_ms, cum_pnl)

    # Iterate in chronological order so the cumulative series is monotonic in time.
    sorted_fills = sorted(fills, key=lambda f: int(f.get("time", 0)))
    cum = 0.0
    for f in sorted_fills:
        try:
            pnl = float(f.get("closedPnl", "0") or "0")
        except (TypeError, ValueError):
            pnl = 0.0
        try:
            sz = abs(float(f.get("sz", "0") or "0"))
            px = abs(float(f.get("px", "0") or "0"))
        except (TypeError, ValueError):
            sz = px = 0.0

        t_ms = int(f.get("time", 0))
        day = time.strftime("%Y-%m-%d", time.gmtime(t_ms / 1000.0))
        daily_pnl[day] += pnl
        total_pnl += pnl
        volume += sz * px
        if pnl > 0:
            wins += 1
        cum += pnl
        cumulative_series.append((t_ms, cum))

    fill_count = len(sorted_fills)
    win_rate = wins / fill_count if fill_count else 0.0

    # Sharpe: daily-pnl distribution -> annualised.
    daily_values = list(daily_pnl.values())
    if len(daily_values) >= 2:
        mean = sum(daily_values) / len(daily_values)
        var = sum((x - mean) ** 2 for x in daily_values) / (len(daily_values) - 1)
        std = math.sqrt(var)
        sharpe = (mean / std) * math.sqrt(252.0) if std > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown over the running cumulative series.
    max_dd_pct = 0.0
    running_peak = 0.0
    for _, c in cumulative_series:
        if c > running_peak:
            running_peak = c
        if running_peak > 0:
            dd = (running_peak - c) / running_peak
            if dd > max_dd_pct:
                max_dd_pct = dd

    return WindowMetrics(
        pnl_usd=round(total_pnl, 2),
        sharpe=round(sharpe, 3),
        max_drawdown_pct=round(max_dd_pct, 4),
        win_rate=round(win_rate, 3),
        fill_count=fill_count,
        volume_usd=round(volume, 2),
        window_days=window_days,
    )


async def fetch_metrics_window(
    client: httpx.AsyncClient,
    wallet: str,
    window_days: int = 30,
) -> WindowMetrics:
    """
    Full extended-metrics fetch for one wallet over the trailing window.

    One HTTP call against HL's userFillsByTime. The metric computation is
    a pure function — see _compute_metrics_from_fills for the implementation.
    """
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - window_days * 86_400 * 1000
    body = {
        "type": "userFillsByTime",
        "user": wallet,
        "startTime": start_ms,
        "endTime": now_ms,
        "aggregateByTime": False,
    }
    resp = await client.post(HL_INFO_URL, json=body, timeout=15.0)
    resp.raise_for_status()
    fills = resp.json() if isinstance(resp.json(), list) else []
    return _compute_metrics_from_fills(fills, window_days)


async def fetch_pnl_window_all(
    wallets: list[str],
    window_days: int = 30,
) -> dict[str, float]:
    """Concurrent realised-PnL fetch for every wallet. Returns {wallet: pnl_usd}."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_pnl_window(client, w, window_days) for w in wallets),
            return_exceptions=True,
        )
    out: dict[str, float] = {}
    for wallet, r in zip(wallets, results):
        if isinstance(r, BaseException):
            print(f"WARN: PnL fetch failed for {wallet}: {r}")
            out[wallet] = 0.0
        else:
            out[wallet] = float(r)
    return out


def parse_positions(wallet: str, state: dict[str, Any]) -> list[WhalePosition]:
    """Extract structured positions from a clearinghouseState response."""
    out: list[WhalePosition] = []
    fetched_at = int(time.time())
    account_value = float(state.get("marginSummary", {}).get("accountValue", "0"))

    for asset_pos in state.get("assetPositions", []):
        pos = asset_pos.get("position", {})
        szi = float(pos.get("szi", "0"))
        if szi == 0:
            continue
        out.append(WhalePosition(
            wallet=wallet,
            coin=pos["coin"],
            side="long" if szi > 0 else "short",
            size=abs(szi),
            entry_price=float(pos["entryPx"]),
            leverage=int(pos["leverage"]["value"]),
            notional_usd=float(pos["positionValue"]),
            account_value=account_value,
            fetched_at=fetched_at,
        ))
    return out


def load_watchlist() -> list[dict[str, Any]]:
    """
    Load the curated whale watchlist as legacy-shaped dicts.

    Delegates to agent.whale_schema.load_watchlist (which understands both V1
    and V2 layouts) and renders the result as `[{wallet, label, source,
    last_verified, _notes}]` so existing consumers don't have to change.
    """
    # Import inside function to avoid a circular import (whale_schema imports
    # nothing from this module, but whale_curator imports from us).
    from agent.whale_schema import (
        load_watchlist as _load_typed,
        watchlist_as_legacy_dicts,
    )
    return watchlist_as_legacy_dicts(_load_typed(WATCHLIST_PATH))


async def fetch_all_whales() -> list[WhalePosition]:
    """Read every whale in the watchlist concurrently."""
    watchlist = load_watchlist()
    async with httpx.AsyncClient() as client:
        tasks = [fetch_clearinghouse_state(client, w["wallet"]) for w in watchlist]
        states = await asyncio.gather(*tasks, return_exceptions=True)

    positions: list[WhalePosition] = []
    for entry, state in zip(watchlist, states):
        if isinstance(state, BaseException):
            print(f"WARN: failed to read {entry['wallet']}: {state}")
            continue
        assert isinstance(state, dict)
        positions.extend(parse_positions(entry["wallet"], state))
    return positions


# ---------------------------------------------------------------------------
# Multi-venue extension. HL path above is unchanged; Drift is stubbed.
# ---------------------------------------------------------------------------

async def fetch_drift_positions() -> list[WhalePosition]:
    """
    Read Drift maker positions. STUB — returns empty list until a Drift fetcher lands.

    Real implementation will hit https://dlob.drift.trade/users/{wallet}/positions
    (or the corresponding @drift-labs/sdk RPC call) and map to WhalePosition.
    Drift uses Solana base58 wallet IDs, not 0x EVM addresses, so this path
    cannot share fetch_clearinghouse_state.
    """
    return []


async def fetch_positions(venue: str) -> list[WhalePosition]:
    """Dispatch to the right venue reader. Unknown venues raise."""
    if venue == "hl":
        return await fetch_all_whales()
    if venue == "drift":
        return await fetch_drift_positions()
    raise ValueError(f"Unknown venue: {venue!r}. Known: {sorted(WATCHLISTS)}")


async def fetch_all_venues(venues: list[str] | None = None) -> list[WhalePosition]:
    """Read every configured venue concurrently and merge positions."""
    venues = venues or list(WATCHLISTS)
    results = await asyncio.gather(*(fetch_positions(v) for v in venues), return_exceptions=True)
    out: list[WhalePosition] = []
    for venue, result in zip(venues, results):
        if isinstance(result, BaseException):
            print(f"WARN: {venue} venue failed: {result}")
            continue
        assert isinstance(result, list)
        out.extend(result)
    return out


if __name__ == "__main__":
    positions = asyncio.run(fetch_all_whales())
    by_coin: dict[str, float] = {}
    for p in positions:
        signed_notional = p.notional_usd if p.side == "long" else -p.notional_usd
        by_coin[p.coin] = by_coin.get(p.coin, 0) + signed_notional

    print(f"Read {len(positions)} positions from {len({p.wallet for p in positions})} whales.")
    print("Aggregate net notional (USD) by coin:")
    for coin, net in sorted(by_coin.items(), key=lambda kv: -abs(kv[1])):
        print(f"  {coin:8s}  {net:+15,.0f}")
