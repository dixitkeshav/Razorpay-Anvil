"""Slice lattice constants — the dimensions the generator, and every layer
above it, slice traffic by. See docs/EPISODE-SPEC.md §2.
"""

METHODS = ["upi", "card", "netbanking", "wallet", "emi"]
METHOD_WEIGHTS = [0.55, 0.25, 0.12, 0.06, 0.02]

PSPS = ["PSP-A", "PSP-B", "PSP-C"]
PSP_WEIGHTS = [0.5, 0.3, 0.2]

ISSUERS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YESB"]
ISSUER_WEIGHTS = [0.22, 0.20, 0.20, 0.16, 0.14, 0.08]

REGIONS = ["Maharashtra", "Karnataka", "Delhi", "TamilNadu", "Rajasthan", "WestBengal"]
REGION_WEIGHTS = [0.24, 0.20, 0.18, 0.16, 0.12, 0.10]

MERCHANT_CATEGORIES = [
    "ecommerce",
    "food_delivery",
    "travel",
    "utilities",
    "gaming",
    "subscription",
]
MERCHANT_CATEGORY_WEIGHTS = [0.30, 0.22, 0.14, 0.14, 0.12, 0.08]

# 3 merchants per category, deterministic ids: M100 + category_index*10 + n
MERCHANTS_BY_CATEGORY: dict[str, list[str]] = {
    cat: [f"M{100 + i * 10 + n}" for n in range(3)] for i, cat in enumerate(MERCHANT_CATEGORIES)
}

WALLETS = ["paytm", "phonepe", "amazonpay"]

# Card BIN pools. "523" is reserved for Episode C (card BIN issue).
CARD_BIN_POOL = ["411111", "555555", "400000", "512345", "601111", "379412"]
EPISODE_C_BINS = ["523112", "523187", "523240"]

# Baseline success rate by method (steady state, before any per-slice offset)
BASELINE_SR_BY_METHOD = {
    "upi": 0.94,
    "card": 0.91,
    "netbanking": 0.89,
    "wallet": 0.93,
    "emi": 0.87,
}

# Baseline P95 latency (ms) by method
BASELINE_P95_LATENCY_MS_BY_METHOD = {
    "upi": 700,
    "card": 1500,
    "netbanking": 2200,
    "wallet": 900,
    "emi": 2500,
}

# Typical order amount (paise) log-normal center by merchant category
AMOUNT_MEDIAN_PAISE_BY_CATEGORY = {
    "ecommerce": 150_000,
    "food_delivery": 35_000,
    "travel": 900_000,
    "utilities": 80_000,
    "gaming": 20_000,
    "subscription": 50_000,
}

ERROR_VOCAB = {
    # customer-side failures — routine, not incident-caused
    "customer": [
        (
            "BAD_REQUEST_ERROR",
            "authentication",
            "payment_failed",
            "insufficient funds in the account",
        ),
        ("BAD_REQUEST_ERROR", "authentication", "payment_failed", "otp incorrect or expired"),
        (
            "BAD_REQUEST_ERROR",
            "authorization",
            "payment_failed",
            "transaction declined by customer bank",
        ),
    ],
    # bank/gateway-side failures — what incidents drive
    "bank": [
        ("GATEWAY_ERROR", "authorization", "payment_failed", "issuing bank unavailable"),
        ("GATEWAY_ERROR", "authorization", "payment_failed", "bank server timeout"),
    ],
    "gateway": [
        ("GATEWAY_ERROR", "processing", "gateway_error", "psp gateway timeout"),
        ("SERVER_ERROR", "processing", "gateway_error", "psp internal error"),
    ],
    "business": [
        ("BAD_REQUEST_ERROR", "processing", "payment_failed", "risk engine declined the payment"),
    ],
}
