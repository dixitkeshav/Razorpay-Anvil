"""Eligibility gates — [1] in the policy pipeline. Hard, deterministic,
fail-closed: any check that cannot be positively confirmed makes the
action ineligible, never the reverse. See docs/POLICY.md.
"""

from src.policy import config
from src.policy.models import Action, GateCheck, PolicyContext


def _check(name: str, passed: bool, reason: str) -> GateCheck:
    return GateCheck(name=name, passed=passed, reason=reason)


def retry_gates(ctx: PolicyContext) -> list[GateCheck]:
    max_retries = config.MAX_RETRIES_BY_METHOD.get(ctx.method)
    checks = [
        _check(
            "method_has_retry_policy",
            max_retries is not None,
            f"no configured max_retries for method={ctx.method}"
            if max_retries is None
            else "ok",
        ),
    ]
    if max_retries is not None:
        checks.append(
            _check(
                "attempt_below_max_retries",
                ctx.attempt_number < max_retries,
                f"attempt {ctx.attempt_number} >= max_retries {max_retries} for {ctx.method}",
            )
        )
    checks.append(
        _check(
            "not_already_captured",
            not ctx.captured,
            "payment already captured -- retrying would risk a duplicate charge",
        )
    )
    checks.append(
        _check(
            "within_retry_window",
            (ctx.now - ctx.created_at) <= config.RETRY_WINDOW_SECONDS,
            f"attempt is {ctx.now - ctx.created_at}s old, "
            f"exceeds the {config.RETRY_WINDOW_SECONDS}s retry window",
        )
    )
    checks.append(
        _check(
            "idempotency_key_unused",
            ctx.idempotency_key not in ctx.idempotency_keys_used,
            "idempotency key already used -- refusing to replay",
        )
    )
    return checks


def reroute_gates(ctx: PolicyContext) -> list[GateCheck]:
    checks = [
        _check(
            "method_supports_reroute",
            ctx.method in config.METHODS_SUPPORTING_REROUTE,
            f"method={ctx.method} has no alternate-PSP routing path",
        ),
        _check(
            "not_already_captured",
            not ctx.captured,
            "payment already captured -- rerouting would risk a duplicate charge",
        ),
        _check(
            "alternate_psp_healthy",
            ctx.alternate_psp_healthy,
            "no healthy alternate PSP available for this method",
        ),
        _check(
            "idempotency_key_unused",
            ctx.idempotency_key not in ctx.idempotency_keys_used,
            "idempotency key already used -- refusing to replay",
        ),
    ]
    return checks


def hold_gates(ctx: PolicyContext) -> list[GateCheck]:
    # HOLD is always eligible -- doing nothing is the fail-safe default.
    return [_check("always_eligible", True, "ok")]


def escalate_gates(ctx: PolicyContext) -> list[GateCheck]:
    # ESCALATE_HUMAN is always eligible -- surfacing to an operator is
    # always a safe fallback.
    return [_check("always_eligible", True, "ok")]


GATE_FUNCTIONS = {
    Action.RETRY: retry_gates,
    Action.REROUTE: reroute_gates,
    Action.HOLD: hold_gates,
    Action.ESCALATE_HUMAN: escalate_gates,
}


def is_eligible(checks: list[GateCheck]) -> bool:
    return all(c.passed for c in checks)


def evaluate_all_gates(ctx: PolicyContext) -> dict[Action, list[GateCheck]]:
    return {action: fn(ctx) for action, fn in GATE_FUNCTIONS.items()}
