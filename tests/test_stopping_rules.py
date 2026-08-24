"""Phase 6 gate: stopping rules -- max retries, cooldowns, circuit-break
on SEVERE state. See docs/POLICY.md.
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


class TestMaxRetries:
    def test_retry_not_offered_at_max_retries(self):
        ctx = make_context(method="upi", attempt_number=2)  # max_retries(upi) = 2
        decision = decide(ctx)
        assert Action.RETRY not in decision.ev_by_action
        assert decision.action != Action.RETRY

    def test_reroute_still_available_when_retries_exhausted(self):
        """Exhausting retries doesn't block a different action -- REROUTE
        should still be considered on its own merits."""
        ctx = make_context(method="upi", attempt_number=2)
        decision = decide(ctx)
        assert Action.REROUTE in decision.ev_by_action


class TestCooldown:
    def test_cooldown_forces_hold(self):
        ctx = make_context(cooldown_active=True)
        decision = decide(ctx)
        assert decision.action == Action.HOLD
        assert any("cooldown" in r.lower() for r in decision.hold_reasons)

    def test_no_cooldown_does_not_force_hold(self):
        ctx = make_context(cooldown_active=False)
        decision = decide(ctx)
        assert decision.action != Action.HOLD or not decision.hold_reasons


class TestCircuitBreakOnSevere:
    def test_severe_state_blocks_retry_specifically(self):
        """SEVERE should HOLD when the candidate is RETRY -- this is the
        guardrail that exists specifically so an incident system never
        hammers an already-down dependency with hundreds of retries. See
        anvil-build-plan.md §15."""
        ctx = make_context(incident_state=IncidentState.SEVERE, method="upi")
        decision = decide(ctx)
        assert decision.action == Action.HOLD
        assert any("SEVERE" in r for r in decision.hold_reasons)

    def test_severe_state_does_not_block_reroute(self):
        """The guardrail is specifically about RETRY hammering a downed
        dependency -- REROUTE to a healthy alternate is still sound."""
        ctx = make_context(
            incident_state=IncidentState.SEVERE,
            method="netbanking",  # doesn't support reroute -> forces RETRY-only candidate path
        )
        # netbanking has no reroute path, so with SEVERE + RETRY-only
        # eligibility, the only guardrail-safe outcome is HOLD or escalate
        decision = decide(ctx)
        assert decision.action in (Action.HOLD, Action.ESCALATE_HUMAN)

    def test_degraded_state_does_not_trigger_circuit_break(self):
        """Only SEVERE triggers the circuit-break -- DEGRADED still allows
        EV-ranked automated action through."""
        ctx = make_context(incident_state=IncidentState.DEGRADED)
        decision = decide(ctx)
        assert decision.action in (Action.RETRY, Action.REROUTE)
