"""`make eval` entrypoint. Generates the held-out set in-memory
(deterministic, no dependency on `make holdout` having been run first —
same seed, same output, always), replays it, scores stratified recall and
decoy false alarms against it, and writes docs/RESULTS.md.

Headline metrics come from the held-out set only — fresh seed, redrawn
parameters, never used to tune the detector or attribution — per
docs/EPISODE-SPEC.md §7. Every number in docs/RESULTS.md comes from this
run; see CLAUDE.md rule #1.
"""

from src.evaluation.recall import evaluate_recall
from src.evaluation.replay import replay
from src.evaluation.scorecard import render_results_md
from src.generator.engine import HOLDOUT_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, HOLDOUT_SEED, generate
from src.ingest.db import connect, register_events

RESULTS_PATH = "docs/RESULTS.md"


def main() -> None:
    print(f"generating held-out set (seed={HOLDOUT_SEED}, minutes={DEFAULT_SIM_MINUTES})...")
    events_df, gt_df = generate(
        seed=HOLDOUT_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=HOLDOUT_START_EPOCH
    )

    con = connect()
    register_events(con, events_df)

    print("running counterfactual replay (detect -> attribute -> impact -> policy -> execute)...")
    scorecard = replay(con, seed=HOLDOUT_SEED)

    print("scoring stratified recall and decoy false alarms against held-out ground truth...")
    recall = evaluate_recall(con, gt_df, HOLDOUT_START_EPOCH // 60)

    print("writing", RESULTS_PATH)
    content = render_results_md(
        scorecard, recall, seed=HOLDOUT_SEED, sim_minutes=DEFAULT_SIM_MINUTES
    )
    with open(RESULTS_PATH, "w") as f:
        f.write(content)

    print(f"net incremental recovery: {scorecard['net_incremental_recovery_paise'] / 100:,.2f} INR")


if __name__ == "__main__":
    main()
