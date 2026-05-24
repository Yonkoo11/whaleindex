"""
AllocatorAgent — proposes a SLATE of competing allocations.

Inputs:
  - scores: list[WhaleScore]  (from ScorerAgent, sorted by score desc)
  - positions: list[WhalePosition]  (the survivors' open positions)
  - aum_usdc: float           total dollars to allocate

Output:
  list[AllocationProposal]    one per strategy variant

Three proposals always built (when feasible):
  1. equal_weight       — top-N coins by aggregate notional, equal weight
  2. score_weighted     — coins weighted by their backing whales' summed score
  3. kelly_bounded      — score_weighted but capped at MAX_WEIGHT per coin

The RiskAgent picks (or vetoes) downstream. Surfacing multiple proposals
makes the audit log richer than "one number from one rule."
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.leaderboard_reader import WhalePosition
from agent.allocation_engine import Allocation, aggregate_by_coin
from agent.agents.scorer import WhaleScore


@dataclass
class AllocationProposal:
    name: str                         # "equal_weight" | "score_weighted" | "kelly_bounded"
    allocations: list[Allocation]
    total_usdc: float
    reasoning: str
    weighting_method: str             # short tag for the audit doc


@dataclass
class AllocatorAgent:
    top_n_coins: int = 5
    kelly_max_weight: float = 0.40    # no single coin > 40% of AUM

    def propose(
        self,
        scores: list[WhaleScore],
        positions: list[WhalePosition],
        aum_usdc: float,
    ) -> list[AllocationProposal]:
        if aum_usdc <= 0 or not positions:
            return []

        # Score map for downstream weighting.
        score_map = {s.wallet: s.score for s in scores}

        equal = self._equal_weight(positions, aum_usdc)
        scored = self._score_weighted(positions, score_map, aum_usdc)
        kelly = self._kelly_bounded(positions, score_map, aum_usdc)

        return [p for p in (equal, scored, kelly) if p is not None and p.allocations]

    # --- strategies ---------------------------------------------------------

    def _equal_weight(self, positions: list[WhalePosition], aum: float) -> AllocationProposal | None:
        net = aggregate_by_coin(positions)
        ranked = sorted(
            ((c, n) for c, n in net.items() if n != 0),
            key=lambda kv: -abs(kv[1]),
        )[: self.top_n_coins]
        if not ranked:
            return None
        per = aum / len(ranked)
        allocations = [
            Allocation(
                coin=c,
                direction="long" if n > 0 else "short",
                target_notional_usd=per,
                rationale=f"equal-weight; net_notional={n:+,.0f}",
            )
            for c, n in ranked
        ]
        return AllocationProposal(
            name="equal_weight",
            allocations=allocations,
            total_usdc=aum,
            reasoning=f"top-{len(ranked)} coins by |aggregate notional|, equal-weighted",
            weighting_method="equal-weight",
        )

    def _score_weighted(
        self,
        positions: list[WhalePosition],
        score_map: dict[str, float],
        aum: float,
    ) -> AllocationProposal | None:
        # Per-coin signed notional, but weighted by the producing whale's score.
        weighted: dict[str, float] = {}
        weight_seen: dict[str, float] = {}
        for p in positions:
            s = score_map.get(p.wallet, 0.0)
            signed = (p.notional_usd if p.side == "long" else -p.notional_usd) * (s / 100.0)
            weighted[p.coin] = weighted.get(p.coin, 0.0) + signed
            weight_seen[p.coin] = weight_seen.get(p.coin, 0.0) + (s / 100.0)
        ranked = sorted(
            ((c, n) for c, n in weighted.items() if n != 0),
            key=lambda kv: -abs(kv[1]),
        )[: self.top_n_coins]
        if not ranked:
            return None
        total_weight = sum(abs(n) for _, n in ranked)
        if total_weight <= 0:
            return None
        allocations: list[Allocation] = []
        for c, n in ranked:
            share = abs(n) / total_weight
            allocations.append(Allocation(
                coin=c,
                direction="long" if n > 0 else "short",
                target_notional_usd=aum * share,
                rationale=f"score-weighted; share={share*100:.1f}%; weighted_notional={n:+,.0f}",
            ))
        return AllocationProposal(
            name="score_weighted",
            allocations=allocations,
            total_usdc=aum,
            reasoning="per-coin score-weighted notional, normalised to AUM",
            weighting_method="score-weighted",
        )

    def _kelly_bounded(
        self,
        positions: list[WhalePosition],
        score_map: dict[str, float],
        aum: float,
    ) -> AllocationProposal | None:
        base = self._score_weighted(positions, score_map, aum)
        if base is None:
            return None
        # Cap any allocation at kelly_max_weight; redistribute the excess
        # proportionally to the uncapped allocations (deterministic).
        max_per = aum * self.kelly_max_weight
        capped = [a for a in base.allocations if a.target_notional_usd > max_per]
        uncapped = [a for a in base.allocations if a.target_notional_usd <= max_per]
        if not capped:
            return AllocationProposal(
                name="kelly_bounded",
                allocations=base.allocations,
                total_usdc=aum,
                reasoning=f"score-weighted; no single allocation exceeded the {self.kelly_max_weight*100:.0f}% cap",
                weighting_method="kelly-bounded",
            )

        excess = sum(a.target_notional_usd - max_per for a in capped)
        # Cap the capped ones.
        for a in capped:
            a.target_notional_usd = max_per
            a.rationale = f"kelly-capped at {self.kelly_max_weight*100:.0f}% of AUM"
        # Redistribute excess proportionally among uncapped.
        if uncapped:
            uncapped_total = sum(a.target_notional_usd for a in uncapped) or 1.0
            for a in uncapped:
                share = a.target_notional_usd / uncapped_total
                a.target_notional_usd += excess * share

        return AllocationProposal(
            name="kelly_bounded",
            allocations=base.allocations,
            total_usdc=aum,
            reasoning=f"score-weighted, capped at {self.kelly_max_weight*100:.0f}%/coin, excess redistributed",
            weighting_method="kelly-bounded",
        )
