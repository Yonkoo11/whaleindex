"""
WhaleIndex Phase 1 orchestrator.

Pipeline:
  1. Read every whale in data/whales-hl.json concurrently from Hyperliquid's
     public clearinghouseState endpoint.
  2. Aggregate net notional per coin.
  3. Compute equal-weighted allocation across the top-5 coins.
  4. Print a rebalance plan (Phase 1 stops here; signing + submission is
     Phase 1c once an operator key is available in .env).

Run:
  python -m agent.main

Phase 1 acceptance: this script outputs a non-empty rebalance plan when at
least one watched whale has open positions.
"""

import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone

from leaderboard_reader import fetch_all_whales
from allocation_engine import compute_allocations


async def run(aum_usdc: float = 100_000.0) -> dict:
    positions = await fetch_all_whales()
    allocs = compute_allocations(positions, total_aum_usdc=aum_usdc)

    plan = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aum_usdc": aum_usdc,
        "whale_count": len({p.wallet for p in positions}),
        "position_count": len(positions),
        "allocations": [asdict(a) for a in allocs],
    }
    return plan


if __name__ == "__main__":
    plan = asyncio.run(run())
    print(json.dumps(plan, indent=2, default=str))
