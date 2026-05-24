"""Multi-agent decomposition of the rebalance decision.

Four cooperating agents:
  - ScorerAgent      ranks whales by a composite score (PnL, recency, position quality).
  - AllocatorAgent   proposes target weights as a SLATE of competing proposals.
  - RiskAgent        accepts or vetoes each proposal against policy bounds.
  - CoordinatorAgent resolves votes into a final allocation + audit trail.

The audit trail is what gets serialised into the on-chain-anchored allocation
document. Judges and operators can see exactly which agent said what + why.
"""

from .scorer import ScorerAgent, WhaleScore, ScoreComponents
from .allocator import AllocatorAgent, AllocationProposal
from .risk import RiskAgent, RiskVerdict, RiskPolicy
from .coordinator import CoordinatorAgent, FinalDecision
from .reasoner import ReasonerAgent

__all__ = [
    "ScorerAgent", "WhaleScore", "ScoreComponents",
    "AllocatorAgent", "AllocationProposal",
    "RiskAgent", "RiskVerdict", "RiskPolicy",
    "CoordinatorAgent", "FinalDecision",
    "ReasonerAgent",
]
