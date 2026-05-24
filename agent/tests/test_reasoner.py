"""ReasonerAgent (B8) — LLM-explanation tests using a mock transport.

No real Claude API key needed. The transport seam takes the request payload
and returns a fake response dict shaped like the SDK's output.
"""

from __future__ import annotations

import os
from typing import Any

from agent.agents.reasoner import ReasonerAgent, _format_audit_for_prompt


def _fake_response(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 500, "output_tokens": 200},
    }


def _sample_audit() -> dict[str, Any]:
    return {
        "scorer": {
            "agent": "ScorerAgent",
            "scores": [
                {"wallet": "0xAAA1111111111111111111111111111111111111",
                 "score": 78.5,
                 "components": {"pnl": 90, "sharpe": 80, "drawdown": 70, "win_rate": 60,
                                "position_quality": 100, "recency": 100},
                 "reasoning": "pnl=$+12000 (90/100), sharpe=+2.1 (80/100), maxDD=8% (70/100)",
                 "raw_pnl_usd": 12000.0, "raw_position_count": 4,
                 "raw_sharpe": 2.1, "raw_drawdown_pct": 0.08, "raw_win_rate": 0.6},
                {"wallet": "0xBBB2222222222222222222222222222222222222",
                 "score": 50.0,
                 "components": {"pnl": 50, "sharpe": 50, "drawdown": 50, "win_rate": 50,
                                "position_quality": 50, "recency": 50},
                 "reasoning": "pnl=$+0 (50/100), sharpe=+0.0 (50/100), maxDD=20% (50/100)",
                 "raw_pnl_usd": 0.0, "raw_position_count": 2,
                 "raw_sharpe": 0.0, "raw_drawdown_pct": 0.2, "raw_win_rate": 0.5},
            ],
        },
        "allocator": {
            "agent": "AllocatorAgent",
            "proposals": [
                {"name": "equal_weight", "weighting_method": "equal-weight",
                 "reasoning": "top-3 coins equal-weighted",
                 "total_usdc": 100.0,
                 "allocations": [
                     {"coin": "BTC", "direction": "long", "target_notional_usd": 33.3, "rationale": "equal"},
                     {"coin": "ETH", "direction": "long", "target_notional_usd": 33.3, "rationale": "equal"},
                     {"coin": "SOL", "direction": "long", "target_notional_usd": 33.4, "rationale": "equal"},
                 ]},
                {"name": "kelly_bounded", "weighting_method": "kelly-bounded",
                 "reasoning": "score-weighted, capped at 40% per coin",
                 "total_usdc": 100.0,
                 "allocations": [
                     {"coin": "BTC", "direction": "long", "target_notional_usd": 40.0, "rationale": "kelly-capped"},
                     {"coin": "ETH", "direction": "long", "target_notional_usd": 35.0, "rationale": "score-weighted"},
                     {"coin": "SOL", "direction": "long", "target_notional_usd": 25.0, "rationale": "score-weighted"},
                 ]},
            ],
        },
        "risk": {
            "agent": "RiskAgent",
            "verdicts": [
                {"proposal_name": "equal_weight", "verdict": "accept",
                 "reasons": ["all policy checks passed"], "adjusted": None},
                {"proposal_name": "kelly_bounded", "verdict": "accept",
                 "reasons": ["all policy checks passed"], "adjusted": None},
            ],
        },
    }


def test_explain_returns_none_when_no_key_and_no_transport(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = ReasonerAgent().explain(
        audit=_sample_audit(),
        chosen_proposal_name="kelly_bounded",
        coordinator_reasoning="chose kelly_bounded (precedence rule)",
        aum_usdc=100.0,
    )
    assert out is None


def test_explain_uses_transport_when_provided(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured: dict[str, Any] = {}

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        captured.update(payload)
        return _fake_response("This cycle picked kelly_bounded; allocated $100 across BTC/ETH/SOL.")

    out = ReasonerAgent(transport=transport).explain(
        audit=_sample_audit(),
        chosen_proposal_name="kelly_bounded",
        coordinator_reasoning="chose kelly_bounded (precedence rule)",
        aum_usdc=100.0,
    )
    assert out is not None
    assert "kelly_bounded" in out
    # Payload contained the system prompt + user prompt.
    assert captured["model"].startswith("claude-haiku")
    assert any("kelly_bounded" in m["content"] for m in captured["messages"])
    assert captured["max_tokens"] == 600


def test_explain_returns_none_when_response_empty(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = ReasonerAgent(transport=lambda _p: {"content": []}).explain(
        audit=_sample_audit(),
        chosen_proposal_name="kelly_bounded",
        coordinator_reasoning="x",
        aum_usdc=100.0,
    )
    assert out is None


def test_format_audit_includes_top_scores_and_verdicts() -> None:
    s = _format_audit_for_prompt(_sample_audit())
    # Contains both top scorers' shortened wallets (formatter trims to 10 chars).
    assert "0xAAA11111" in s
    assert "0xBBB22222" in s
    # Contains the proposal names + verdicts.
    assert "equal_weight" in s
    assert "kelly_bounded" in s
    assert "accept" in s


def test_format_audit_handles_empty() -> None:
    s = _format_audit_for_prompt({})
    assert "empty" in s.lower()


def test_explain_passes_chosen_proposal_into_prompt(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seen: dict[str, Any] = {}

    def transport(payload: dict[str, Any]) -> dict[str, Any]:
        seen["user_message"] = payload["messages"][0]["content"]
        return _fake_response("ok")

    ReasonerAgent(transport=transport).explain(
        audit=_sample_audit(),
        chosen_proposal_name="NO DECISION (all vetoed)",
        coordinator_reasoning="All proposals vetoed by RiskAgent",
        aum_usdc=0.0,
    )
    assert "NO DECISION" in seen["user_message"]
    assert "vetoed" in seen["user_message"]
