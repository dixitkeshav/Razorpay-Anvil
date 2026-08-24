"""Expected value — [2] in the policy pipeline. Only computed for actions
that survived eligibility gates. See docs/OUTCOME-MODEL.md §4.

EV(retry)   = p_retry_success   x amount - cost_retry
EV(reroute) = p_reroute_success x amount - cost_reroute
EV(hold)    = 0
"""

from src.policy import config
from src.policy.models import Action, PolicyContext


def expected_value(action: Action, ctx: PolicyContext) -> float:
    if action == Action.RETRY:
        return config.P_RETRY_SUCCESS * ctx.amount - config.COST_RETRY_PAISE
    if action == Action.REROUTE:
        return config.P_REROUTE_SUCCESS * ctx.amount - config.COST_REROUTE_PAISE
    if action == Action.HOLD:
        return 0.0
    if action == Action.ESCALATE_HUMAN:
        return 0.0  # not EV-ranked -- escalation is a guardrail outcome, not a bid
    raise ValueError(f"unknown action: {action}")
