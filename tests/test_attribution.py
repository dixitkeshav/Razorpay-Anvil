"""Phase 4 gate: names the correct slice on episodes A, C, D, E; reports
over-broad rather than wrong on G. See docs/PHASES.md.
"""

import ast

import polars as pl
import pytest

from src.attribution.decomposition import find_minimal_cut
from src.detection.cusum import cusum_sr
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
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


def _episode_window(gt_df: pl.DataFrame, episode_id: str) -> tuple[int, int]:
    row = gt_df.filter(pl.col("episode_id") == episode_id).row(0, named=True)
    return EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"]


def _true_slice(gt_df: pl.DataFrame, episode_id: str) -> dict:
    row = gt_df.filter(pl.col("episode_id") == episode_id).row(0, named=True)
    raw = ast.literal_eval(row["slice_filter"])
    # the generator's ground truth already uses x_-prefixed keys (x_issuer,
    # x_psp, x_region, x_merchant_id) matching attribution's dimension
    # names, except bin_prefix, which attribution exposes as x_bin_prefix.
    return {("x_bin_prefix" if k == "bin_prefix" else k): v for k, v in raw.items()}


def _method_baseline_before(con, method: str, minute: int) -> float:
    """The detector's own CUSUM baseline for this method, right before
    `minute` -- an honest, ground-truth-free baseline, exactly what
    src.detection.detector would hand attribution in a real pipeline."""
    df = rollup(con, ["method"]).filter(pl.col("method") == method).sort("minute_bucket")
    sr = df["success_rate"].to_list()
    n = df["attempts"].to_list()
    minutes = df["minute_bucket"].to_list()
    _, baselines = cusum_sr(sr, n)
    idx = max(i for i, m in enumerate(minutes) if m < minute)
    return baselines[idx]


def _consistent(cut: dict, true_slice: dict) -> bool:
    """Never wrong: every dimension the cut names must agree with the true
    cause. The cut may be a subset (over-broad) but must not contradict."""
    return all(cut.get(k) == v for k, v in true_slice.items() if k in cut)


@pytest.mark.parametrize(
    "episode_id,method",
    [("ep-A", "upi"), ("ep-C", "card"), ("ep-E", "card")],
)
def test_names_the_exact_correct_slice(con, gt, episode_id, method):
    window = _episode_window(gt, episode_id)
    true_slice = _true_slice(gt, episode_id)
    baseline = _method_baseline_before(con, method, window[0])

    result = find_minimal_cut(con, {"method": method}, window, baseline)

    assert result["cut"] == true_slice, f"{episode_id}: cut {result['cut']} != true {true_slice}"


def test_episode_d_is_correct_though_possibly_partial(con, gt):
    """D is Hard tier: a low-volume regional slice. Attribution must never
    contradict the true cause, but is allowed to under-specify it (name
    region without psp, say) when the evidence for a further refinement
    isn't statistically justified -- over-broad, not wrong."""
    window = _episode_window(gt, "ep-D")
    true_slice = _true_slice(gt, "ep-D")
    baseline = _method_baseline_before(con, "upi", window[0])

    result = find_minimal_cut(con, {"method": "upi"}, window, baseline)

    assert _consistent(result["cut"], true_slice), (
        f"ep-D: cut {result['cut']} contradicts true cause {true_slice}"
    )
    assert len(result["cut"]) > 1, "ep-D: attribution found nothing beyond the parent slice"


def test_episode_g_concurrent_causes_not_confused(con, gt):
    """G is two unrelated causes (different methods) overlapping in time.
    Attribution, run once per method-level parent, must name each cause
    correctly and never blend one episode's cause into the other's cut."""
    g1_window = _episode_window(gt, "ep-G1")
    g1_true = _true_slice(gt, "ep-G1")
    g1_baseline = _method_baseline_before(con, "upi", g1_window[0])
    g1_result = find_minimal_cut(con, {"method": "upi"}, g1_window, g1_baseline)

    g2_window = _episode_window(gt, "ep-G2")
    g2_true = _true_slice(gt, "ep-G2")
    g2_baseline = _method_baseline_before(con, "card", g2_window[0])
    g2_result = find_minimal_cut(con, {"method": "card"}, g2_window, g2_baseline)

    assert _consistent(g1_result["cut"], g1_true), (
        f"ep-G1: cut {g1_result['cut']} contradicts true cause {g1_true}"
    )
    assert _consistent(g2_result["cut"], g2_true), (
        f"ep-G2: cut {g2_result['cut']} contradicts true cause {g2_true}"
    )
    # neither cut should reach for the other episode's cause -- that would
    # be the "confounded" failure mode G is designed to test for
    assert "x_bin_prefix" not in g1_result["cut"]
    assert "x_issuer" not in g2_result["cut"]


class TestFindMinimalCutUnit:
    def test_no_cut_beyond_parent_when_nothing_localized(self):
        """A synthetic connection with a flat, undifferentiated slice
        should never invent a cause."""
        import duckdb

        con = duckdb.connect(":memory:")
        rows = []
        for t in range(100):
            for i in range(20):
                rows.append(
                    {
                        "created_at": t * 60,
                        "status": "captured" if i % 10 != 0 else "failed",
                        "method": "upi",
                        "x_psp": "PSP-A",
                        "x_issuer": "HDFC",
                        "x_region": "Delhi",
                        "x_merchant_id": "M100",
                        "x_bin": None,
                    }
                )
        df = pl.DataFrame(rows)
        register_events(con, df)

        result = find_minimal_cut(con, {"method": "upi"}, (0, 99), 0.9)
        assert result["cut"] == {"method": "upi"}
