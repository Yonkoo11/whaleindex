"""
ReasonerAgent — LLM-generated human-readable explanation of the rebalance.

Takes the full multi-agent audit (from CoordinatorAgent.FinalDecision.audit)
and produces 2-4 paragraphs of plain English that a non-developer can read:
  - what the agent saw (whale signal summary)
  - what proposals it considered + which was picked + why
  - what the Risk agent vetoed (if anything)
  - any caveats or limitations
  - a calibrated confidence level

Design constraints:
  - OPTIONAL. If ANTHROPIC_API_KEY is unset, ReasonerAgent.explain returns
    None and the orchestrator just omits the field from the allocation doc.
    The product runs identically without an LLM.
  - DETERMINISTIC structure even though the prose is LLM-generated. The
    audit dict is the source of truth; the LLM only PHRASES it. The
    orchestrator embeds both the prose AND the raw audit so a reader can
    spot-check the LLM against the data.
  - Cheap by default. Uses Claude Haiku (claude-haiku-4-5) with
    max_tokens 600. Per-call cost on Haiku is sub-cent.
  - Testable without a network. The HTTP call is wrapped in a thin
    `_call_claude` method that's mockable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

# anthropic SDK import is lazy — only fails if explain() is invoked without
# the SDK installed, and the error message points the user at the install.


SYSTEM_PROMPT = """\
You are a quant-aware financial writer summarising a single rebalance decision
made by an automated multi-agent system. Your job is to translate the agents'
structured votes into plain English that a non-developer can read in 30
seconds, while staying faithful to the data.

Rules:
- Use the audit dict as the ONLY source of facts. Do not invent numbers.
- 2-4 short paragraphs. No bullet lists, no headers, no markdown.
- Sentence #1 must say what was decided (which proposal, total USDC, top 1-2 coins).
- Include the *why*: cite the top scoring whale's reasoning line, name the
  risk verdict for the chosen proposal, and note any vetoed proposals.
- If RiskAgent vetoed everything, say so plainly and stop.
- End with one sentence on the biggest caveat (e.g., "this cycle had only N
  whales with nonzero PnL", "no real Sharpe signal", etc.).
- Calibrated language. Avoid "should", "will", "guaranteed". Prefer "the
  data suggests" / "this cycle picked" / "the audit shows".
"""


def _format_audit_for_prompt(audit: dict[str, Any]) -> str:
    """Slim the audit dict so the prompt fits comfortably in a Haiku request."""
    if not audit:
        return "(empty audit — no agents ran)"

    scorer = audit.get("scorer", {})
    allocator = audit.get("allocator", {})
    risk = audit.get("risk", {})

    # Top-3 scorers only (their reasoning lines are the most useful).
    scores = scorer.get("scores", [])[:3]
    score_lines = [
        f"  - {s['wallet'][:10]}...  composite={s['score']:.1f}/100  ({s['reasoning']})"
        for s in scores
    ]

    proposal_lines = []
    for p in allocator.get("proposals", []):
        coins = ", ".join(
            f"{a['coin']}({a['direction']} ${a['target_notional_usd']:.2f})"
            for a in p.get("allocations", [])[:5]
        )
        proposal_lines.append(f"  - {p['name']}: {coins or '(empty)'}  ({p['reasoning']})")

    verdict_lines = [
        f"  - {v['proposal_name']}: {v['verdict']}  ({'; '.join(v['reasons'])})"
        for v in risk.get("verdicts", [])
    ]

    return (
        "SCORER (top 3):\n" + ("\n".join(score_lines) or "  (none)") + "\n\n"
        + "ALLOCATOR proposals:\n" + ("\n".join(proposal_lines) or "  (none)") + "\n\n"
        + "RISK verdicts:\n" + ("\n".join(verdict_lines) or "  (none)")
    )


@dataclass
class ReasonerAgent:
    """LLM reasoning over the multi-agent audit dict.

    api_key:  ANTHROPIC_API_KEY (read from env if not passed).
    model:    Claude model. Default haiku-4-5 for cheap explanations.
    max_tokens:  cap; 600 fits 4 short paragraphs comfortably.
    transport:  Optional callable for testing — takes the request kwargs dict
                and returns a fake response dict matching the SDK's shape.
    """
    api_key: str | None = None
    model: str = "claude-haiku-4-5"
    max_tokens: int = 600
    transport: Callable[..., dict[str, Any]] | None = None

    def explain(
        self,
        audit: dict[str, Any],
        chosen_proposal_name: str | None,
        coordinator_reasoning: str,
        aum_usdc: float,
    ) -> str | None:
        """Returns the LLM-generated explanation, or None when no API key is set."""
        key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key and not self.transport:
            return None

        prompt = (
            f"Multi-agent rebalance audit. Decision: {chosen_proposal_name or 'NO DECISION (all vetoed)'}\n"
            f"Coordinator reasoning: {coordinator_reasoning}\n"
            f"Total AUM this cycle: ${aum_usdc:,.2f}\n\n"
            f"{_format_audit_for_prompt(audit)}\n\n"
            "Write the explanation now."
        )

        request_payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

        if self.transport is not None:
            response = self.transport(request_payload)
        else:
            assert key is not None  # narrowed by the early-return above
            response = self._call_claude(key, request_payload)

        # Extract the text. The Anthropic API returns content as a list of blocks.
        try:
            content = response.get("content", [])
            if not content:
                return None
            return content[0].get("text", "") or None
        except (KeyError, IndexError, AttributeError):
            return None

    def _call_claude(self, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Thin wrapper around the Anthropic SDK. Imported lazily."""
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Install the anthropic SDK to use ReasonerAgent: "
                "pip install anthropic"
            ) from e
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(**payload)
        # Coerce SDK Message object to plain dict matching our test-transport shape.
        return {
            "content": [
                {"type": block.type, "text": getattr(block, "text", "")}
                for block in msg.content
            ],
            "stop_reason": msg.stop_reason,
            "usage": {
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
            },
        }
