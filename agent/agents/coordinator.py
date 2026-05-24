"""
CoordinatorAgent — resolves the multi-agent vote into one final decision.

Resolution rules (deterministic):
  1. Filter to verdicts in {accept, accept_with_adjustment}.
  2. If empty, return FinalDecision with chosen=None + reasoning explaining
     that every proposal was vetoed. Caller decides what to do.
  3. Among the surviving set, pick by precedence:
       a. `kelly_bounded` (most risk-aware) accepted -> use it
       b. else `score_weighted` accepted -> use it
       c. else `equal_weight` accepted -> use it
       d. else first accepted -> use it
  4. If the picked verdict carried an adjusted_proposal, use the adjustment.
  5. Emit FinalDecision with the chosen AllocationProposal + a full audit
     trail (every agent's full output).

The precedence rule is a senior engineering choice, not magic: kelly_bounded
is the most conservative variant of score-weighted (cap + redistribute).
If risk accepts it, we prefer it. Otherwise fall back to the next-best.

The FinalDecision object is what the orchestrator serialises into the
allocation document; the on-chain CID hashes over this whole structure.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from agent.agents.scorer import WhaleScore
from agent.agents.allocator import AllocationProposal
from agent.agents.risk import RiskVerdict


PROPOSAL_PRECEDENCE = ("kelly_bounded", "score_weighted", "equal_weight")


@dataclass
class FinalDecision:
    chosen: AllocationProposal | None
    reasoning: str
    audit: dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinatorAgent:
    def decide(
        self,
        scores: list[WhaleScore],
        proposals: list[AllocationProposal],
        verdicts: list[RiskVerdict],
    ) -> FinalDecision:
        # Index verdicts by proposal name for O(1) lookup.
        verdict_by_name = {v.proposal_name: v for v in verdicts}

        # Build the audit trail upfront so even a "no decision" outcome
        # carries the full multi-agent reasoning.
        audit = {
            "scorer": {
                "agent": "ScorerAgent",
                "scores": [asdict(s) for s in scores],
            },
            "allocator": {
                "agent": "AllocatorAgent",
                "proposals": [
                    {
                        "name": p.name,
                        "weighting_method": p.weighting_method,
                        "reasoning": p.reasoning,
                        "total_usdc": p.total_usdc,
                        "allocations": [asdict(a) for a in p.allocations],
                    }
                    for p in proposals
                ],
            },
            "risk": {
                "agent": "RiskAgent",
                "verdicts": [
                    {
                        "proposal_name": v.proposal_name,
                        "verdict": v.verdict,
                        "reasons": v.reasons,
                        "adjusted": v.adjusted_proposal.name if v.adjusted_proposal else None,
                    }
                    for v in verdicts
                ],
            },
        }

        accepted_names = {
            v.proposal_name for v in verdicts
            if v.verdict in ("accept", "accept_with_adjustment")
        }

        if not accepted_names:
            return FinalDecision(
                chosen=None,
                reasoning="All proposals vetoed by RiskAgent — no rebalance this cycle.",
                audit=audit,
            )

        # Precedence pick.
        chosen_name = None
        for name in PROPOSAL_PRECEDENCE:
            if name in accepted_names:
                chosen_name = name
                break
        if chosen_name is None:
            # No precedence match (shouldn't happen with current AllocatorAgent
            # which always emits the three named variants, but defend anyway).
            chosen_name = next(iter(accepted_names))

        verdict = verdict_by_name[chosen_name]
        base = next(p for p in proposals if p.name == chosen_name)
        chosen = verdict.adjusted_proposal if verdict.adjusted_proposal else base
        reasoning = (
            f"chose {chosen_name} (verdict: {verdict.verdict}); "
            f"precedence rule favours kelly_bounded -> score_weighted -> equal_weight; "
            f"accepted set: {sorted(accepted_names)}"
        )
        return FinalDecision(chosen=chosen, reasoning=reasoning, audit=audit)
