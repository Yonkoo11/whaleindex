"""
RiskAgent — accepts or vetoes each AllocationProposal against policy bounds.

The on-chain RebalanceExecutor enforces `maxSingleMove` + `dailyCap`. That's
*spending* policy. RiskAgent adds *portfolio* policy — properties of the
proposed allocation, not the size of the move:

  - max_single_coin_pct       no single coin > N% of AUM
  - max_long_short_imbalance  |sum(long) - sum(short)| / aum <= N
  - min_coin_count            at least N coins for diversification
  - max_zero_weight_threshold reject if any allocation < threshold (dust)

Each proposal gets a verdict: accept, accept_with_adjustment, or veto.
If accept_with_adjustment, the agent emits a tweaked AllocationProposal
(e.g., drops dust coins, redistributes). Coordinator picks from
the accepted set.

Why surface adjustments instead of silently mutating?
  The audit document records both the original and the adjustment so the
  reader sees what the risk agent changed and why.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from agent.agents.allocator import AllocationProposal


@dataclass
class RiskPolicy:
    max_single_coin_pct: float = 0.50      # 50% cap on any one coin's weight
    max_long_short_imbalance: float = 0.80 # net directional bias cap (|L-S|/AUM)
    min_coin_count: int = 2                # require at least 2 coins
    dust_threshold_usdc: float = 0.05      # reject allocations < $0.05


@dataclass
class RiskVerdict:
    proposal_name: str
    verdict: str                  # "accept" | "accept_with_adjustment" | "veto"
    reasons: list[str] = field(default_factory=list)
    adjusted_proposal: AllocationProposal | None = None


@dataclass
class RiskAgent:
    policy: RiskPolicy = field(default_factory=RiskPolicy)

    def evaluate(self, proposals: list[AllocationProposal]) -> list[RiskVerdict]:
        return [self._evaluate_one(p) for p in proposals]

    # --- per-proposal evaluation -------------------------------------------

    def _evaluate_one(self, p: AllocationProposal) -> RiskVerdict:
        reasons: list[str] = []
        aum = p.total_usdc or 1.0  # avoid div-by-zero on empty proposals

        # 1. Concentration check
        max_alloc = max((a.target_notional_usd for a in p.allocations), default=0.0)
        max_share = max_alloc / aum
        if max_share > self.policy.max_single_coin_pct:
            reasons.append(
                f"concentration: max coin = {max_share*100:.1f}% (cap {self.policy.max_single_coin_pct*100:.0f}%)"
            )

        # 2. Long/short imbalance
        longs = sum(a.target_notional_usd for a in p.allocations if a.direction == "long")
        shorts = sum(a.target_notional_usd for a in p.allocations if a.direction == "short")
        imbalance = abs(longs - shorts) / aum
        if imbalance > self.policy.max_long_short_imbalance:
            reasons.append(
                f"directional bias: |L-S|/AUM = {imbalance*100:.0f}% (cap {self.policy.max_long_short_imbalance*100:.0f}%)"
            )

        # 3. Diversification
        if len(p.allocations) < self.policy.min_coin_count:
            reasons.append(
                f"under-diversified: {len(p.allocations)} coins (min {self.policy.min_coin_count})"
            )

        # 4. Dust allocations
        dust = [a for a in p.allocations if a.target_notional_usd < self.policy.dust_threshold_usdc]
        if dust:
            adjusted = self._strip_dust(p)
            return RiskVerdict(
                proposal_name=p.name,
                verdict="accept_with_adjustment",
                reasons=[
                    f"dropped {len(dust)} dust allocations < ${self.policy.dust_threshold_usdc:.2f}",
                    *reasons,
                ],
                adjusted_proposal=adjusted,
            )

        if not reasons:
            return RiskVerdict(proposal_name=p.name, verdict="accept", reasons=["all policy checks passed"])
        return RiskVerdict(proposal_name=p.name, verdict="veto", reasons=reasons)

    def _strip_dust(self, p: AllocationProposal) -> AllocationProposal:
        kept = [a for a in p.allocations if a.target_notional_usd >= self.policy.dust_threshold_usdc]
        if not kept:
            adjusted = deepcopy(p)
            adjusted.allocations = []
            return adjusted
        # Redistribute the dropped weight proportionally among the kept.
        total_kept = sum(a.target_notional_usd for a in kept) or 1.0
        boost = p.total_usdc / total_kept
        adjusted = deepcopy(p)
        adjusted.allocations = []
        for a in kept:
            new_a = deepcopy(a)
            new_a.target_notional_usd = a.target_notional_usd * boost
            new_a.rationale = a.rationale + " [dust-redistributed by RiskAgent]"
            adjusted.allocations.append(new_a)
        adjusted.name = f"{p.name}__dust-stripped"
        return adjusted
