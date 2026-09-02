"""Anvil core service — FastAPI. The dashboard (web/) is a thin client
over this API; all logic lives here and in the src/ pipeline modules it
calls. Read-only, same as src/mcp/server.py: no endpoint executes a
payment action.

State is computed once, on first request, from the committed main seed —
the same deterministic pipeline (detect -> attribute -> impact -> policy
-> execute) already gated in Phases 3-8.
"""

import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.attribution.decomposition import find_minimal_cut
from src.detection.detector import detect_incidents
from src.evaluation.replay import replay
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.impact.estimator import estimate_impact
from src.ingest.db import connect, register_events
from src.ledger.store import LedgerStore
from src.llm.cache import LlmCache
from src.llm.qa import answer_question

app = FastAPI(title="Anvil")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_state: dict = {}
_state_lock = threading.Lock()
_qa_cache = LlmCache()  # in-memory only for this process; never .save()d, so the
# committed fixtures/llm_cache.json is never mutated by a live API request


def _get_llm_client():
    """Best-effort Groq client for the /api/qa endpoint. Never raises --
    any failure to configure a live client (offline mode, missing key,
    import error) falls back to answer_question()'s own template path,
    same fail-closed contract as src.llm.narrative."""
    from src.llm.client import is_offline

    if is_offline():
        return None
    try:
        from src.llm.client import get_client

        return get_client()
    except Exception:
        return None


def _load_state() -> dict:
    if _state:
        return _state

    with _state_lock:
        if _state:
            return _state
        _compute_state()
    return _state


def _compute_state() -> None:
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


class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/qa")
def qa(req: QARequest) -> dict:
    """Answer an operator's question (e.g. "why are payments failing",
    "which PSP is down") using only already-detected incident data.
    Read-only: calls no code path that can execute a payment action.
    The question is untrusted user text and is fenced before it ever
    reaches a prompt -- see src.llm.prompts.incident_qa_prompt."""
    incidents = _load_state()["incidents"]
    summaries = [_incident_summary(i, entry) for i, entry in enumerate(incidents)]

    result = answer_question(
        req.question,
        summaries,
        cache=_qa_cache,
        client=_get_llm_client(),
        offline=False,
    )
    return result.model_dump()


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
