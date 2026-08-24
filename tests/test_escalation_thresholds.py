"""Phase 6 gate: escalation triggers on all four documented conditions.
See docs/POLICY.md for why there are four, not the three named in
anvil-build-plan.md's original guardrail list.
"""

from src.policy.engine import decide
from src.policy.models import Action, IncidentState, PolicyContext

BASE_TIME = 1_800_000_000


def make_context(**overrides) -> PolicyContext:
    defaults = dict(
        payment_id="pay_abc123",
        method="upi",
        amount=100_00,
        attempt_number=0,
        captured=False,
        idempotency_key="idem-1",
        created_at=BASE_TIME,
        now=BASE_TIME + 60,
        incident_state=IncidentState.NORMAL,
        root_cause_confidence=0.95,
        x_psp="PSP-A",
        alternate_psp_healthy=True,
    )
    defaults.update(overrides)
    return PolicyContext(**defaults)


def test_escalates_on_large_amount():
    ctx = make_context(amount=50_001_00)  # ₹50,001 > ₹50,000 threshold
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
    assert any("amount" in r for r in decision.escalation_reasons)


def test_escalates_on_low_root_cause_confidence():
    ctx = make_context(root_cause_confidence=0.5)
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
    assert any("confidence" in r for r in decision.escalation_reasons)


def test_escalates_on_mandate_debit():
    ctx = make_context(is_mandate_debit=True)
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
    assert any("mandate" in r.lower() for r in decision.escalation_reasons)


def test_escalates_when_no_automated_action_eligible():
    """netbanking doesn't support reroute; exhausting retries leaves
    nothing for RETRY or REROUTE to do -- must escalate, not silently
    HOLD forever with no path back to a human."""
    ctx = make_context(method="netbanking", attempt_number=1)  # max_retries(netbanking) = 1
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
    assert any("no automated action" in r for r in decision.escalation_reasons)


def test_does_not_escalate_on_an_ordinary_payment():
    ctx = make_context()
    decision = decide(ctx)
    assert decision.action != Action.ESCALATE_HUMAN
    assert decision.escalation_reasons == []


def test_amount_and_confidence_can_both_trigger_together():
    ctx = make_context(amount=60_000_00, root_cause_confidence=0.4)
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
    assert len(decision.escalation_reasons) >= 2


def test_escalation_takes_priority_over_hold_guardrails():
    """If both an escalation and a hold condition fire, escalation wins --
    see docs/POLICY.md."""
    ctx = make_context(
        amount=60_000_00,
        incident_state=IncidentState.SEVERE,  # would otherwise trigger HOLD
    )
    decision = decide(ctx)
    assert decision.action == Action.ESCALATE_HUMAN
