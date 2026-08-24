"""Simulation engine — L0. Emits PaymentAttempt-shaped rows plus a
ground-truth sidecar. See docs/EPISODE-SPEC.md.

This module is frozen once committed per CLAUDE.md rule #4.
"""

import math
import uuid
from datetime import UTC, datetime

import numpy as np

from src.generator import lattice as L
from src.generator.episodes import EpisodeSpec, build_episode_set

SIM_START_EPOCH = int(datetime(2026, 6, 1, tzinfo=UTC).timestamp())
HOLDOUT_START_EPOCH = int(datetime(2026, 6, 15, tzinfo=UTC).timestamp())

BASE_LAMBDA_PER_MIN = 120.0
ONBOARD_MERCHANT_ID = "M900"
ONBOARD_RAMP_MIN = 90


def _diurnal_multiplier(minute_of_day: int) -> float:
    hour = minute_of_day / 60.0
    # two humps (late morning, evening) on top of an overnight trough
    morning = math.exp(-((hour - 12.5) ** 2) / (2 * 4.0**2))
    evening = math.exp(-((hour - 20.0) ** 2) / (2 * 2.5**2))
    trough_floor = 0.18
    return trough_floor + 1.35 * morning + 0.9 * evening


def _p95_lognormal_params(p95_ms: float, sigma: float = 0.4) -> tuple[float, float]:
    mu = math.log(p95_ms) - 1.645 * sigma
    return mu, sigma


def _build_slice_sr_offsets(rng: np.random.Generator) -> dict[tuple[str, str, str], float]:
    offsets = {}
    for method in L.METHODS:
        for psp in L.PSPS:
            for issuer in L.ISSUERS:
                offsets[(method, psp, issuer)] = float(np.clip(rng.normal(0, 0.015), -0.04, 0.04))
    return offsets


def _active_episodes(episodes: list[EpisodeSpec], t: int) -> list[EpisodeSpec]:
    active = []
    for ep in episodes:
        if ep.decoy:
            continue
        lo, hi = ep.onset_min, ep.recovery_end_min
        if lo <= t <= hi:
            active.append(ep)
    return active


def _active_decoys(episodes: list[EpisodeSpec], t: int) -> list[EpisodeSpec]:
    return [ep for ep in episodes if ep.decoy and ep.onset_min <= t <= ep.recovery_end_min]


def simulate(
    seed: int, sim_minutes: int = 4320, start_epoch: int = SIM_START_EPOCH
) -> tuple[list[dict], list[dict]]:
    rng = np.random.default_rng(seed)
    episodes = build_episode_set(rng, sim_minutes)
    sr_offsets = _build_slice_sr_offsets(rng)

    events: list[dict] = []

    for t in range(sim_minutes):
        minute_of_day = t % 1440
        lam = BASE_LAMBDA_PER_MIN * _diurnal_multiplier(minute_of_day)

        decoys = _active_decoys(episodes, t)
        volume_decoy = next((d for d in decoys if d.episode_type == "decoy_volume_spike"), None)
        onboarding_decoy = next(
            (d for d in decoys if d.episode_type == "decoy_onboarding"), None
        )
        if volume_decoy is not None:
            eco_share = L.MERCHANT_CATEGORY_WEIGHTS[L.MERCHANT_CATEGORIES.index("ecommerce")]
            lam *= 1 + eco_share * (volume_decoy.volume_multiplier - 1)

        n_t = rng.poisson(lam)
        if n_t == 0:
            continue

        active_eps = _active_episodes(episodes, t)

        method_arr = rng.choice(L.METHODS, size=n_t, p=L.METHOD_WEIGHTS)
        psp_arr = rng.choice(L.PSPS, size=n_t, p=L.PSP_WEIGHTS)
        issuer_arr = rng.choice(L.ISSUERS, size=n_t, p=L.ISSUER_WEIGHTS)
        region_arr = rng.choice(L.REGIONS, size=n_t, p=L.REGION_WEIGHTS)
        category_arr = rng.choice(
            L.MERCHANT_CATEGORIES, size=n_t, p=L.MERCHANT_CATEGORY_WEIGHTS
        )

        onboarding_frac = 0.0
        if onboarding_decoy is not None and t >= onboarding_decoy.onset_min:
            onboarding_frac = min(1.0, (t - onboarding_decoy.onset_min) / ONBOARD_RAMP_MIN) * 0.25

        merchant_arr = np.empty(n_t, dtype=object)
        onboard_roll = rng.random(n_t)
        for i in range(n_t):
            cat = category_arr[i]
            if (
                cat == "ecommerce"
                and onboarding_decoy is not None
                and onboard_roll[i] < onboarding_frac
            ):
                merchant_arr[i] = ONBOARD_MERCHANT_ID
            else:
                merchants = L.MERCHANTS_BY_CATEGORY[cat]
                merchant_arr[i] = merchants[rng.integers(0, len(merchants))]

        bin_roll = rng.random(n_t)
        bin_arr = np.empty(n_t, dtype=object)
        for i in range(n_t):
            if method_arr[i] != "card":
                bin_arr[i] = None
            elif bin_roll[i] < 0.15:
                bin_arr[i] = L.EPISODE_C_BINS[rng.integers(0, len(L.EPISODE_C_BINS))]
            else:
                bin_arr[i] = L.CARD_BIN_POOL[rng.integers(0, len(L.CARD_BIN_POOL))]

        amount_arr = np.empty(n_t, dtype=np.int64)
        for cat in L.MERCHANT_CATEGORIES:
            mask = category_arr == cat
            n_cat = int(mask.sum())
            if n_cat == 0:
                continue
            median = L.AMOUNT_MEDIAN_PAISE_BY_CATEGORY[cat]
            draws = rng.lognormal(mean=math.log(median), sigma=0.6, size=n_cat)
            amount_arr[mask] = np.clip(draws, 100, 5_000_000).astype(np.int64)

        latency_arr = np.empty(n_t, dtype=np.int64)
        for method in L.METHODS:
            mask = method_arr == method
            n_m = int(mask.sum())
            if n_m == 0:
                continue
            p95 = L.BASELINE_P95_LATENCY_MS_BY_METHOD[method]
            mu, sigma = _p95_lognormal_params(p95)
            draws = rng.lognormal(mean=mu, sigma=sigma, size=n_m)
            latency_arr[mask] = draws.astype(np.int64)

        sr_arr = np.array(
            [
                float(
                    np.clip(
                        L.BASELINE_SR_BY_METHOD[method_arr[i]]
                        + sr_offsets[(method_arr[i], psp_arr[i], issuer_arr[i])],
                        0.5,
                        0.99,
                    )
                )
                for i in range(n_t)
            ]
        )
        confidence_arr = np.clip(sr_arr + rng.normal(0, 0.03, size=n_t), 0.05, 0.99)
        episode_id_arr: list[str | None] = [None] * n_t
        latency_mult_arr = np.ones(n_t)

        for ep in active_eps:
            frac = ep.effect_fraction(t)
            if frac <= 0 and not ep.persistent:
                continue
            ctxs = [
                {
                    "method": method_arr[i],
                    "x_psp": psp_arr[i],
                    "x_issuer": issuer_arr[i],
                    "x_region": region_arr[i],
                    "x_merchant_id": merchant_arr[i],
                    "x_bin": bin_arr[i],
                }
                for i in range(n_t)
            ]
            match_mask = np.array([ep.matches(ctx) for ctx in ctxs])
            if not match_mask.any():
                continue

            tagged = ep.is_tagged(t)
            if ep.persistent:
                sr_arr[match_mask] = ep.target_sr
                confidence_arr[match_mask] = ep.oracle_confidence_override
            else:
                if ep.sr_drop:
                    sr_arr[match_mask] = np.clip(sr_arr[match_mask] - ep.sr_drop * frac, 0.02, 0.99)
                if ep.latency_multiplier:
                    latency_mult_arr[match_mask] = 1 + (ep.latency_multiplier - 1) * frac

            if tagged:
                for i in np.where(match_mask)[0]:
                    episode_id_arr[i] = ep.episode_id

        latency_arr = (latency_arr * latency_mult_arr).astype(np.int64)

        success_roll = rng.random(n_t)
        success_arr = success_roll < sr_arr

        error_source_roll = rng.random(n_t)

        for i in range(n_t):
            method = method_arr[i]
            success = bool(success_arr[i])
            eid = episode_id_arr[i]
            created_at = start_epoch + t * 60 + int(rng.integers(0, 60))
            pay_id = f"pay_{uuid.uuid4().hex[:14]}"
            order_id = f"order_{uuid.uuid4().hex[:14]}"

            bank = issuer_arr[i]
            if method == "upi":
                handle = psp_arr[i].lower().replace("psp-", "psp")
                vpa = f"user{rng.integers(1000, 999999)}@{handle}"
            else:
                vpa = None
            wallet = L.WALLETS[rng.integers(0, len(L.WALLETS))] if method == "wallet" else None
            card_id = f"card_{uuid.uuid4().hex[:12]}" if method == "card" else None

            error_code = error_desc = error_source = error_step = error_reason = None
            status = "captured" if success else "failed"
            if not success:
                if eid in ("ep-A", "ep-D", "ep-G1"):
                    source = "bank"
                elif eid in ("ep-C", "ep-G2"):
                    source = "bank"
                elif eid == "ep-B":
                    source = "gateway"
                else:
                    r = error_source_roll[i]
                    if r < 0.70:
                        source = "customer"
                    elif r < 0.85:
                        source = "bank"
                    elif r < 0.95:
                        source = "gateway"
                    else:
                        source = "business"
                vocab = L.ERROR_VOCAB[source]
                error_code, error_step, error_reason, error_desc = vocab[
                    int(rng.integers(0, len(vocab)))
                ]
                error_source = source

            events.append(
                {
                    "id": pay_id,
                    "order_id": order_id,
                    "entity": "payment",
                    "amount": int(amount_arr[i]),
                    "currency": "INR",
                    "status": status,
                    "method": method,
                    "bank": bank if method in ("card", "netbanking") else None,
                    "wallet": wallet,
                    "vpa": vpa,
                    "card_id": card_id,
                    "international": False,
                    "captured": success,
                    "description": None,
                    "error_code": error_code,
                    "error_description": error_desc,
                    "error_source": error_source,
                    "error_step": error_step,
                    "error_reason": error_reason,
                    "created_at": created_at,
                    "x_psp": psp_arr[i],
                    "x_issuer": issuer_arr[i],
                    "x_bin": bin_arr[i],
                    "x_attempt_number": 1,
                    "x_latency_ms": int(latency_arr[i]),
                    "x_region": region_arr[i],
                    "x_merchant_id": merchant_arr[i],
                    "x_merchant_category": category_arr[i],
                    "x_route_confidence": float(confidence_arr[i]),
                    "x_episode_id": eid,
                }
            )

    ground_truth = [
        {
            "episode_id": ep.episode_id,
            "episode_type": ep.episode_type,
            "tier": ep.tier,
            "decoy": ep.decoy,
            "slice_filter": ep.slice_filter,
            "onset_min": ep.onset_min,
            "plateau_start_min": ep.plateau_start_min,
            "plateau_end_min": ep.plateau_end_min,
            "recovery_end_min": ep.recovery_end_min,
            "description": ep.description,
        }
        for ep in episodes
    ]

    return events, ground_truth
