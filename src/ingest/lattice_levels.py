"""The slice lattice, as it applies to rollups — see anvil-build-plan.md §7
and docs/EPISODE-SPEC.md §2. Detection (L2) walks these levels top-down,
only drilling into a child once its parent fires.
"""

ALLOWED_DIMS = {
    "method",
    "x_psp",
    "x_issuer",
    "x_region",
    "x_merchant_id",
    "x_merchant_category",
}

LEVELS: dict[str, list[str]] = {
    "L0_overall": [],
    "L1_method": ["method"],
    "L2_method_psp": ["method", "x_psp"],
    "L3_method_psp_issuer": ["method", "x_psp", "x_issuer"],
    "L4_region": ["method", "x_psp", "x_issuer", "x_region"],
    "L4_merchant": ["method", "x_psp", "x_issuer", "x_merchant_id"],
}
