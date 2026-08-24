"""Phase 6 gate: every gate has a passing unit test; no action can bypass
[3] (guardrails). See docs/PHASES.md and docs/POLICY.md.
"""

from src.policy.engine import decide
from src.policy.gates import is_eligible, reroute_gates, retry_gates
from src.policy.models import Action, IncidentState, PolicyContext

BASE_TIME = 1_800_000_000


def make_context(**overrides) -> PolicyContext:
    defaults = dict(
        payment_id="pay_abc123",
        method="upi",
        amount=100_00,  # ₹100
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


class TestRetryGates:
    def test_eligible_when_all_conditions_met(self):
        ctx = make_context(attempt_number=0)
        assert is_eligible(retry_gates(ctx))

    def test_ineligible_at_max_retries(self):
        ctx = make_context(method="card", attempt_number=2)  # max_retries(card) = 2
        assert not is_eligible(retry_gates(ctx))

    def test_ineligible_when_already_captured(self):
        ctx = make_context(captured=True)
        assert not is_eligible(retry_gates(ctx))

    def test_ineligible_outside_retry_window(self):
        ctx = make_context(now=BASE_TIME + 3600)  # 1 hour later, window is 30 min
        assert not is_eligible(retry_gates(ctx))

    def test_ineligible_when_idempotency_key_reused(self):
        ctx = make_context(
            idempotency_key="used-key", idempotency_keys_used=frozenset({"used-key"})
        )
        assert not is_eligible(retry_gates(ctx))


class TestRerouteGates:
    def test_eligible_when_all_conditions_met(self):
        ctx = make_context(method="upi")
        assert is_eligible(reroute_gates(ctx))

    def test_ineligible_for_netbanking(self):
        ctx = make_context(method="netbanking")
        assert not is_eligible(reroute_gates(ctx))

    def test_ineligible_when_already_captured(self):
        ctx = make_context(captured=True)
        assert not is_eligible(reroute_gates(ctx))

    def test_ineligible_when_no_healthy_alternate_psp(self):
        ctx = make_context(alternate_psp_healthy=False)
        assert not is_eligible(reroute_gates(ctx))

    def test_ineligible_when_idempotency_key_reused(self):
        ctx = make_context(
            idempotency_key="used-key", idempotency_keys_used=frozenset({"used-key"})
        )
        assert not is_eligible(reroute_gates(ctx))


class TestHoldAndEscalateAlwaysEligible:
    def test_hold_always_eligible(self):
        from src.policy.gates import hold_gates

        assert is_eligible(hold_gates(make_context(captured=True)))

    def test_escalate_always_eligible(self):
        from src.policy.gates import escalate_gates

        assert is_eligible(escalate_gates(make_context(captured=True)))


class TestGuardrailsCannotBeBypassed:
    def test_severe_state_forces_hold_even_though_retry_has_higher_ev(self):
        """RETRY would otherwise win on EV (cheap, no cost, decent success
        probability) -- the SEVERE guardrail must still override it."""
        ctx = make_context(incident_state=IncidentState.SEVERE)
        decision = decide(ctx)
        assert decision.action == Action.HOLD
        assert Action.RETRY in decision.ev_by_action  # RETRY *was* eligible and ranked

    def test_large_amount_forces_escalation_even_though_retry_has_higher_ev(self):
        ctx = make_context(amount=60_000_00)  # ₹60,000 > ₹50,000 threshold
        decision = decide(ctx)
        assert decision.action == Action.ESCALATE_HUMAN
        assert Action.RETRY in decision.ev_by_action

    def test_ordinary_case_lets_ev_ranking_through_when_no_guardrail_fires(self):
        ctx = make_context()
        decision = decide(ctx)
        assert decision.action in (Action.RETRY, Action.REROUTE)
        assert decision.action == max(decision.ev_by_action, key=decision.ev_by_action.get)
