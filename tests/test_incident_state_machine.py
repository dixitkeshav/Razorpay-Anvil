"""Phase 5 gate (state machine half): state transitions follow the
documented FSM. See docs/PHASES.md and src/impact/state_machine.py.
"""

import polars as pl
import pytest

from src.detection.cusum import cusum_sr
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.impact.state_machine import ALLOWED_TRANSITIONS, IncidentState, run_fsm
from src.ingest.db import connect, register_events
from src.ingest.rollup import rollup


def _all_transitions_legal(states: list[IncidentState]) -> bool:
    return all(states[i + 1] in ALLOWED_TRANSITIONS[states[i]] for i in range(len(states) - 1))


class TestFsmUnit:
    def test_flat_series_stays_normal(self):
        n = [100] * 200
        sr = [0.95] * 200
        _, baselines = cusum_sr(sr, n, warmup=20)
        alarms = [False] * 200
        states = run_fsm(sr, baselines, alarms)
        assert _all_transitions_legal(states)
        assert states[-1] == IncidentState.NORMAL
        assert IncidentState.DEGRADED not in states[30:]

    def test_sustained_severe_drop_escalates_through_watch_and_degraded(self):
        n = [100] * 60 + [100] * 40
        sr = [0.95] * 60 + [0.60] * 40  # a 35pp drop -- should reach SEVERE
        alarms, baselines = cusum_sr(sr, n, warmup=30)
        states = run_fsm(sr, baselines, alarms)

        assert _all_transitions_legal(states)
        # must pass through WATCH and DEGRADED before ever reaching SEVERE
        first_severe = next((i for i, s in enumerate(states) if s == IncidentState.SEVERE), None)
        assert first_severe is not None, "never reached SEVERE on a 35pp sustained drop"
        assert IncidentState.WATCH in states[:first_severe]
        assert IncidentState.DEGRADED in states[:first_severe]

    def test_recovery_returns_to_normal(self):
        n = [100] * 300
        sr = [0.95] * 60 + [0.60] * 40 + [0.95] * 200  # drop, then full recovery
        alarms, baselines = cusum_sr(sr, n, warmup=30)
        states = run_fsm(sr, baselines, alarms)

        assert _all_transitions_legal(states)
        assert states[-1] == IncidentState.NORMAL
        assert IncidentState.RECOVERING in states

    def test_no_direct_normal_to_degraded_or_severe(self):
        """A single-minute spike right after warmup must still pass
        through WATCH -- escalation is rate-limited by construction."""
        n = [100] * 40
        sr = [0.95] * 35 + [0.30] * 5  # abrupt, severe drop with no ramp
        alarms, baselines = cusum_sr(sr, n, warmup=20)
        states = run_fsm(sr, baselines, alarms)

        assert _all_transitions_legal(states)
        for i in range(1, len(states)):
            if states[i] in (IncidentState.DEGRADED, IncidentState.SEVERE):
                assert states[i - 1] != IncidentState.NORMAL


@pytest.fixture(scope="module")
def con():
    events_df, _ = generate(
        seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=SIM_START_EPOCH
    )
    c = connect()
    register_events(c, events_df)
    return c


def test_real_data_transitions_are_all_legal(con):
    """Run the FSM over the full committed main-seed run for every
    method's L1 series and confirm every single transition, across the
    whole 3-day run and all 5 methods, is a legal edge."""
    for method in ["upi", "card", "netbanking", "wallet", "emi"]:
        df = rollup(con, ["method"]).filter(pl.col("method") == method).sort("minute_bucket")
        sr = df["success_rate"].to_list()
        n = df["attempts"].to_list()
        alarms, baselines = cusum_sr(sr, n)
        states = run_fsm(sr, baselines, alarms)
        assert _all_transitions_legal(states), f"illegal transition found for method={method}"


def test_real_incident_reaches_degraded(con):
    """ep-A causes a real, sustained SR drop at the upi L1 aggregate --
    the state machine must escalate at least to DEGRADED during it."""
    df = rollup(con, ["method"]).filter(pl.col("method") == "upi").sort("minute_bucket")
    sr = df["success_rate"].to_list()
    n = df["attempts"].to_list()
    alarms, baselines = cusum_sr(sr, n)
    states = run_fsm(sr, baselines, alarms)

    assert IncidentState.DEGRADED in states or IncidentState.SEVERE in states
