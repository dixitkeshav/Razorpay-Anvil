"""Anvil core service — FastAPI. The dashboard (web/) is a thin client
over this API; all logic lives here and in the src/ pipeline modules it
calls. Read-only, same as src/mcp/server.py: no endpoint executes a
payment action.

State is computed once, on first request, from the committed main seed —
the same deterministic pipeline (detect -> attribute -> impact -> policy
-> execute) already gated in Phases 3-8.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.attribution.decomposition import find_minimal_cut
from src.detection.detector import detect_incidents
from src.evaluation.replay import replay
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.impact.estimator import estimate_impact
from src.ingest.db import connect, register_events
from src.ledger.store import LedgerStore

app = FastAPI(title="Anvil")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    _state["incidents"] = incidents
    _state["ledger"] = ledger
    _state["scorecard"] = scorecard
    return _state


def _incident_summary(index: int, entry: dict) -> dict:
    detector, attribution, impact = entry["detector"], entry["attribution"], entry["impact"]
    return {
        "incident_index": index,
        "slice": attribution["cut"],
        "window": detector["window"],
        "baseline_success_rate": detector["baseline"],
        "affected_attempts": impact["affected_attempts"],
        "affected_successes": impact["affected_successes"],
        "at_risk_gmv_paise": impact["at_risk_gmv"],
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/scorecard")
def scorecard() -> dict:
    return _load_state()["scorecard"]


@app.get("/api/incidents")
def list_incidents() -> list[dict]:
    incidents = _load_state()["incidents"]
    return [_incident_summary(i, entry) for i, entry in enumerate(incidents)]


@app.get("/api/incidents/{incident_index}")
def get_incident(incident_index: int) -> dict:
    incidents = _load_state()["incidents"]
    if not (0 <= incident_index < len(incidents)):
        raise HTTPException(status_code=404, detail="incident not found")

    entry = incidents[incident_index]
    summary = _incident_summary(incident_index, entry)
    summary["top_merchants"] = entry["impact"]["per_merchant"][:10]
    return summary


@app.get("/api/incidents/{incident_index}/attribution")
def get_incident_attribution(incident_index: int) -> dict:
    incidents = _load_state()["incidents"]
    if not (0 <= incident_index < len(incidents)):
        raise HTTPException(status_code=404, detail="incident not found")

    attribution = incidents[incident_index]["attribution"]
    return {
        "minimal_cut": attribution["cut"],
        "coverage": attribution["coverage"],
        "original_deficit": attribution["original_deficit"],
        "target_deficit": attribution["target_deficit"],
        "trace": [
            {
                "dimension": step["dim"],
                "value": step["value"],
                "p_value": step.get("pvalue"),
                "fraction_explained": step["fraction"],
                "attempts": step["attempts"],
            }
            for step in attribution["trace"]
        ],
    }


@app.get("/api/incidents/{incident_index}/ledger")
def get_incident_ledger(incident_index: int, limit: int = 100) -> dict:
    incidents = _load_state()["incidents"]
    if not (0 <= incident_index < len(incidents)):
        raise HTTPException(status_code=404, detail="incident not found")

    ledger = _load_state()["ledger"]
    entries = ledger.read_all()[-limit:]
    return {
        "total": len(ledger),
        "entries": [
            {
                "sequence": e.sequence,
                "payment_id": e.payment_id,
                "action": e.action.value,
                "execution_status": e.execution_status,
                "amount_paise": e.amount,
                "rationale": e.rationale,
            }
            for e in entries
        ],
    }
