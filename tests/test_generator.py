"""Phase 1 gate: `make seed` emits >=100k events; every injected episode is
recoverable from ground truth; schema validates. See docs/PHASES.md.
"""

import polars as pl
import pytest

from src.generator import lattice as L
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate


@pytest.fixture(scope="module")
def generated():
    events_df, gt_df = generate(
        seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=SIM_START_EPOCH
    )
    return events_df, gt_df


def test_emits_at_least_100k_events(generated):
    events_df, _ = generated
    assert events_df.height >= 100_000


def test_ground_truth_has_all_episode_types(generated):
    _, gt_df = generated
    types = set(gt_df["episode_type"].to_list())
    expected = {
        "A_bank_degradation",
        "B_psp_timeout",
        "C_card_bin_issue",
        "D_regional",
        "E_merchant_specific",
        "F_calibration_drift",
        "G_concurrent",
        "decoy_volume_spike",
        "decoy_onboarding",
    }
    assert expected.issubset(types)


@pytest.mark.parametrize(
    "episode_id,method,expected_drop_min",
    [
        ("ep-A", "upi", 0.10),
        ("ep-C", "card", 0.25),
        ("ep-D", "upi", 0.08),
        ("ep-E", "card", 0.15),
        ("ep-F", "upi", 0.15),
        ("ep-G1", "upi", 0.08),
        ("ep-G2", "card", 0.10),
    ],
)
def test_episode_recoverable_sr_drop(generated, episode_id, method, expected_drop_min):
    """Every SR-shape episode leaves attempts tagged with its id whose
    realised success rate is materially below the method's steady-state
    baseline — i.e. it is recoverable purely from the emitted events plus
    the ground-truth sidecar, with no generator internals required."""
    events_df, _ = generated
    tagged = events_df.filter(pl.col("x_episode_id") == episode_id)
    assert tagged.height > 0, f"{episode_id} has no tagged attempts"

    baseline = L.BASELINE_SR_BY_METHOD[method]
    observed_sr = tagged["status"].eq("captured").mean()
    assert observed_sr < baseline - expected_drop_min


def test_episode_b_recoverable_latency_spike(generated):
    events_df, _ = generated
    tagged = events_df.filter(pl.col("x_episode_id") == "ep-B")
    assert tagged.height > 0

    # compare tagged P95 latency against the untagged PSP-A baseline P95
    untagged_pspA = events_df.filter(
        (pl.col("x_psp") == "PSP-A") & pl.col("x_episode_id").is_null()
    )
    tagged_p95 = tagged["x_latency_ms"].quantile(0.95)
    baseline_p95_val = untagged_pspA["x_latency_ms"].quantile(0.95)
    assert tagged_p95 > baseline_p95_val * 2


def test_episode_f_persistent_calibration_gap(generated):
    events_df, _ = generated
    tagged = events_df.filter(pl.col("x_episode_id") == "ep-F")
    assert tagged.height >= 100  # enough samples for a believable calibration read

    realised_sr = tagged["status"].eq("captured").mean()
    mean_confidence = tagged["x_route_confidence"].mean()
    assert realised_sr < 0.70
    assert mean_confidence > 0.85
    assert mean_confidence - realised_sr > 0.20


def test_decoy_onboarding_does_not_depress_success_rate(generated):
    events_df, _ = generated
    onboard = events_df.filter(pl.col("x_merchant_id") == "M900")
    assert onboard.height > 0

    ecommerce_baseline = events_df.filter(pl.col("x_merchant_category") == "ecommerce")
    onboard_sr = onboard["status"].eq("captured").mean()
    baseline_sr = ecommerce_baseline["status"].eq("captured").mean()
    assert abs(onboard_sr - baseline_sr) < 0.08


def test_decoy_volume_spike_does_not_carry_an_episode_tag(generated):
    events_df, _ = generated
    # decoys never appear in x_episode_id -- only real episodes do
    tags = set(events_df["x_episode_id"].drop_nulls().unique().to_list())
    assert "decoy-volume-spike" not in tags
    assert "decoy-onboarding" not in tags


def test_schema_valid_amounts_and_currency(generated):
    events_df, _ = generated
    assert (events_df["amount"] > 0).all()
    assert (events_df["currency"] == "INR").all()
    valid_statuses = ["created", "authorized", "captured", "failed", "refunded"]
    assert events_df["status"].is_in(valid_statuses).all()
