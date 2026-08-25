"""Phase 10 gate: detects episode F, which every L2 detector misses;
calibration gap reported per slice. See docs/PHASES.md and
anvil-build-plan.md §6.
"""

import polars as pl
import pytest

from src.detection.detector import detect_incidents
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.ingest.db import connect, register_events
from src.quality.calibration import detect_calibration_drift
from src.quality.oracle import RoutingOracle, SimulatedOracle, VulcanOracle

EPOCH_MIN_OFFSET = SIM_START_EPOCH // 60
F_SLICE = {"method": "upi", "x_psp": "PSP-C", "x_issuer": "ICICI"}


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


def test_detects_episode_f(con, gt):
    row = gt.filter(pl.col("episode_id") == "ep-F").row(0, named=True)
    true_window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])

    results = detect_calibration_drift(con, ["method", "x_psp", "x_issuer"])
    hits = [r for r in results if r["slice"] == F_SLICE]

    assert hits, "episode F's slice was not flagged as a calibration-drift incident"
    hit = hits[0]
    lo, hi = hit["window"]
    assert lo <= true_window[1] and hi >= true_window[0]  # overlaps the true window
    assert hit["calibration_gap"] >= 0.15
    assert hit["mean_oracle_confidence"] > hit["realised_success_rate"]


def test_calibration_gap_reported_per_slice(con):
    results = detect_calibration_drift(con, ["method", "x_psp", "x_issuer"])
    assert results  # the run finds at least one flagged slice on this seed
    for r in results:
        assert set(r["slice"].keys()) == {"method", "x_psp", "x_issuer"}
        assert "calibration_gap" in r
        assert "realised_success_rate" in r
        assert "mean_oracle_confidence" in r
        assert r["duration_minutes"] >= 14


def test_l2_detector_does_not_see_episode_f_as_a_sustained_incident(con, gt):
    """L2 (CUSUM) compares a slice against its own history -- episode F
    has no changepoint, since the oracle has always been wrong here. L2
    can at best catch scattered single-minute noise near the slice, never
    a single coherent multi-minute incident the way L10 does."""
    row = gt.filter(pl.col("episode_id") == "ep-F").row(0, named=True)
    f_window = (EPOCH_MIN_OFFSET + row["onset_min"], EPOCH_MIN_OFFSET + row["recovery_end_min"])

    incidents = detect_incidents(con, metric="sr")
    overlapping = [
        r
        for r in incidents
        if r["slice"].get("method") == "upi"
        and r["slice"].get("x_psp") == "PSP-C"
        and r["slice"].get("x_issuer") == "ICICI"
        and r["window"][0] <= f_window[1]
        and r["window"][1] >= f_window[0]
    ]
    longest = max(
        (w[1] - w[0] + 1 for w in (r["window"] for r in overlapping)), default=0
    )
    assert longest < 14, (
        f"L2 detector found a {longest}-minute sustained incident on F's exact slice -- "
        "expected only short fragments, since F has no changepoint for CUSUM to find"
    )


class TestCalibrationUnit:
    def test_sustained_gap_is_flagged(self):
        import duckdb

        rows = []
        base = 0
        for t in range(60):
            for i in range(10):
                success = i < 3  # SR ~0.3
                rows.append(
                    {
                        "created_at": base + t * 60 + i,
                        "status": "captured" if success else "failed",
                        "method": "upi",
                        "x_psp": "PSP-A",
                        "x_issuer": "HDFC",
                        "x_route_confidence": 0.9,
                    }
                )
        con = duckdb.connect(":memory:")
        register_events(con, pl.DataFrame(rows))

        results = detect_calibration_drift(con, ["method", "x_psp", "x_issuer"])
        assert results
        assert results[0]["calibration_gap"] > 0.15

    def test_no_gap_when_confidence_tracks_reality(self):
        import duckdb

        rows = []
        for t in range(60):
            for i in range(10):
                success = i < 9  # SR ~0.9
                rows.append(
                    {
                        "created_at": t * 60 + i,
                        "status": "captured" if success else "failed",
                        "method": "upi",
                        "x_psp": "PSP-A",
                        "x_issuer": "HDFC",
                        "x_route_confidence": 0.9,  # matches reality
                    }
                )
        con = duckdb.connect(":memory:")
        register_events(con, pl.DataFrame(rows))

        results = detect_calibration_drift(con, ["method", "x_psp", "x_issuer"])
        assert results == []


class TestRoutingOracle:
    def test_vulcan_oracle_is_a_documented_stub(self):
        oracle = VulcanOracle()
        with pytest.raises(NotImplementedError):
            oracle.score_routes(None)

    def test_simulated_oracle_satisfies_the_protocol_shape(self):
        assert hasattr(SimulatedOracle, "score_routes")
        assert hasattr(VulcanOracle, "score_routes")
        # structural check -- both are valid RoutingOracle implementations
        assert isinstance(SimulatedOracle(), RoutingOracle)
        assert isinstance(VulcanOracle(), RoutingOracle)
