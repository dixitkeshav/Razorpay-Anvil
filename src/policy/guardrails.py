"""Guardrails — [3] in the policy pipeline. Override expected value, never
the reverse: a guardrail's verdict always wins over whatever the EV
ranking picked. See docs/POLICY.md.

Six documented guardrail conditions (anvil-build-plan.md §8), plus a
fourth escalation trigger this module adds -- "no eligible automated
action" -- so the four ESCALATE_HUMAN conditions promised by
docs/PHASES.md Phase 6 are: amount threshold, low root-cause confidence,
mandate/autopay limits, and no eligible action surviving the gates. The
plan's own guardrail bullet list only names three explicit
ESCALATE_HUMAN triggers; this fourth is a deliberate, documented addition
(a safe default when automation has nothing eligible to do), not an
oversight -- see docs/JOURNAL.md.
"""

from src.policy import config
from src.policy.models import Action, PolicyContext


def escalation_reasons(ctx: PolicyContext, any_action_eligible: bool) -> list[str]:
    reasons = []
    if ctx.amount > config.AMOUNT_ESCALATION_THRESHOLD_PAISE:
        reasons.append(
            f"amount {ctx.amount} paise exceeds escalation threshold "
            f"{config.AMOUNT_ESCALATION_THRESHOLD_PAISE} paise"
        )
    if ctx.root_cause_confidence < config.CONFIDENCE_ESCALATION_THRESHOLD:
        reasons.append(
            f"root-cause confidence {ctx.root_cause_confidence:.2f} below threshold "
            f"{config.CONFIDENCE_ESCALATION_THRESHOLD:.2f}"
        )
    if ctx.is_mandate_debit:
        reasons.append("mandate/autopay debit -- requires human sign-off")
    if not any_action_eligible:
        reasons.append("no automated action (RETRY or REROUTE) survived eligibility gates")
    return reasons


def hold_reasons(ctx: PolicyContext, candidate_action: Action) -> list[str]:
    reasons = []
    if ctx.incident_state.value == "SEVERE" and candidate_action == Action.RETRY:
        reasons.append("incident state is SEVERE -- retrying would hammer a downed dependency")
    if ctx.merchant_hourly_spend_paise >= config.MERCHANT_HOURLY_BUDGET_PAISE:
        reasons.append(
            f"merchant hourly recovery budget spent "
            f"({ctx.merchant_hourly_spend_paise} >= {config.MERCHANT_HOURLY_BUDGET_PAISE} paise)"
        )
    if ctx.cooldown_active:
        reasons.append("cooldown active on this payment_id")
    return reasons
