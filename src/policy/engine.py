"""Policy engine — L5, THE TRUST BOUNDARY.

    payment + incident context
       v
    [1] ELIGIBILITY GATES  -- src.policy.gates
       v
    [2] EXPECTED VALUE     -- src.policy.expected_value
       v
    [3] GUARDRAILS          -- src.policy.guardrails (override EV, never the reverse)
       v
    [4] DECISION + rationale

Every money action passes through `decide()`. No other module executes a
retry, reroute, or hold — CLAUDE.md rule #6. This module reads only its
PolicyContext argument: no ground truth, no LLM. Enforced by
tests/test_detector_ignores_ground_truth.py.
"""

from src.policy.expected_value import expected_value
from src.policy.gates import evaluate_all_gates, is_eligible
from src.policy.guardrails import escalation_reasons, hold_reasons
from src.policy.models import Action, Decision, PolicyContext

_EV_RANKED_ACTIONS = (Action.RETRY, Action.REROUTE)


def decide(ctx: PolicyContext) -> Decision:
    rationale: list[str] = []

    gate_results = evaluate_all_gates(ctx)
    eligible = {action: is_eligible(checks) for action, checks in gate_results.items()}
    for action, checks in gate_results.items():
        failed = [c.reason for c in checks if not c.passed]
        if failed:
            rationale.append(f"{action.value} ineligible: {'; '.join(failed)}")
        else:
            rationale.append(f"{action.value} eligible")

    ev_by_action: dict[Action, float] = {}
    for action in _EV_RANKED_ACTIONS:
        if eligible[action]:
            ev = expected_value(action, ctx)
            ev_by_action[action] = ev
            rationale.append(f"EV({action.value}) = {ev:.0f} paise")

    any_action_eligible = any(eligible[a] for a in _EV_RANKED_ACTIONS)
    candidate_action = (
        max(ev_by_action, key=ev_by_action.get) if ev_by_action else Action.HOLD
    )
    if ev_by_action:
        rationale.append(f"EV ranking selects {candidate_action.value}")
    else:
        rationale.append("no EV-ranked action eligible; candidate defaults to HOLD")

    esc_reasons = escalation_reasons(ctx, any_action_eligible)
    if esc_reasons:
        rationale.append(f"guardrail overrides to ESCALATE_HUMAN: {'; '.join(esc_reasons)}")
        return Decision(
            action=Action.ESCALATE_HUMAN,
            rationale=rationale,
            gate_results=gate_results,
            ev_by_action=ev_by_action,
            escalation_reasons=esc_reasons,
        )

    hold_reas = hold_reasons(ctx, candidate_action)
    if hold_reas:
        rationale.append(f"guardrail overrides to HOLD: {'; '.join(hold_reas)}")
        return Decision(
            action=Action.HOLD,
            rationale=rationale,
            gate_results=gate_results,
            ev_by_action=ev_by_action,
            hold_reasons=hold_reas,
        )

    rationale.append(f"final decision: {candidate_action.value}")
    return Decision(
        action=candidate_action,
        rationale=rationale,
        gate_results=gate_results,
        ev_by_action=ev_by_action,
    )
