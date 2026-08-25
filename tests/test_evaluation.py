"""Phase 8 gate: `make eval` emits docs/RESULTS.md with a real Rs. figure,
agent-on vs agent-off, from the same seed. See docs/PHASES.md.
"""

import pathlib

import pytest

from src.evaluation.recall import evaluate_recall
from src.evaluation.replay import replay
from src.evaluation.scorecard import render_results_md
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.ingest.db import connect, register_events


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
def scorecard(con):
    return replay(con, seed=MAIN_SEED)


@pytest.fixture(scope="module")
def recall(con, generated):
    _, gt_df = generated
    return evaluate_recall(con, gt_df, SIM_START_EPOCH // 60)


def test_replay_finds_at_least_one_incident(scorecard):
    assert scorecard["incidents_detected"] >= 1


def test_replay_replays_a_nonzero_number_of_failed_attempts(scorecard):
    assert scorecard["attempts_replayed"] > 0


def test_agent_off_never_recovers_by_construction(scorecard):
    """The do-nothing baseline (docs/OUTCOME-MODEL.md §5) always recovers
    Rs. 0 -- the generator has no independent retry mechanism, so a failed
    attempt with no Anvil action simply stays failed."""
    assert scorecard["gmv_recovered_agent_off_paise"] == 0


def test_net_incremental_recovery_is_a_real_positive_rupee_figure(scorecard):
    assert scorecard["gmv_recovered_agent_on_paise"] > 0
    assert scorecard["net_incremental_recovery_paise"] == (
        scorecard["gmv_recovered_agent_on_paise"]
        - scorecard["gmv_recovered_agent_off_paise"]
        - scorecard["execution_cost_paise"]
    )
    assert scorecard["net_incremental_recovery_paise"] > 0


def test_every_replayed_attempt_produced_a_ledger_entry(scorecard):
    assert scorecard["ledger_entry_count"] == scorecard["attempts_replayed"]


def test_decision_counts_sum_to_attempts_replayed(scorecard):
    assert sum(scorecard["decisions_by_action"].values()) == scorecard["attempts_replayed"]


def test_replay_is_deterministic_given_the_same_seed(con):
    """make reproduce promises deterministic output -- verify replaying
    the same seed twice gives byte-for-byte identical money figures."""
    first = replay(con, seed=MAIN_SEED)
    second = replay(con, seed=MAIN_SEED)
    assert first["net_incremental_recovery_paise"] == second["net_incremental_recovery_paise"]
    assert first["recovered_count"] == second["recovered_count"]
    assert first["decisions_by_action"] == second["decisions_by_action"]


def test_scorecard_markdown_contains_the_actual_computed_numbers(scorecard, recall):
    content = render_results_md(
        scorecard, recall, seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES
    )
    assert str(scorecard["attempts_replayed"]) in content
    assert str(scorecard["recovered_count"]) in content
    net_rupees = f"{scorecard['net_incremental_recovery_paise'] / 100:,.2f}"
    assert net_rupees in content
    assert "Rs. 0.00" in content  # agent-off, always
    assert "Stratified recall" in content
    assert "Failure taxonomy" in content


def test_make_eval_writes_docs_results_md():
    from src.evaluation.run_eval import main

    main()

    path = pathlib.Path("docs/RESULTS.md")
    assert path.exists()
    content = path.read_text()
    assert "GENERATED" in content
    assert "Net incremental recovery" in content
