"""Counterfactual replay — L8. Runs the full pipeline (detect -> attribute
-> impact -> policy -> execute) over one generated run and compares
agent-on (Anvil's policy engine acts on every failed attempt inside a
detected incident) against agent-off (nothing happens — the do-nothing
baseline fixed in docs/OUTCOME-MODEL.md §5, where every one of those
attempts simply stays failed).

Uses only src.detection/attribution/impact/policy/execution/ledger — the
same modules already gated in Phases 3-7. No new detection or attribution
logic lives here; this module only orchestrates and totals.
"""

import random

import duckdb
import polars as pl

from src.attribution.decomposition import find_minimal_cut
from src.detection.cusum import cusum_sr
from src.detection.detector import detect_incidents
from src.execution.executor import execute, new_idempotency_key
from src.impact.state_machine import IncidentState as FsmIncidentState
from src.impact.state_machine import run_fsm
from src.ingest.lattice_levels import dim_expr
from src.ingest.rollup import rollup
from src.ledger.store import LedgerStore
from src.policy import config as policy_config
from src.policy.engine import decide
from src.policy.models import Action, IncidentState, PolicyContext


def _query_failed_attempts(
    con: duckdb.DuckDBPyConnection, cut: dict, window: tuple[int, int]
) -> list[dict]:
    clauses = ["status = 'failed'", "(created_at // 60) BETWEEN ? AND ?"]
    params: list = [window[0], window[1]]
    for key, value in cut.items():
        clauses.append(f"{dim_expr(key)} = ?")
        params.append(value)
    where_sql = " AND ".join(clauses)
    sql = f"""
        SELECT id, method, amount, x_attempt_number, x_psp, x_merchant_id, created_at
        FROM events
        WHERE {where_sql}
    """
    cols = ["id", "method", "amount", "x_attempt_number", "x_psp", "x_merchant_id", "created_at"]
    return [dict(zip(cols, row, strict=True)) for row in con.execute(sql, params).fetchall()]


def _method_states(con: duckdb.DuckDBPyConnection, method: str) -> dict[int, FsmIncidentState]:
    df = rollup(con, ["method"]).filter(pl.col("method") == method).sort("minute_bucket")
    sr = df["success_rate"].to_list()
    n = df["attempts"].to_list()
    minutes = df["minute_bucket"].to_list()
    alarms, baselines = cusum_sr(sr, n)
    states = run_fsm(sr, baselines, alarms)
    return dict(zip(minutes, states, strict=True))


def replay(
    con: duckdb.DuckDBPyConnection, seed: int = 42, ledger: LedgerStore | None = None
) -> dict:
    """`ledger` defaults to a fresh, throwaway store. Pass one in to keep a
    reference to the real entries afterward — src.mcp.server does this so
    `query_recovery_ledger` has real data to serve."""
    ledger = ledger if ledger is not None else LedgerStore()
    rng = random.Random(seed)

    incidents = detect_incidents(con, metric="sr")
    l1_incidents = [r for r in incidents if r["level"] == "L1_method"]

    scorecard = {
        "incidents_detected": len(l1_incidents),
        "incident_slices": [i["slice"] for i in l1_incidents],
        "attempts_replayed": 0,
        "decisions_by_action": dict.fromkeys((a.value for a in Action), 0),
        "escalation_reasons_count": {},
        "hold_reasons_count": {},
        "gmv_recovered_agent_on_paise": 0,
        "gmv_recovered_agent_off_paise": 0,  # always 0 -- the do-nothing baseline recovers nothing
        "execution_cost_paise": 0,
        "recovered_count": 0,
        "automated_action_count": 0,
    }

    for incident in l1_incidents:
        method = incident["slice"]["method"]
        window = incident["window"]
        baseline = incident["baseline"]

        attr = find_minimal_cut(con, {"method": method}, window, baseline)
        cut = attr["cut"]
        confidence = min(attr["coverage"], 1.0) if attr["coverage"] > 0 else 0.0

        minute_to_state = _method_states(con, method)
        failed_rows = _query_failed_attempts(con, cut, window)

        merchant_hour_spend: dict[tuple[str, int], int] = {}

        for row in failed_rows:
            minute_bucket = row["created_at"] // 60
            state = minute_to_state.get(minute_bucket, FsmIncidentState.DEGRADED)
            hour = row["created_at"] // 3600
            merchant_key = (row["x_merchant_id"], hour)

            ctx = PolicyContext(
                payment_id=row["id"],
                method=row["method"],
                amount=row["amount"],
                attempt_number=max(row["x_attempt_number"] - 1, 0),
                captured=False,
                idempotency_key=new_idempotency_key(row["id"], row["x_attempt_number"]),
                created_at=row["created_at"],
                now=row["created_at"] + 30,
                incident_state=IncidentState(state.value),
                root_cause_confidence=confidence,
                x_psp=row["x_psp"],
                alternate_psp_healthy=True,
                merchant_id=row["x_merchant_id"],
                merchant_hourly_spend_paise=merchant_hour_spend.get(merchant_key, 0),
            )

            decision = decide(ctx)
            entry = execute(ctx, decision, ledger, mode="simulate", rng=rng)

            scorecard["attempts_replayed"] += 1
            scorecard["decisions_by_action"][decision.action.value] += 1
            for reason in decision.escalation_reasons:
                bucket = reason.split(" ")[0]
                scorecard["escalation_reasons_count"][bucket] = (
                    scorecard["escalation_reasons_count"].get(bucket, 0) + 1
                )
            for reason in decision.hold_reasons:
                bucket = reason.split(" ")[0]
                scorecard["hold_reasons_count"][bucket] = (
                    scorecard["hold_reasons_count"].get(bucket, 0) + 1
                )

            if decision.action in (Action.RETRY, Action.REROUTE):
                scorecard["automated_action_count"] += 1
                merchant_hour_spend[merchant_key] = (
                    merchant_hour_spend.get(merchant_key, 0) + row["amount"]
                )
                if decision.action == Action.REROUTE:
                    scorecard["execution_cost_paise"] += policy_config.COST_REROUTE_PAISE
                if entry.execution_status == "success":
                    scorecard["gmv_recovered_agent_on_paise"] += row["amount"]
                    scorecard["recovered_count"] += 1

    scorecard["net_incremental_recovery_paise"] = (
        scorecard["gmv_recovered_agent_on_paise"]
        - scorecard["gmv_recovered_agent_off_paise"]
        - scorecard["execution_cost_paise"]
    )
    scorecard["ledger_entry_count"] = len(ledger)
    return scorecard
