"""Policy engine configuration — every threshold named here, not buried in
logic. Outcome-model parameters (p_retry_success, p_reroute_success, costs)
are sourced from docs/OUTCOME-MODEL.md; do not change a default here
without updating that doc's basis column too.
"""

from src.policy.models import Action

# Outcome model — docs/OUTCOME-MODEL.md §2-3
P_RETRY_SUCCESS = 0.45
P_REROUTE_SUCCESS = 0.65
COST_RETRY_PAISE = 0
COST_REROUTE_PAISE = 5_000  # ₹50

# Eligibility gates
MAX_RETRIES_BY_METHOD: dict[str, int] = {
    "upi": 2,
    "card": 2,
    "netbanking": 1,
    "wallet": 2,
    "emi": 1,
}
RETRY_WINDOW_SECONDS = 30 * 60  # an attempt older than this is no longer eligible for retry
METHODS_SUPPORTING_REROUTE = {"upi", "card", "wallet"}

# Guardrails — anvil-build-plan.md §8
AMOUNT_ESCALATION_THRESHOLD_PAISE = 50_000 * 100  # ₹50,000
CONFIDENCE_ESCALATION_THRESHOLD = 0.80
MERCHANT_HOURLY_BUDGET_PAISE = 200_000 * 100  # ₹2,00,000/hour per merchant, a reasoned placeholder

ACTIONS_ELIGIBLE_FOR_EV = (Action.RETRY, Action.REROUTE)
