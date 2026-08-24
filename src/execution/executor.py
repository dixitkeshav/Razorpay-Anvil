"""Execution orchestration — L6. Every RETRY/REROUTE decision from the
policy engine passes through here before touching Razorpay or the
simulator; every outcome, and every non-executed decision (HOLD,
ESCALATE_HUMAN), is appended to the Recovery Ledger.

Idempotency is enforced here, before any external call: if
`ctx.idempotency_key` already has a ledger entry, that entry is returned
unchanged and nothing is executed again — this is what makes replaying a
key safe against a real Razorpay account, not just against our own
in-memory state. See tests/test_idempotency.py.
"""

import random
import time

from src.execution.razorpay_adapter import execute_recovery_order
from src.execution.simulator import simulate_outcome
from src.ledger.models import LedgerEntry
from src.ledger.store import LedgerStore
from src.policy.models import Action, Decision, PolicyContext


def execute(
    ctx: PolicyContext,
    decision: Decision,
    ledger: LedgerStore,
    mode: str = "simulate",
    client=None,
    rng: random.Random | None = None,
) -> LedgerEntry:
    """mode: "simulate" (default, used for batch replay) or
    "razorpay_test_mode" (real API calls, requires `client`)."""
    existing = ledger.find_by_idempotency_key(ctx.idempotency_key)
    if existing is not None:
        return existing

    execution_status = "not_executed"
    execution_detail: dict | None = None

    if decision.action in (Action.RETRY, Action.REROUTE):
        if mode == "razorpay_test_mode":
            if client is None:
                raise ValueError("razorpay_test_mode requires a client")
            order = execute_recovery_order(client, ctx.amount, "INR", ctx.idempotency_key)
            execution_status = "success"
            execution_detail = {"razorpay_order_id": order["id"]}
        elif mode == "simulate":
            success = simulate_outcome(decision.action, rng or random.Random())
            execution_status = "success" if success else "failed"
            execution_detail = {"simulated": True}
        else:
            raise ValueError(f"unknown execution mode: {mode}")

    return ledger.append(
        payment_id=ctx.payment_id,
        idempotency_key=ctx.idempotency_key,
        action=decision.action,
        rationale=decision.rationale,
        execution_status=execution_status,
        execution_detail=execution_detail,
        amount=ctx.amount,
        created_at=int(time.time()),
    )


def new_idempotency_key(payment_id: str, attempt_number: int) -> str:
    """Deterministic by design: the same logical retry of the same
    payment+attempt must produce the same key, or replaying it on a
    network timeout would no longer be safe against double-execution."""
    return f"{payment_id}:{attempt_number}"
