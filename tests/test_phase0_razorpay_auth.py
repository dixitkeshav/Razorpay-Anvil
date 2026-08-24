"""Phase 0 gate: a real Razorpay test-mode order.create call succeeds.

This is the day-one test per docs/PHASES.md — auth friction is the classic
day-eater, so it is verified before anything else is built. Requires
RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET (test-mode) in .env.
"""

import os

import pytest
import razorpay


def _client() -> razorpay.Client:
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret or not key_id.startswith("rzp_test_"):
        pytest.skip(
            "RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET not set to test-mode keys in .env "
            "— see .env.example"
        )
    return razorpay.Client(auth=(key_id, key_secret))


def test_create_test_mode_order_returns_valid_order_id():
    client = _client()

    order = client.order.create(
        {
            "amount": 50000,  # paise -> ₹500.00
            "currency": "INR",
            "receipt": "anvil-phase0-smoke-test",
        }
    )

    assert order["id"].startswith("order_")
    assert order["amount"] == 50000
    assert order["currency"] == "INR"
    assert order["status"] in ("created", "attempted", "paid")
