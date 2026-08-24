"""Policy engine data model — the trust boundary's input/output contract.

PolicyContext carries only what a real caller (the L4 impact/incident
layer, or later the ledger) would actually have on hand. It never carries
simulation ground truth, and idempotency/cooldown/budget state is passed
in explicitly rather than looked up internally, so this module never
needs to import src/ledger/ or src/llm/ to make a decision — it is a pure
function of its inputs. Enforced by
tests/test_detector_ignores_ground_truth.py.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Action(StrEnum):
    RETRY = "RETRY"
    REROUTE = "REROUTE"
    HOLD = "HOLD"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class IncidentState(StrEnum):
    """Mirrors src.impact.state_machine.IncidentState. Duplicated (not
    imported) so the policy engine's public contract never depends on the
    impact layer's internal module structure — only on this enum's values.
    """

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    SEVERE = "SEVERE"
    RECOVERING = "RECOVERING"


class PolicyContext(BaseModel):
    # payment
    payment_id: str
    method: str
    amount: int  # paise
    attempt_number: int
    captured: bool
    idempotency_key: str
    created_at: int  # unix epoch seconds of this attempt
    now: int  # unix epoch seconds "now" -- for retry-window checks

    # incident
    incident_state: IncidentState
    root_cause_confidence: float = Field(ge=0.0, le=1.0)

    # routing
    x_psp: str
    alternate_psp_healthy: bool = True

    # operational state -- passed in explicitly; wired to the real ledger
    # in Phase 7, defaulted here so the policy engine has no dependency on
    # it existing yet
    idempotency_keys_used: frozenset[str] = frozenset()
    cooldown_active: bool = False
    merchant_id: str = ""
    merchant_hourly_spend_paise: int = 0
    is_mandate_debit: bool = False


class GateCheck(BaseModel):
    name: str
    passed: bool
    reason: str


class Decision(BaseModel):
    action: Action
    rationale: list[str]
    gate_results: dict[Action, list[GateCheck]]
    ev_by_action: dict[Action, float]
    escalation_reasons: list[str] = []
    hold_reasons: list[str] = []
