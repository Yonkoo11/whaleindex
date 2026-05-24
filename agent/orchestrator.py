"""
WhaleIndex orchestrator — the single entry point that runs the full agentic loop.

Pipeline (executed in order, fail-fast):

  1. Read whale watchlist (data/whales-hl.json).
  2. Concurrent fetch: current positions + 30d realised PnL per whale.
  3. Rank whales by realised PnL, run rank-decay filter via selection_engine
     (evicts whales whose rank fell by > threshold places since last run).
  4. Compute target allocations from surviving whales' positions
     (top-N coins by aggregate signed notional, equal-weighted).
  5. Build a canonical JSON allocation document. Hash it with keccak256
     to produce a 32-byte CID. Write it to docs/allocations/<cid_hex>.json
     so it's publicly resolvable at
     https://<github-pages-host>/allocations/<cid_hex>.json.
  6. Build a single RebalanceArgs (currently — V2 limits this to one CCTP
     move per cycle, so we route AUM to the top-allocation coin's chain) and
     submit via contract_client.send_rebalance(...).
  7. Append outcome to data/orchestrator-history.jsonl so retrospective
     analysis (and the /history page) has structured rows.

Run:
    python -m agent.orchestrator --network arc-testnet
    python -m agent.orchestrator --network arc-testnet --dry-run

Dry-run skips steps 6-7: builds the allocation doc + writes the CID file
but does NOT submit a rebalance. Useful for sanity-checking the pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from eth_account import Account
from web3 import Web3

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.contract_client import (
    RebalanceArgs,
    RebalanceClient,
    WhaleAttestationClient,
    _load_deployment,
)
from agent.leaderboard_reader import (
    fetch_clearinghouse_state,
    fetch_metrics_window,
    load_watchlist,
    parse_positions,
    WhalePosition,
    WindowMetrics,
)
from agent.allocation_engine import Allocation
from agent.selection_engine import (
    WhaleScore as DecayScore,
    DecayDecision,
    evaluate,
    survivors,
    pending_slashes,
)
from agent.agents import (
    ScorerAgent,
    AllocatorAgent,
    RiskAgent,
    CoordinatorAgent,
    ReasonerAgent,
)

DOCS_SLASHES_DIR = REPO_ROOT / "docs" / "slashes"


def _build_slash_doc(decision: DecayDecision, max_slash_bps: int) -> dict[str, Any]:
    """Canonical JSON the slash evidence CID hashes over."""
    return {
        "version": 1,
        "kind": "slash_evidence",
        "snapshot_at": int(time.time()),
        "snapshot_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wallet": decision.wallet,
        "prior_rank": decision.prior_rank,
        "current_rank": decision.current_rank,
        "decay_places": decision.decay_places,
        "slash_bps": decision.slash_bps,
        "slash_bps_cap": max_slash_bps,
        "reason": decision.reason,
        "policy": (
            "decay_severity_to_slash_bps: <=1 places -> 0, 2-3 -> 500, "
            "4-5 -> 1500, 6-10 -> 3000, 11+ -> max_slash_bps"
        ),
    }


def _publish_slash_doc(doc: dict[str, Any]) -> tuple[bytes, Path]:
    """Hash + write to docs/slashes/<cid_hex>.json. Returns (cid, path)."""
    DOCS_SLASHES_DIR.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    cid = Web3.keccak(canonical)
    out_path = DOCS_SLASHES_DIR / f"{cid.hex()}.json"
    out_path.write_text(json.dumps(doc, sort_keys=True, indent=2))
    return cid, out_path

DOCS_ALLOCATIONS_DIR = REPO_ROOT / "docs" / "allocations"
HISTORY_PATH = REPO_ROOT / "data" / "orchestrator-history.jsonl"

# CCTP V2 domain IDs for the coins we know about.
# This is a heuristic: most whales trade perps on HL itself (no cross-chain leg).
# For the rebalance leg we just route to a fixed destination (Arbitrum, the most
# liquid receiving chain) and pin the destination there until cross-venue ships.
DEFAULT_DESTINATION_DOMAIN = 3  # Arbitrum
DEFAULT_DESTINATION_RECIPIENT_FALLBACK = "0xf9946775891a24462cD4ec885d0D4E2675C84355"


async def _fetch_positions_and_metrics(
    wallets: list[str], pnl_window_days: int
) -> tuple[list[WhalePosition], dict[str, WindowMetrics]]:
    """Concurrent fetch of positions + extended metrics across every wallet."""
    async with httpx.AsyncClient() as client:
        position_tasks = [fetch_clearinghouse_state(client, w) for w in wallets]
        metric_tasks = [fetch_metrics_window(client, w, pnl_window_days) for w in wallets]
        results = await asyncio.gather(*(position_tasks + metric_tasks), return_exceptions=True)

    n = len(wallets)
    position_results = results[:n]
    metric_results = results[n:]

    positions: list[WhalePosition] = []
    metrics: dict[str, WindowMetrics] = {}
    for wallet, p_res, m_res in zip(wallets, position_results, metric_results):
        if isinstance(p_res, dict):
            positions.extend(parse_positions(wallet, p_res))
        else:
            print(f"  WARN: positions fetch failed for {wallet}: {p_res}")
        if isinstance(m_res, WindowMetrics):
            metrics[wallet] = m_res
        else:
            if isinstance(m_res, BaseException):
                print(f"  WARN: metrics fetch failed for {wallet}: {m_res}")
            metrics[wallet] = WindowMetrics(
                pnl_usd=0.0, sharpe=0.0, max_drawdown_pct=0.0,
                win_rate=0.0, fill_count=0, volume_usd=0.0, window_days=pnl_window_days,
            )
    return positions, metrics


def _build_allocation_doc(
    survivors_wallets: list[str],
    positions: list[WhalePosition],
    pnl_window: dict[str, float],
    allocations: list[Allocation],
    aum_usdc: float,
    pnl_window_days: int,
    multi_agent_audit: dict[str, Any] | None = None,
    chosen_proposal_name: str | None = None,
    coordinator_reasoning: str | None = None,
    human_reasoning: str | None = None,
) -> dict[str, Any]:
    """Canonical JSON the CID hashes over. Stable key order is enforced at write time."""
    return {
        "version": 2,
        "snapshot_at": int(time.time()),
        "snapshot_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "aum_usdc": aum_usdc,
        "pnl_window_days": pnl_window_days,
        "whales": [
            {
                "wallet": w,
                "realised_pnl_usd_window": pnl_window.get(w, 0.0),
                "open_position_count": sum(1 for p in positions if p.wallet == w),
            }
            for w in survivors_wallets
        ],
        "allocations": [asdict(a) for a in allocations],
        "decision": {
            "chosen_proposal": chosen_proposal_name,
            "coordinator_reasoning": coordinator_reasoning,
            "human_reasoning": human_reasoning or "(no LLM key configured — set ANTHROPIC_API_KEY to populate)",
            "multi_agent_audit": multi_agent_audit or {},
        },
        "method": (
            "Hyperliquid positions + 30d realised PnL -> rank-decay eviction "
            "-> Scorer (composite 0-100) -> Allocator (3 proposals: equal/score/kelly) "
            "-> Risk (concentration/imbalance/diversification/dust checks) "
            "-> Coordinator (precedence: kelly > score > equal)"
        ),
        "limitations": [
            "Realised PnL only (no unrealised). A whale with large open winning trades is undervalued.",
            "Risk veto bounds are heuristic, not derived from a return-distribution model.",
            "Allocator's score-weighting uses composite score; a true Sharpe-weighted variant lands in V3.",
            "Single-cycle decisions; no inter-cycle memory beyond rank-decay baseline.",
        ],
    }


def _cid_of(doc: dict[str, Any]) -> bytes:
    """Content-hash CID = keccak256 over the canonical JSON serialisation."""
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    return Web3.keccak(canonical)


def _publish_allocation_doc(doc: dict[str, Any], cid: bytes) -> Path:
    """Write the doc to docs/allocations/<cid_hex>.json so GitHub Pages serves it."""
    DOCS_ALLOCATIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DOCS_ALLOCATIONS_DIR / f"{cid.hex()}.json"
    out_path.write_text(json.dumps(doc, sort_keys=True, indent=2))
    return out_path


def _append_history(row: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a") as f:
        f.write(json.dumps(row) + "\n")


def _resolve_rpc_url() -> str | None:
    """RPC override env names that beat the deployment file's placeholder."""
    for name in ("ARC_RPC_URL", "RPC"):
        v = os.getenv(name)
        if v:
            return v
    return None


def _resolve_operator_key() -> str:
    for name in ("OPERATOR_PRIVATE_KEY", "DEPLOYER_PRIVATE_KEY"):
        v = os.getenv(name)
        if v:
            os.environ.setdefault("OPERATOR_PRIVATE_KEY", v)
            return v
    raise EnvironmentError(
        "Set OPERATOR_PRIVATE_KEY (or DEPLOYER_PRIVATE_KEY) in env. "
        "Use scripts/orchestrate-arc.sh which sources ~/.zshenv."
    )


async def run(
    network: str,
    pnl_window_days: int,
    decay_threshold: int,
    aum_usdc: float,
    dry_run: bool,
    new_nav_usdc: int,
    park_amount_usdc: int,
    allow_demo_fallback: bool = False,
    cctp_mode: str = "on-chain",
) -> int:
    print(f"[orchestrator] network={network} aum=${aum_usdc:,.2f} pnl_window={pnl_window_days}d dry_run={dry_run}")

    # Step 1: load watchlist
    watchlist = load_watchlist()
    wallets = [w["wallet"] for w in watchlist]
    print(f"[1/7] watchlist: {len(wallets)} whales")

    # Step 2: concurrent positions + extended metrics (PnL + Sharpe + drawdown + win-rate + volume)
    print(f"[2/7] fetching HL positions + {pnl_window_days}d extended metrics...")
    positions, metrics_by_wallet = await _fetch_positions_and_metrics(wallets, pnl_window_days)
    pnl = {w: m.pnl_usd for w, m in metrics_by_wallet.items()}
    print(f"      {len(positions)} positions from {len({p.wallet for p in positions})} whales")
    for w in wallets:
        m = metrics_by_wallet[w]
        print(f"      {w[:10]}...  PnL ${m.pnl_usd:>+12,.2f}  sharpe={m.sharpe:+5.2f}  "
              f"win={m.win_rate*100:>3.0f}%  maxDD={m.max_drawdown_pct*100:>4.1f}%  "
              f"fills={m.fill_count:>3d}  positions={sum(1 for p in positions if p.wallet == w)}")

    # Step 3: rank-decay filter (selection_engine — evicts whales whose rank fell).
    # If a WhaleAttestation V3 contract is deployed, bonded whales with decay
    # > threshold are routed through the slash path instead of plain eviction.
    print("[3/7] rank-decay filter...")
    attestation_client: WhaleAttestationClient | None = None
    is_bonded_fn = None
    max_slash_bps = 5000
    if not dry_run:
        try:
            deployment_peek = _load_deployment(network)
            if deployment_peek["addresses"].get("WhaleAttestation"):
                # Build the web3 connection early so we can query bond state.
                rpc_url_peek = _resolve_rpc_url() or deployment_peek["_meta"]["rpc"]
                if "<arc-canteen-token>" not in rpc_url_peek:
                    w3_peek = Web3(Web3.HTTPProvider(rpc_url_peek, request_kwargs={"timeout": 30}))
                    if w3_peek.is_connected():
                        attestation_client = WhaleAttestationClient.from_deployments(deployment_peek, w3_peek)
                        max_slash_bps = attestation_client.max_slash_bps()
                        is_bonded_fn = attestation_client.is_bonded
                        print(f"      WhaleAttestation V3 connected: {attestation_client.address}  maxSlashBps={max_slash_bps}")
        except Exception as e:
            print(f"      WARN: WhaleAttestation lookup failed ({e}); proceeding without slash path")

    decay_scores = [DecayScore(wallet=w, score=pnl[w]) for w in wallets]
    decisions = evaluate(
        decay_scores,
        decay_threshold=decay_threshold,
        update_baseline=not dry_run,
        is_bonded_fn=is_bonded_fn,
        max_slash_bps=max_slash_bps,
    )
    keep = survivors(decisions)
    print(f"      survivors: {len(keep)} of {len(wallets)} whales")
    for d in decisions:
        suffix = f"  [slash {d.slash_bps/100:.1f}%]" if d.verdict == "slash_pending" else ""
        print(f"      {d.wallet[:10]}...  {d.verdict:14s}  {d.reason}{suffix}")

    # Step 3.5: perform on-chain slashes for any slash_pending decisions.
    slash_decisions = pending_slashes(decisions)
    slash_receipts: list[dict[str, Any]] = []
    if slash_decisions and attestation_client is not None and not dry_run:
        print(f"[3.5/7] performing {len(slash_decisions)} on-chain slash(es)...")
        for d in slash_decisions:
            slash_doc = _build_slash_doc(d, max_slash_bps)
            scid, spath = _publish_slash_doc(slash_doc)
            print(f"      slash evidence cid: 0x{scid.hex()}")
            print(f"      published: {spath.relative_to(REPO_ROOT)}")
            try:
                rcpt = attestation_client.slash(d.wallet, d.slash_bps, scid)
                print(f"      → {rcpt.plain_english()}")
                slash_receipts.append({
                    "wallet": d.wallet,
                    "slash_bps": d.slash_bps,
                    "slash_amount_usdc": rcpt.slash_amount_usdc,
                    "evidence_cid": scid.hex(),
                    "evidence_path": str(spath.relative_to(REPO_ROOT)),
                    "tx_hash": rcpt.tx_hash,
                    "block_number": rcpt.block_number,
                    "gas_used": rcpt.gas_used,
                    "latency_seconds": rcpt.latency_seconds,
                })
            except Exception as e:
                print(f"      SLASH FAILED for {d.wallet}: {e}")
    elif slash_decisions and (attestation_client is None or dry_run):
        print(f"[3.5/7] would slash {len(slash_decisions)} bonded whales (dry_run or no attestation client)")
        for d in slash_decisions:
            print(f"      {d.wallet[:10]}...  slash_bps={d.slash_bps}")

    # Step 4: multi-agent decision (Scorer -> Allocator -> Risk -> Coordinator)
    print("[4/7] multi-agent decision (Scorer + Allocator + Risk + Coordinator)...")
    surviving_positions = [p for p in positions if p.wallet in set(keep)]
    surviving_metrics = {w: metrics_by_wallet[w] for w in keep}

    scorer = ScorerAgent()
    allocator = AllocatorAgent()
    risk = RiskAgent()
    coordinator = CoordinatorAgent()

    # Extended scoring (uses Sharpe, drawdown, win-rate in addition to PnL).
    scored = scorer.score(keep, surviving_positions, metrics_by_wallet=surviving_metrics)
    print(f"      Scorer:    {len(scored)} whales scored")
    for s in scored[:5]:
        print(f"        {s.wallet[:10]}...  composite={s.score:>5.1f}/100   {s.reasoning}")

    proposals = allocator.propose(scored, surviving_positions, aum_usdc)
    print(f"      Allocator: {len(proposals)} proposals")
    for p in proposals:
        print(f"        {p.name:18s} {len(p.allocations)} coins  ({p.reasoning})")

    verdicts = risk.evaluate(proposals)
    for v in verdicts:
        flag = "ok" if v.verdict == "accept" else ("adj" if v.verdict == "accept_with_adjustment" else "VETO")
        print(f"      Risk:      {v.proposal_name:18s} [{flag}]  {'; '.join(v.reasons)}")

    decision = coordinator.decide(scored, proposals, verdicts)
    print(f"      Coord:     {decision.reasoning}")

    allocations: list[Allocation] = decision.chosen.allocations if decision.chosen else []

    if not allocations and not allow_demo_fallback:
        print("[orchestrator] no allocations produced — nothing to rebalance. exit 0.")
        print("              (set --demo-allocation to inject a synthetic 1-coin allocation for end-to-end testing)")
        return 0

    if not allocations and allow_demo_fallback:
        print("[orchestrator] DEMO FALLBACK: no real allocations — injecting synthetic 1-coin allocation")
        allocations = [Allocation(
            coin="BTC",
            direction="long",
            target_notional_usd=aum_usdc,
            rationale="DEMO synthetic — no real whale data available (placeholders only)",
        )]
        keep = wallets  # mark all watchlist wallets as "survivors" for the doc
        # No real audit trail when demoing; record the gap honestly.
        decision = CoordinatorAgent().decide([], [], [])
        decision.reasoning = "DEMO synthetic; no real agents ran. See limitations."

    # Step 5: optional LLM reasoning + build + publish allocation document.
    print("[5/7] building canonical allocation doc + content-hash CID...")
    human_reasoning: str | None = None
    if os.getenv("ANTHROPIC_API_KEY"):
        print("      ANTHROPIC_API_KEY set — generating human-readable explanation via Claude...")
        try:
            human_reasoning = ReasonerAgent().explain(
                audit=decision.audit,
                chosen_proposal_name=decision.chosen.name if decision.chosen else None,
                coordinator_reasoning=decision.reasoning,
                aum_usdc=aum_usdc,
            )
            if human_reasoning:
                print(f"      reasoning ({len(human_reasoning)} chars): {human_reasoning[:120]}...")
        except Exception as e:
            print(f"      WARN: ReasonerAgent failed ({e}); proceeding without LLM reasoning")
    else:
        print("      (no ANTHROPIC_API_KEY — skipping LLM reasoning, audit-only doc)")

    doc = _build_allocation_doc(
        survivors_wallets=keep,
        positions=positions,
        pnl_window=pnl,
        allocations=allocations,
        aum_usdc=aum_usdc,
        pnl_window_days=pnl_window_days,
        multi_agent_audit=decision.audit,
        chosen_proposal_name=decision.chosen.name if decision.chosen else None,
        coordinator_reasoning=decision.reasoning,
        human_reasoning=human_reasoning,
    )
    cid = _cid_of(doc)
    out_path = _publish_allocation_doc(doc, cid)
    print(f"      cid: 0x{cid.hex()}")
    print(f"      written: {out_path.relative_to(REPO_ROOT)}")
    print(f"      will be public at: https://yonkoo11.github.io/whaleindex/allocations/{cid.hex()}.json")

    if dry_run:
        print("[6/7] DRY RUN — skipping rebalance submission")
        print("[7/7] DRY RUN — skipping history append")
        return 0

    # Step 6: submit rebalance (mode-dispatched)
    print(f"[6/7] submitting rebalance to {network} (cctp_mode={cctp_mode})...")
    key = _resolve_operator_key()
    rpc_url = _resolve_rpc_url()
    deployment = _load_deployment(network)
    if rpc_url:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    else:
        rpc_from_file = deployment["_meta"]["rpc"]
        if "<arc-canteen-token>" in rpc_from_file or not rpc_from_file:
            raise RuntimeError(
                "No RPC: deployment file has placeholder, ARC_RPC_URL/RPC not set in env"
            )
        w3 = Web3(Web3.HTTPProvider(rpc_from_file, request_kwargs={"timeout": 30}))
    if not w3.is_connected():
        raise ConnectionError("Arc RPC unreachable")

    client = RebalanceClient(w3, deployment)
    operator_addr = Account.from_key(key).address

    total_usdc_base = sum(int(a.target_notional_usd * 1_000_000) for a in allocations)

    args = RebalanceArgs(
        total_usdc=total_usdc_base,
        park_amount=park_amount_usdc,
        destination_domain=DEFAULT_DESTINATION_DOMAIN,
        mint_recipient_evm=operator_addr,
        max_fee=50_000,
        min_finality_threshold=2000,  # Standard finality
        new_nav_usdc=new_nav_usdc,
        allocation_cid=cid,
        whale_count=len(keep),
    )

    history_row = {
        "ts": int(time.time()),
        "network": network,
        "cid": cid.hex(),
        "allocation_doc_path": str(out_path.relative_to(REPO_ROOT)),
        "destination_domain": args.destination_domain,
        "usdc_routed": total_usdc_base - park_amount_usdc,
        "whale_count": len(keep),
        "cctp_mode": cctp_mode,
        "slashes": slash_receipts,
    }

    if cctp_mode == "off-chain":
        # Read real TokenMessenger from deployment metadata.
        meta = deployment.get("_meta", {})
        canon = meta.get("canonical_arc_addresses_referenced_but_not_called", {})
        real_messenger = canon.get("TokenMessengerV2")
        if not real_messenger:
            raise RuntimeError(
                "off-chain mode requires _meta.canonical_arc_addresses_referenced_but_not_called.TokenMessengerV2 in the deployment file"
            )
        print(f"      real CCTP TokenMessenger: {real_messenger}")
        offchain_receipt = client.send_rebalance_offchain_cctp(args, real_messenger)
        print(f"      prepare tx: {offchain_receipt.prepare_tx_hash}")
        print(f"      burn tx:    {offchain_receipt.burn_tx_hash}")
        print(f"      commit tx:  {offchain_receipt.commit_tx_hash}")
        print(f"      burn id:    {offchain_receipt.burn_id}")
        print(f"      total latency: {offchain_receipt.total_latency_seconds:.2f}s (3-tx flow)")
        print(f"      NAV: ${offchain_receipt.nav_before_usdc/1e6:.4f} -> ${offchain_receipt.nav_after_usdc/1e6:.4f}")
        print(f"      routed: ${offchain_receipt.usdc_routed/1e6:.4f} via REAL CCTP nonce {offchain_receipt.cctp_nonce}")
        history_row.update({
            "prepare_tx_hash": offchain_receipt.prepare_tx_hash,
            "burn_tx_hash": offchain_receipt.burn_tx_hash,
            "commit_tx_hash": offchain_receipt.commit_tx_hash,
            "burn_id": offchain_receipt.burn_id,
            "cctp_nonce": offchain_receipt.cctp_nonce,
            "total_latency_seconds": offchain_receipt.total_latency_seconds,
            "nav_before_usdc": offchain_receipt.nav_before_usdc,
            "nav_after_usdc": offchain_receipt.nav_after_usdc,
        })
    else:
        receipt = client.send_rebalance(args)
        print(f"      tx: {receipt.tx_hash}")
        print(f"      latency: {receipt.latency_seconds:.2f}s")
        print(f"      NAV: ${receipt.nav_before_usdc/1e6:.4f} -> ${receipt.nav_after_usdc/1e6:.4f}")
        print(f"      routed: ${receipt.usdc_routed/1e6:.4f} to Arbitrum (mock CCTP nonce {receipt.cctp_nonce})")
        print(f"      gas: {receipt.gas_used:,}")
        history_row.update({
            "tx_hash": receipt.tx_hash,
            "block_number": receipt.block_number,
            "latency_seconds": receipt.latency_seconds,
            "nav_before_usdc": receipt.nav_before_usdc,
            "nav_after_usdc": receipt.nav_after_usdc,
            "cctp_nonce": receipt.cctp_nonce,
            "gas_used": receipt.gas_used,
        })

    print("[7/7] appending outcome to history...")
    _append_history(history_row)
    print("[orchestrator] done.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WhaleIndex full agentic loop")
    parser.add_argument("--network", default="arc-testnet", help="Deployment name (local | arc-testnet)")
    parser.add_argument("--pnl-window-days", type=int, default=30)
    parser.add_argument("--decay-threshold", type=int, default=2,
                        help="Evict whales whose rank dropped by > N places.")
    parser.add_argument("--aum-usdc", type=float, default=1.0,
                        help="Total AUM to allocate this cycle (USDC, decimal).")
    parser.add_argument("--new-nav-usdc", type=int, default=1_000_000,
                        help="New NAV value after rebalance (base units, 6 decimals).")
    parser.add_argument("--park-usdc", type=int, default=0,
                        help="USDC base units to park in USYC this cycle.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip rebalance submission + history append.")
    parser.add_argument("--demo-allocation", action="store_true",
                        help="If watchlist returns no positions (e.g. placeholder addresses), "
                             "inject a synthetic 1-coin allocation so the submit path is testable.")
    parser.add_argument("--cctp-mode", choices=["on-chain", "off-chain"], default="on-chain",
                        help="on-chain: single-tx rebalance via the deployed (currently Mock) CCTPRouter. "
                             "off-chain: 3-tx flow that sidesteps Arc's contract-caller gate: "
                             "prepareRebalance -> operator EOA signs real depositForBurn -> commitRebalance.")
    args = parser.parse_args()
    return asyncio.run(run(
        network=args.network,
        pnl_window_days=args.pnl_window_days,
        decay_threshold=args.decay_threshold,
        aum_usdc=args.aum_usdc,
        dry_run=args.dry_run,
        new_nav_usdc=args.new_nav_usdc,
        park_amount_usdc=args.park_usdc,
        allow_demo_fallback=args.demo_allocation,
        cctp_mode=args.cctp_mode,
    ))


if __name__ == "__main__":
    sys.exit(main())
