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
import json
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
    """Load the curated whale watchlist."""
    if not WATCHLIST_PATH.exists():
        raise FileNotFoundError(f"Watchlist missing: {WATCHLIST_PATH}")
    return json.loads(WATCHLIST_PATH.read_text())


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
