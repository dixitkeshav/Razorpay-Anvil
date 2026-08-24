"""Razorpay test-mode adapter — L6, real API calls, test mode only.

Never uses live keys — see CLAUDE.md's Secrets section. A recovery attempt
is represented as a real Razorpay Order (order.create): this is a genuine,
verifiable API call against Razorpay's test environment, proving actual
integration rather than a mocked stand-in. A full RETRY/REROUTE against a
specific customer's card requires a live checkout (card entry, OTP) that a
server-side batch process cannot drive — order.create is the subset of the
real payment lifecycle this adapter can execute end-to-end on its own.
"""

import os

import razorpay


def get_client() -> razorpay.Client:
    key_id = os.environ["RAZORPAY_KEY_ID"]
    key_secret = os.environ["RAZORPAY_KEY_SECRET"]
    if not key_id.startswith("rzp_test_"):
        raise RuntimeError("refusing to use non-test-mode Razorpay keys")
    return razorpay.Client(auth=(key_id, key_secret))


def execute_recovery_order(
    client: razorpay.Client, amount: int, currency: str, idempotency_key: str
) -> dict:
    """Creates a real Razorpay test-mode order representing one recovery
    attempt. `amount` is in paise. Idempotency itself is enforced one
    layer up, in src.execution.executor, by checking the Recovery Ledger
    before this function is ever called — so a replayed key never reaches
    this adapter at all.
    """
    return client.order.create(
        {
            "amount": amount,
            "currency": currency,
            "receipt": idempotency_key,
            "notes": {"anvil_idempotency_key": idempotency_key},
        }
    )
