"""Anvil MCP server — exposes get_incident, explain_attribution, and
query_recovery_ledger over the Model Context Protocol, so an agent
(Claude Desktop, Claude Code, or any other MCP client) can query Anvil's
incident state directly.

Read-only, by construction: every tool here only reads from an
already-computed incident list and an already-populated Recovery Ledger.
No tool executes a payment action or calls src.policy.engine.decide() —
src/policy/ remains the only code path that can, per CLAUDE.md rule #6.

State is computed once, on first tool call, from the committed main seed
— the same deterministic pipeline (detect -> attribute -> impact ->
policy -> execute) already gated in Phases 3-8, run once and cached for
the life of the server process.
"""

from mcp.server import MCPServer
from src.attribution.decomposition import find_minimal_cut
from src.detection.detector import detect_incidents
from src.evaluation.replay import replay
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.impact.estimator import estimate_impact
from src.ingest.db import connect, register_events
from src.ledger.store import LedgerStore

mcp = MCPServer("anvil")

_state: dict = {}


def _load_state() -> dict:
    if _state:
        return _state

    events_df, _ = generate(
        seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=SIM_START_EPOCH
    )
    con = connect()
    register_events(con, events_df)

    l1_incidents = [r for r in detect_incidents(con, metric="sr") if r["level"] == "L1_method"]
    incidents = []
    for inc in l1_incidents:
        method = inc["slice"]["method"]
        attr = find_minimal_cut(con, {"method": method}, inc["window"], inc["baseline"])
        impact = estimate_impact(con, attr["cut"], inc["window"])
        incidents.append({"detector": inc, "attribution": attr, "impact": impact})

    ledger = LedgerStore()
    scorecard = replay(con, seed=MAIN_SEED, ledger=ledger)

    _state["con"] = con
    _state["incidents"] = incidents
    _state["ledger"] = ledger
    _state["scorecard"] = scorecard
    return _state


@mcp.tool()
def get_incident(incident_index: int = 0) -> dict:
    """Get one detected incident by index: its slice, detected time
    window, and impact (affected attempts, at-risk GMV). Call with no
    arguments to get the first incident; the response includes how many
    incidents are available in total.
    """
    state = _load_state()
    incidents = state["incidents"]
    if not incidents:
        return {"error": "no incidents detected in this run"}
    if not (0 <= incident_index < len(incidents)):
        return {
            "error": f"incident_index {incident_index} out of range",
            "available_incidents": len(incidents),
        }

    entry = incidents[incident_index]
    detector, attribution, impact = entry["detector"], entry["attribution"], entry["impact"]
    return {
        "incident_index": incident_index,
        "total_incidents": len(incidents),
        "slice": attribution["cut"],
        "detected_window_minutes": detector["window"],
        "detector_p_value": detector["p_value"],
        "baseline_success_rate": detector["baseline"],
        "affected_attempts": impact["affected_attempts"],
        "affected_successes": impact["affected_successes"],
        "at_risk_gmv_paise": impact["at_risk_gmv"],
        "top_merchants": impact["per_merchant"][:5],
    }


@mcp.tool()
def explain_attribution(incident_index: int = 0) -> dict:
    """Explain how the minimal explanatory cut for one incident was
    derived: the dimensions added, in order, with the statistical
    significance and coverage of each step. See docs/POLICY.md and
    src/attribution/decomposition.py.
    """
    state = _load_state()
    incidents = state["incidents"]
    if not (0 <= incident_index < len(incidents)):
        return {
            "error": f"incident_index {incident_index} out of range",
            "available_incidents": len(incidents),
        }

    attribution = incidents[incident_index]["attribution"]
    trace = [
        {
            "dimension": step["dim"],
            "value": step["value"],
            "p_value": step.get("pvalue"),
            "fraction_of_target_deficit_explained": step["fraction"],
            "attempts": step["attempts"],
        }
        for step in attribution["trace"]
    ]
    return {
        "incident_index": incident_index,
        "minimal_cut": attribution["cut"],
        "coverage": attribution["coverage"],
        "original_deficit": attribution["original_deficit"],
        "target_deficit": attribution["target_deficit"],
        "trace": trace,
    }


@mcp.tool()
def query_recovery_ledger(action: str | None = None, limit: int = 20) -> dict:
    """Query the append-only Recovery Ledger produced by the last
    counterfactual replay. `action`, if given, filters to one of RETRY,
    REROUTE, HOLD, ESCALATE_HUMAN. Returns the most recent `limit` entries
    (by ledger sequence) and the total matching count.
    """
    state = _load_state()
    ledger = state["ledger"]

    entries = ledger.read_all()
    if action is not None:
        entries = [e for e in entries if e.action.value == action]

    total = len(entries)
    page = entries[-limit:] if limit > 0 else []

    return {
        "total_matching": total,
        "returned": len(page),
        "entries": [
            {
                "sequence": e.sequence,
                "entry_id": e.entry_id,
                "payment_id": e.payment_id,
                "action": e.action.value,
                "execution_status": e.execution_status,
                "amount_paise": e.amount,
                "rationale": e.rationale,
            }
            for e in page
        ],
    }


if __name__ == "__main__":
    mcp.run()
