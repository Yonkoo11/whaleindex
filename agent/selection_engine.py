"""
Strategy degradation detector.

A whale is only useful while their strategy is producing alpha. When a previously
top-ranked wallet starts performing in the middle of the pack, we want to evict
them from the watchlist before the index passively follows them down.

Approach (deliberately simple — see Limitations below):

  1. For each whale, score recent realised PnL over a fixed window (default 30d).
  2. Rank whales by that score (highest score = rank 1).
  3. Persist the ranking to data/whale-rankings.json with a timestamp.
  4. On the NEXT eval, compare current rank vs. the prior persisted rank.
  5. Evict any whale whose rank has decayed by more than `decay_threshold` places.

Inputs
------
The eval takes a list of `WhaleScore(wallet, score)` tuples. The score source is
deliberately abstracted: Phase 1 wires this against Hyperliquid's userFillsByTime
endpoint (cumulative realised PnL over the window). Phase 2 swaps in a
Sharpe-style risk-adjusted measure.

Limitations
-----------
- This is rank-based decay, not a statistical estimator of alpha. A whale with
  consistently mediocre but slightly improving PnL would NOT trigger eviction.
- The window length and decay threshold are heuristics, not derived from a
  power analysis. A more rigorous approach would compute a t-statistic on
  PnL vs. a benchmark and evict only when |t| < threshold. Phase 2 work.
- No correction for survivorship bias in the prior baseline.
- If the same whale is missing from the new ranking (no recent trades), the
  detector flags them as "stale" rather than "decayed". Operator decides.

Operator surface
----------------
Run once per allocation cycle, BEFORE compute_allocations. Pass the surviving
watchlist downstream so the allocation engine never sees decayed whales.

CLI
---
    python -m agent.selection_engine --window-days 30 --decay-threshold 2
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RANKINGS_PATH = REPO_ROOT / "data" / "whale-rankings.json"


@dataclass
class WhaleScore:
    wallet: str
    score: float       # realised PnL over the window, in USD


@dataclass
class DecayDecision:
    wallet: str
    prior_rank: int | None       # None if not seen before
    current_rank: int | None     # None if missing from new ranking
    decay_places: int | None     # current - prior; None if either side missing
    verdict: str                 # "keep" | "evict_decay" | "evict_stale" | "new"
    reason: str


def _rank_scores(scores: list[WhaleScore]) -> dict[str, int]:
    """Rank whales by score desc. Returns {wallet: rank}, rank 1 = best."""
    ordered = sorted(scores, key=lambda s: -s.score)
    return {w.wallet: i + 1 for i, w in enumerate(ordered)}


def load_baseline() -> dict[str, int]:
    """Load the prior persisted ranking, or empty dict if first run."""
    if not RANKINGS_PATH.exists():
        return {}
    raw = json.loads(RANKINGS_PATH.read_text())
    return {wallet: int(rank) for wallet, rank in raw.get("ranks", {}).items()}


def save_ranking(ranks: dict[str, int]) -> None:
    """Persist a ranking snapshot. Caller passes the NEW ranking."""
    payload = {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "ranks": ranks,
    }
    RANKINGS_PATH.write_text(json.dumps(payload, indent=2))


def evaluate(
    scores: list[WhaleScore],
    decay_threshold: int = 2,
    update_baseline: bool = True,
) -> list[DecayDecision]:
    """
    Compare current scores against the persisted baseline and return per-whale
    decisions. By default, the new ranking is saved as the next baseline.

    Pass `update_baseline=False` to dry-run without overwriting state.
    """
    baseline = load_baseline()
    current = _rank_scores(scores)

    decisions: list[DecayDecision] = []
    seen_in_current = set(current)

    for wallet, current_rank in current.items():
        prior_rank = baseline.get(wallet)
        if prior_rank is None:
            decisions.append(DecayDecision(
                wallet=wallet,
                prior_rank=None,
                current_rank=current_rank,
                decay_places=None,
                verdict="new",
                reason="first appearance in ranking",
            ))
            continue

        decay = current_rank - prior_rank   # positive = got worse
        if decay > decay_threshold:
            decisions.append(DecayDecision(
                wallet=wallet,
                prior_rank=prior_rank,
                current_rank=current_rank,
                decay_places=decay,
                verdict="evict_decay",
                reason=f"rank decay {decay} > threshold {decay_threshold}",
            ))
        else:
            decisions.append(DecayDecision(
                wallet=wallet,
                prior_rank=prior_rank,
                current_rank=current_rank,
                decay_places=decay,
                verdict="keep",
                reason=f"rank decay {decay} within threshold",
            ))

    # Whales who were in the baseline but disappeared from the new ranking.
    for wallet, prior_rank in baseline.items():
        if wallet in seen_in_current:
            continue
        decisions.append(DecayDecision(
            wallet=wallet,
            prior_rank=prior_rank,
            current_rank=None,
            decay_places=None,
            verdict="evict_stale",
            reason="no recent trades — fell out of ranking",
        ))

    if update_baseline:
        save_ranking(current)

    return decisions


def survivors(decisions: list[DecayDecision]) -> list[str]:
    """Wallets the operator should keep allocating to."""
    return [d.wallet for d in decisions if d.verdict in ("keep", "new")]


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=30,
                        help="Realised-PnL window. Currently informational; "
                             "the real fetcher must respect it.")
    parser.add_argument("--decay-threshold", type=int, default=2,
                        help="Evict whales whose rank dropped by more than this many places.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not overwrite the baseline ranking.")
    args = parser.parse_args()

    # Synthetic scores so the CLI runs end-to-end before the HL fill-fetcher lands.
    # Real wiring: pass scores derived from agent.leaderboard_reader.fetch_pnl_window().
    demo_scores = [
        WhaleScore(wallet="0x9A89e02b0b6F1aaF6c5dC8B69D6e7Ad1eF1Cf671", score=120_000.0),
        WhaleScore(wallet="0xCcF3d1aCF799bAe67F6e354d685295557cF64761", score=80_000.0),
        WhaleScore(wallet="0x2068F22b91dF98AB3a04D67BC2A2B4C8c5cF3D1E", score=15_000.0),
    ]

    decisions = evaluate(
        demo_scores,
        decay_threshold=args.decay_threshold,
        update_baseline=not args.dry_run,
    )

    print(f"Evaluated {len(decisions)} whales (window={args.window_days}d, "
          f"decay_threshold={args.decay_threshold}, dry_run={args.dry_run}):")
    for d in decisions:
        print(f"  {d.wallet[:10]}...  {d.verdict:13s}  {d.reason}")
    print()
    keep = survivors(decisions)
    print(f"Survivors (keep allocating): {len(keep)} wallets")
    print(json.dumps([asdict(d) for d in decisions], indent=2))


if __name__ == "__main__":
    _main()
