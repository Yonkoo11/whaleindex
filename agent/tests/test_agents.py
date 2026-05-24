"""Multi-agent unit + integration tests.

Builds synthetic WhalePosition + PnL fixtures, runs each agent in isolation,
then runs the full Scorer -> Allocator -> Risk -> Coordinator pipeline and
checks the audit trail.
"""

from __future__ import annotations

import time

from agent.leaderboard_reader import WhalePosition
from agent.agents.scorer import ScorerAgent
from agent.agents.allocator import AllocatorAgent
from agent.agents.risk import RiskAgent, RiskPolicy
from agent.agents.coordinator import CoordinatorAgent


def _pos(wallet: str, coin: str, side: str, notional: float) -> WhalePosition:
    return WhalePosition(
        wallet=wallet, coin=coin, side=side, size=notional / 50_000.0,
        entry_price=50_000.0, leverage=5, notional_usd=notional,
        account_value=notional * 10, fetched_at=int(time.time()),
    )


WALLETS = ["0xA", "0xB", "0xC"]

# Fixture: A is the best whale (3 positions, +$10K PnL), C is the worst (no positions, -$5K).
POSITIONS = [
    _pos("0xA", "BTC", "long", 2000),
    _pos("0xA", "ETH", "long", 1500),
    _pos("0xA", "SOL", "short", 500),
    _pos("0xB", "BTC", "long", 1000),
    _pos("0xB", "ETH", "short", 800),
]
PNL_WINDOW = {"0xA": 10_000.0, "0xB": 2_500.0, "0xC": -5_000.0}


# --- ScorerAgent --------------------------------------------------------------

def test_scorer_ranks_best_first() -> None:
    out = ScorerAgent().score(WALLETS, POSITIONS, PNL_WINDOW)
    assert len(out) == 3
    # 0xA has best PnL + most positions + active -> top score.
    assert out[0].wallet == "0xA"
    # 0xC has worst PnL + zero positions + inactive -> bottom.
    assert out[-1].wallet == "0xC"


def test_scorer_components_sum_to_composite() -> None:
    scorer = ScorerAgent()
    out = scorer.score(WALLETS, POSITIONS, PNL_WINDOW)
    for s in out:
        expected = (
            scorer.pnl_weight * s.components.pnl
            + scorer.position_quality_weight * s.components.position_quality
            + scorer.recency_weight * s.components.recency
        )
        assert abs(s.score - round(expected, 2)) < 0.05


def test_scorer_falls_back_when_too_few_pnls() -> None:
    # All zero PnL → no signal, every whale gets neutral 50 on pnl component.
    out = ScorerAgent().score(WALLETS, POSITIONS, {w: 0.0 for w in WALLETS})
    for s in out:
        assert s.components.pnl == 50.0


# --- AllocatorAgent -----------------------------------------------------------

def test_allocator_emits_three_proposals_on_real_data() -> None:
    scored = ScorerAgent().score(WALLETS, POSITIONS, PNL_WINDOW)
    proposals = AllocatorAgent().propose(scored, POSITIONS, aum_usdc=100.0)
    names = {p.name for p in proposals}
    assert "equal_weight" in names
    assert "score_weighted" in names
    assert "kelly_bounded" in names


def test_allocator_kelly_cap_actually_caps() -> None:
    # Force a concentrated position: one whale, one coin, all the size.
    concentrated = [_pos("0xA", "BTC", "long", 9_999)]
    scores = ScorerAgent().score(["0xA"], concentrated, {"0xA": 10_000.0})
    proposals = AllocatorAgent(kelly_max_weight=0.30).propose(
        scores, concentrated, aum_usdc=100.0,
    )
    kelly = next(p for p in proposals if p.name == "kelly_bounded")
    # With one coin and cap 0.30, the kelly proposal should be capped to $30.
    # (When there's no other coin to redistribute to, the excess stays on the
    # capped one — but only up to the cap. We assert the cap holds.)
    for a in kelly.allocations:
        assert a.target_notional_usd <= 100.0 * 0.30 + 1e-6


def test_allocator_empty_on_no_positions() -> None:
    assert AllocatorAgent().propose([], [], aum_usdc=100.0) == []


# --- RiskAgent ----------------------------------------------------------------

def test_risk_accepts_diversified_proposal() -> None:
    scored = ScorerAgent().score(WALLETS, POSITIONS, PNL_WINDOW)
    proposals = AllocatorAgent().propose(scored, POSITIONS, aum_usdc=100.0)
    verdicts = RiskAgent().evaluate(proposals)
    # At least one proposal accepted (the test fixture is diversified).
    assert any(v.verdict in ("accept", "accept_with_adjustment") for v in verdicts)


def test_risk_vetoes_under_diversified() -> None:
    # One coin only -> below min_coin_count=2.
    concentrated = [_pos("0xA", "BTC", "long", 5_000)]
    scored = ScorerAgent().score(["0xA"], concentrated, {"0xA": 1000.0})
    proposals = AllocatorAgent().propose(scored, concentrated, aum_usdc=100.0)
    verdicts = RiskAgent(policy=RiskPolicy(min_coin_count=2)).evaluate(proposals)
    assert all(v.verdict == "veto" for v in verdicts)
    assert all(any("under-diversified" in r for r in v.reasons) for v in verdicts)


def test_risk_strips_dust_with_adjustment() -> None:
    # Build a proposal with one dust allocation.
    from agent.allocation_engine import Allocation
    from agent.agents.allocator import AllocationProposal
    dust = AllocationProposal(
        name="test",
        allocations=[
            Allocation(coin="BTC", direction="long", target_notional_usd=99.99, rationale="big"),
            Allocation(coin="DOGE", direction="long", target_notional_usd=0.01, rationale="dust"),
        ],
        total_usdc=100.0,
        reasoning="test",
        weighting_method="test",
    )
    v = RiskAgent(policy=RiskPolicy(dust_threshold_usdc=0.05, min_coin_count=1, max_single_coin_pct=1.0)).evaluate([dust])
    assert v[0].verdict == "accept_with_adjustment"
    assert v[0].adjusted_proposal is not None
    # DOGE dropped.
    assert all(a.coin != "DOGE" for a in v[0].adjusted_proposal.allocations)
    # Remaining BTC allocation scaled up to absorb the dropped dust.
    assert v[0].adjusted_proposal.allocations[0].target_notional_usd > 99.99


# --- CoordinatorAgent (integration) -------------------------------------------

def test_coordinator_picks_kelly_when_accepted() -> None:
    scored = ScorerAgent().score(WALLETS, POSITIONS, PNL_WINDOW)
    proposals = AllocatorAgent().propose(scored, POSITIONS, aum_usdc=100.0)
    verdicts = RiskAgent().evaluate(proposals)
    decision = CoordinatorAgent().decide(scored, proposals, verdicts)

    # If kelly_bounded was accepted, coordinator must pick it (precedence rule).
    accepted = {v.proposal_name for v in verdicts if v.verdict in ("accept", "accept_with_adjustment")}
    if "kelly_bounded" in accepted:
        assert decision.chosen is not None
        assert decision.chosen.name in ("kelly_bounded", "kelly_bounded__dust-stripped")
    else:
        # Otherwise: at least picks something accepted.
        assert decision.chosen is None or decision.chosen.name.startswith(
            tuple(["kelly_bounded", "score_weighted", "equal_weight"])
        )


def test_coordinator_returns_no_decision_when_all_vetoed() -> None:
    concentrated = [_pos("0xA", "BTC", "long", 5_000)]
    scored = ScorerAgent().score(["0xA"], concentrated, {"0xA": 1000.0})
    proposals = AllocatorAgent().propose(scored, concentrated, aum_usdc=100.0)
    verdicts = RiskAgent(policy=RiskPolicy(min_coin_count=2)).evaluate(proposals)
    decision = CoordinatorAgent().decide(scored, proposals, verdicts)
    assert decision.chosen is None
    assert "vetoed" in decision.reasoning.lower()
    # Audit trail still captures everything.
    assert decision.audit["scorer"]["scores"]
    assert decision.audit["allocator"]["proposals"]
    assert decision.audit["risk"]["verdicts"]


def test_coordinator_audit_records_every_agent() -> None:
    scored = ScorerAgent().score(WALLETS, POSITIONS, PNL_WINDOW)
    proposals = AllocatorAgent().propose(scored, POSITIONS, aum_usdc=100.0)
    verdicts = RiskAgent().evaluate(proposals)
    decision = CoordinatorAgent().decide(scored, proposals, verdicts)

    # Every agent contributes to the audit doc.
    assert decision.audit["scorer"]["agent"] == "ScorerAgent"
    assert decision.audit["allocator"]["agent"] == "AllocatorAgent"
    assert decision.audit["risk"]["agent"] == "RiskAgent"
    assert len(decision.audit["scorer"]["scores"]) == 3
    assert len(decision.audit["allocator"]["proposals"]) >= 1
    assert len(decision.audit["risk"]["verdicts"]) >= 1
