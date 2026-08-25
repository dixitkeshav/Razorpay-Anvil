"""Phase 13 gate: `make sweep` emits docs/SENSITIVITY.md — the outcome-
model sensitivity grid, generated, not hand-computed. See docs/PHASES.md.
"""

import pathlib

import pytest

from src.evaluation.run_sweep import COST_GRID_PAISE, REROUTE_GRID, RETRY_GRID, run_sweep
from src.generator.engine import HOLDOUT_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, HOLDOUT_SEED, generate
from src.ingest.db import connect, register_events
from src.policy import config as policy_config


@pytest.fixture(scope="module")
def con():
    events_df, _ = generate(
        seed=HOLDOUT_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=HOLDOUT_START_EPOCH
    )
    c = connect()
    register_events(c, events_df)
    return c


@pytest.fixture(scope="module")
def results(con):
    return run_sweep(con, seed=HOLDOUT_SEED)


def test_sweep_covers_all_48_cells(results):
    assert len(results) == len(RETRY_GRID) * len(REROUTE_GRID) * len(COST_GRID_PAISE) == 48

    seen = {
        (r["p_retry_success"], r["p_reroute_success"], r["cost_reroute_paise"]) for r in results
    }
    assert len(seen) == 48  # every cell is distinct, none skipped or duplicated


def test_sweep_restores_global_policy_config(con):
    """run_sweep monkeypatches src.policy.config for each cell -- verify
    it always restores the original values afterward, even though this
    module runs inside the same pytest process as every other test."""
    before = (
        policy_config.P_RETRY_SUCCESS,
        policy_config.P_REROUTE_SUCCESS,
        policy_config.COST_REROUTE_PAISE,
    )
    run_sweep(con, seed=HOLDOUT_SEED)
    after = (
        policy_config.P_RETRY_SUCCESS,
        policy_config.P_REROUTE_SUCCESS,
        policy_config.COST_REROUTE_PAISE,
    )
    assert before == after


def test_higher_reroute_success_probability_does_not_reduce_recovery_at_fixed_cost(results):
    """Not a strict monotonicity guarantee (EV ranking can shift which
    population gets which action), but a real, generated sanity check:
    holding cost and retry probability fixed, the extremes of the reroute
    grid shouldn't have recovery in reverse order."""
    low = next(
        r
        for r in results
        if r["p_retry_success"] == RETRY_GRID[0]
        and r["p_reroute_success"] == REROUTE_GRID[0]
        and r["cost_reroute_paise"] == COST_GRID_PAISE[0]
    )
    high = next(
        r
        for r in results
        if r["p_retry_success"] == RETRY_GRID[0]
        and r["p_reroute_success"] == REROUTE_GRID[-1]
        and r["cost_reroute_paise"] == COST_GRID_PAISE[0]
    )
    assert high["net_incremental_recovery_paise"] >= low["net_incremental_recovery_paise"]


def test_make_sweep_writes_docs_sensitivity_md():
    from src.evaluation.run_sweep import main

    main()

    path = pathlib.Path("docs/SENSITIVITY.md")
    assert path.exists()
    content = path.read_text()
    assert "GENERATED" in content
    assert "48" in content
    assert "Where Anvil loses money" in content
