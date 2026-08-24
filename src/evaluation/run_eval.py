"""`make eval` entrypoint. Generates the committed main seed in-memory
(deterministic, no dependency on `make seed` having been run first),
replays it, and writes docs/RESULTS.md. Every number in that file comes
from this run — see CLAUDE.md rule #1.
"""

from src.evaluation.replay import replay
from src.evaluation.scorecard import render_results_md
from src.generator.engine import SIM_START_EPOCH
from src.generator.seed import DEFAULT_SIM_MINUTES, MAIN_SEED, generate
from src.ingest.db import connect, register_events

RESULTS_PATH = "docs/RESULTS.md"


def main() -> None:
    print(f"generating main seed (seed={MAIN_SEED}, minutes={DEFAULT_SIM_MINUTES})...")
    events_df, _ = generate(
        seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES, start_epoch=SIM_START_EPOCH
    )

    con = connect()
    register_events(con, events_df)

    print("running counterfactual replay (detect -> attribute -> impact -> policy -> execute)...")
    scorecard = replay(con, seed=MAIN_SEED)

    print("writing", RESULTS_PATH)
    content = render_results_md(scorecard, seed=MAIN_SEED, sim_minutes=DEFAULT_SIM_MINUTES)
    with open(RESULTS_PATH, "w") as f:
        f.write(content)

    print(f"net incremental recovery: {scorecard['net_incremental_recovery_paise'] / 100:,.2f} INR")


if __name__ == "__main__":
    main()
