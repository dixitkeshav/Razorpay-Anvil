"""Outcome simulator — batch counterfactual replay (Phase 8) uses this
instead of real Razorpay calls, since real test-mode payment attempts
require a live checkout flow (card/OTP), not something a server-side
batch job can do at scale.

Draws a Bernoulli outcome for RETRY/REROUTE using docs/OUTCOME-MODEL.md's
p_retry_success / p_reroute_success — entirely independent of simulation
ground truth.
"""

import random

from src.policy import config
from src.policy.models import Action


def simulate_outcome(action: Action, rng: random.Random) -> bool:
    if action == Action.RETRY:
        p = config.P_RETRY_SUCCESS
    elif action == Action.REROUTE:
        p = config.P_REROUTE_SUCCESS
    else:
        return False  # HOLD/ESCALATE_HUMAN never execute a payment outcome
    return rng.random() < p
