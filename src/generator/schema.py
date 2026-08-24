"""Event schema — Razorpay-shaped, non-negotiable. See anvil-build-plan.md §7.

Simulation-only fields are namespaced `x_`. `x_episode_id` is ground truth
and must never be read by src/detection/, src/attribution/, or src/policy/ —
enforced by tests/test_detector_ignores_ground_truth.py.
"""

from typing import Literal

from pydantic import BaseModel


class PaymentAttempt(BaseModel):
    id: str
    order_id: str
    entity: Literal["payment"] = "payment"
    amount: int
    currency: str = "INR"
    status: Literal["created", "authorized", "captured", "failed", "refunded"]
    method: Literal["upi", "card", "netbanking", "wallet", "emi"]
    bank: str | None = None
    wallet: str | None = None
    vpa: str | None = None
    card_id: str | None = None
    international: bool = False
    captured: bool
    description: str | None = None
    error_code: str | None = None
    error_description: str | None = None
    error_source: Literal["customer", "business", "bank", "gateway"] | None = None
    error_step: str | None = None
    error_reason: str | None = None
    created_at: int

    # ops extensions — namespaced so the boundary is obvious
    x_psp: str
    x_issuer: str
    x_bin: str | None = None
    x_attempt_number: int
    x_latency_ms: int
    x_region: str
    x_merchant_id: str
    x_merchant_category: str
    x_route_confidence: float
    x_episode_id: str | None = None


class GroundTruthEpisode(BaseModel):
    """Evaluation-only sidecar. Never read by detection/attribution/policy."""

    episode_id: str
    episode_type: str
    tier: str
    decoy: bool
    slice_filter: dict[str, str]
    onset_min: int
    plateau_start_min: int
    plateau_end_min: int
    recovery_end_min: int
    description: str
