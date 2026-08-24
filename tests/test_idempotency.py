"""Phase 7 gate: replaying the same idempotency key does not double-charge;
>=1 real test-mode recovery completes. See docs/PHASES.md.
"""

import os

import pytest

from src.execution.executor import execute, new_idempotency_key
from src.ledger.store import LedgerStore
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


def test_replaying_key_returns_the_same_entry_without_reexecuting():
    ledger = LedgerStore()
    ctx = make_context(idempotency_key="replay-me")
    decision = decide(ctx)
    assert decision.action in (Action.RETRY, Action.REROUTE)

    first = execute(ctx, decision, ledger, mode="simulate")
    second = execute(ctx, decision, ledger, mode="simulate")

    assert first.entry_id == second.entry_id
    assert len(ledger) == 1  # not 2 -- the replay never re-executed


def test_replaying_key_does_not_call_the_execution_backend_twice():
    """Even if the underlying action would be non-deterministic (a coin
    flip, a real API call), a replay must short-circuit before reaching
    it -- verified here by making the simulated outcome itself
    non-deterministic and checking the ledger only ever recorded one
    outcome for this key."""
    import random

    ledger = LedgerStore()
    ctx = make_context(idempotency_key="replay-nondeterministic")
    decision = decide(ctx)

    call_count = 0
    real_random = random.Random(1)

    class CountingRandom(random.Random):
        def random(self):
            nonlocal call_count
            call_count += 1
            return real_random.random()

    rng = CountingRandom()
    execute(ctx, decision, ledger, mode="simulate", rng=rng)
    execute(ctx, decision, ledger, mode="simulate", rng=rng)

    assert call_count == 1  # the rng was only consulted once
    assert len(ledger) == 1


def test_hold_and_escalate_decisions_never_execute_but_still_ledger():
    ledger = LedgerStore()
    ctx = make_context(incident_state=IncidentState.SEVERE)  # forces HOLD
    decision = decide(ctx)
    assert decision.action == Action.HOLD

    entry = execute(ctx, decision, ledger, mode="simulate")
    assert entry.execution_status == "not_executed"
    assert len(ledger) == 1  # still recorded in the ledger -- an audit trail entry


def test_new_idempotency_key_is_deterministic_per_attempt():
    k1 = new_idempotency_key("pay_1", 0)
    k2 = new_idempotency_key("pay_1", 0)
    k3 = new_idempotency_key("pay_1", 1)
    assert k1 == k2  # same logical retry -> same key
    assert k1 != k3  # different attempt -> different key


class TestRealRazorpayTestMode:
    """Requires real Razorpay test-mode keys in .env -- skips otherwise,
    same pattern as tests/test_phase0_razorpay_auth.py."""

    @staticmethod
    def _client_or_skip():
        from src.execution.razorpay_adapter import get_client

        key_id = os.environ.get("RAZORPAY_KEY_ID", "")
        if not key_id.startswith("rzp_test_"):
            pytest.skip("RAZORPAY_KEY_ID/SECRET not set to test-mode keys in .env")
        return get_client()

    def test_a_real_recovery_completes(self):
        client = self._client_or_skip()
        ledger = LedgerStore()
        ctx = make_context(idempotency_key="anvil-phase7-real-recovery-smoke-test")
        decision = decide(ctx)
        assert decision.action in (Action.RETRY, Action.REROUTE)

        entry = execute(ctx, decision, ledger, mode="razorpay_test_mode", client=client)

        assert entry.execution_status == "success"
        assert entry.execution_detail["razorpay_order_id"].startswith("order_")

    def test_replaying_key_against_real_razorpay_does_not_call_again(self):
        client = self._client_or_skip()
        ledger = LedgerStore()
        ctx = make_context(idempotency_key="anvil-phase7-real-replay-smoke-test")
        decision = decide(ctx)

        call_count = 0
        real_create = client.order.create

        def counting_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return real_create(*args, **kwargs)

        client.order.create = counting_create

        execute(ctx, decision, ledger, mode="razorpay_test_mode", client=client)
        execute(ctx, decision, ledger, mode="razorpay_test_mode", client=client)

        assert call_count == 1  # the real API was only ever hit once
        assert len(ledger) == 1
