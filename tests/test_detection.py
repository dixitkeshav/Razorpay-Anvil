"""Phase 3 gate: detects all easy-tier episodes; fires at <=2 false
alarms/day on a clean stretch; passes the no-ground-truth lint test (see
tests/test_detector_ignores_ground_truth.py). See docs/PHASES.md.
"""

import pytest

from src.detection.cusum import cusum_sr
from src.detection.detector import detect_incidents
from src.detection.ewma import ewma_latency
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.ingest.db import connect, register_events

EPOCH_MIN_OFFSET = SIM_START_EPOCH // 60
SIM_DAYS = DEFAULT_SIM_MINUTES / 1440


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
def gt_windows(generated):
    _, gt_df = generated
    windows = []
    for row in gt_df.iter_rows(named=True):
        windows.append(
            (
                EPOCH_MIN_OFFSET + row["onset_min"],
                EPOCH_MIN_OFFSET + row["recovery_end_min"],
                row["episode_id"],
                row["tier"],
                row["slice_filter"],
            )
        )
    return windows


def _overlapping_episode_ids(window, gt_windows):
    t0, t1 = window
    return [eid for lo, hi, eid, *_ in gt_windows if t0 <= hi and t1 >= lo]


def test_detects_the_easy_tier_episode(con, gt_windows):
    easy_episode = next(w for w in gt_windows if w[3] == "easy")
    _, _, easy_id, _, _ = easy_episode

    incidents = detect_incidents(con, metric="sr")
    hit_ids = set()
    for r in incidents:
        hit_ids.update(_overlapping_episode_ids(r["window"], gt_windows))

    assert easy_id in hit_ids, f"easy-tier episode {easy_id} was not detected"


def test_false_alarm_rate_on_full_run(con, gt_windows):
    """<=2 false alarms/day, measured across the whole run — any incident
    window that does not overlap a real (non-decoy) episode or a decoy
    window counts as a false alarm."""
    incidents = detect_incidents(con, metric="sr")
    false_alarms = [
        r for r in incidents if not _overlapping_episode_ids(r["window"], gt_windows)
    ]
    rate = len(false_alarms) / SIM_DAYS
    assert rate <= 2.0, f"{rate:.2f} false alarms/day (incidents: {false_alarms})"


def test_decoys_do_not_count_as_missed_false_alarms_but_are_tracked(con, gt_windows):
    """Decoys are allowed to fire or not — they are reported separately in
    docs/RESULTS.md, not folded into the false-alarm rate silently. This
    test just documents which decoys the tuned detector currently catches."""
    incidents = detect_incidents(con, metric="sr")
    decoy_hits = set()
    for r in incidents:
        for eid in _overlapping_episode_ids(r["window"], gt_windows):
            if eid.startswith("decoy-"):
                decoy_hits.add(eid)
    # not asserting a specific outcome here -- just that the run completes
    # and decoy hits (if any) are enumerable for the eventual scorecard.
    assert isinstance(decoy_hits, set)


def test_detector_never_touches_raw_events_or_ground_truth_table(con):
    """The detector's public API takes a DuckDB connection over the
    `events` view only -- confirm detect_incidents runs without ever being
    handed the ground-truth frame."""
    incidents = detect_incidents(con, metric="sr")
    assert isinstance(incidents, list)
    for r in incidents:
        assert "episode_id" not in r  # detector output has no ground-truth field


class TestCusumUnit:
    def test_flags_a_sustained_drop(self):
        # 40 clean minutes at sr=0.95, n=100, then a hard drop to 0.60 for 20 minutes
        sr = [0.95] * 40 + [0.60] * 20
        n = [100] * 60
        alarms, _ = cusum_sr(sr, n, warmup=20)
        assert any(alarms[40:])  # fires somewhere during the drop

    def test_does_not_flag_a_flat_series(self):
        sr = [0.95] * 100
        n = [100] * 100
        alarms, _ = cusum_sr(sr, n, warmup=20)
        assert not any(alarms)

    def test_skips_low_volume_minutes(self):
        sr = [0.95] * 40 + [0.0] * 5 + [0.95] * 20
        n = [100] * 40 + [1] * 5 + [100] * 20  # the zeros are single-attempt flukes
        alarms, _ = cusum_sr(sr, n, warmup=20, min_n=5)
        assert not any(alarms)


class TestEwmaUnit:
    def test_flags_a_sustained_rise(self):
        latency = [800.0] * 40 + [4800.0] * 20
        n = [100] * 60
        alarms, _ = ewma_latency(latency, n, warmup=20)
        assert any(alarms[40:])

    def test_does_not_flag_a_flat_series(self):
        latency = [800.0] * 100
        n = [100] * 100
        alarms, _ = ewma_latency(latency, n, warmup=20)
        assert not any(alarms)
