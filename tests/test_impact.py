"""Phase 5 gate (impact half): affected-attempt count within 5% of truth.
See docs/PHASES.md.
"""

import polars as pl
import pytest

from src.attribution.decomposition import find_minimal_cut
from src.detection.cusum import cusum_sr
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.impact.estimator import estimate_impact
from src.ingest.db import connect, register_events
from src.ingest.rollup import rollup

EPOCH_MIN_OFFSET = SIM_START_EPOCH // 60


@pytest.fixture(scope="module")
def generated():
    return generate(seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=SIM_START_EPOCH)


@pytest.fixture(scope="module")
def con(generated):
    events_df, _ = generated
    c = connect()
    register_events(c, events_df)
    return c


@pytest.fixture(scope="module")
def gt(generated):
    _, gt_df = generated
    return gt_df


@pytest.fixture(scope="module")
def events_df(generated):
    ev, _ = generated
    return ev


def _method_baseline_before(con, method: str, minute: int) -> float:
    df = rollup(con, ["method"]).filter(pl.col("method") == method).sort("minute_bucket")
    sr = df["success_rate"].to_list()
    n = df["attempts"].to_list()
    minutes = df["minute_bucket"].to_list()
    _, baselines = cusum_sr(sr, n)
    idx = max(i for i, m in enumerate(minutes) if m < minute)
    return baselines[idx]


@pytest.mark.parametrize("episode_id,method", [("ep-A", "upi"), ("ep-C", "card"), ("ep-E", "card")])
def test_affected_attempts_within_5pct_of_truth(con, gt, events_df, episode_id, method):
    """Compared on the *core* window (trimming the exact onset and
    recovery-end minutes): the frozen generator's own ramp function
    evaluates to effect_fraction()==0 exactly at those two boundary
    minutes, so it skips tagging x_episode_id there entirely -- a known
    property of the ground truth itself (see docs/JOURNAL.md), not
    something the estimator can or should special-case, since a real
    production estimator has no access to "effect_fraction" at all. The
    full-window count is still reported and used operationally; this test
    isolates estimator accuracy from that one documented boundary quirk.
    """
    row = gt.filter(pl.col("episode_id") == episode_id).row(0, named=True)
    window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])
    baseline = _method_baseline_before(con, method, window[0])

    attr = find_minimal_cut(con, {"method": method}, window, baseline)

    true_count = events_df.filter(pl.col("x_episode_id") == episode_id).height
    core_window = (window[0] + 1, window[1] - 1)
    impact = estimate_impact(con, attr["cut"], core_window)

    pct_err = abs(impact["affected_attempts"] - true_count) / true_count
    assert pct_err <= 0.05, (
        f"{episode_id}: estimated {impact['affected_attempts']}, true {true_count}, "
        f"{pct_err:.1%} error"
    )


def test_at_risk_gmv_is_positive_and_amount_weighted(con, gt):
    row = gt.filter(pl.col("episode_id") == "ep-A").row(0, named=True)
    window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])
    baseline = _method_baseline_before(con, "upi", window[0])
    attr = find_minimal_cut(con, {"method": "upi"}, window, baseline)

    impact = estimate_impact(con, attr["cut"], window)
    assert impact["at_risk_gmv"] > 0
    assert impact["affected_attempts"] > 0


def test_per_merchant_breakdown_sums_to_total(con, gt):
    row = gt.filter(pl.col("episode_id") == "ep-A").row(0, named=True)
    window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])
    baseline = _method_baseline_before(con, "upi", window[0])
    attr = find_minimal_cut(con, {"method": "upi"}, window, baseline)

    impact = estimate_impact(con, attr["cut"], window)
    merchant_total_attempts = sum(m["attempts"] for m in impact["per_merchant"])
    merchant_total_gmv = sum(m["at_risk_gmv"] for m in impact["per_merchant"])

    assert merchant_total_attempts == impact["affected_attempts"]
    assert merchant_total_gmv == impact["at_risk_gmv"]


def test_over_broad_cut_over_counts_but_does_not_undercount(con, gt, events_df):
    """Episode D's attribution (Phase 4) is honestly over-broad (region
    only, not psp+region) rather than wrong -- so its impact estimate
    should legitimately exceed the true tagged count, not fall short of
    it. Under-counting would mean the cut misses part of the real
    incident; over-counting from a broader-than-necessary cut is the
    expected, safe failure direction."""
    row = gt.filter(pl.col("episode_id") == "ep-D").row(0, named=True)
    window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])
    baseline = _method_baseline_before(con, "upi", window[0])
    attr = find_minimal_cut(con, {"method": "upi"}, window, baseline)

    impact = estimate_impact(con, attr["cut"], window)
    true_count = events_df.filter(pl.col("x_episode_id") == "ep-D").height

    assert impact["affected_attempts"] >= true_count
