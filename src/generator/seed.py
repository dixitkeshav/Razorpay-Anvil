"""CLI entrypoint for `make seed` / `make holdout`.

Writes the frozen episode set (or, with --holdout, a fresh held-out set —
see docs/EPISODE-SPEC.md §7) to data/ as Parquet.
"""

import argparse
import pathlib

import polars as pl

from src.generator.engine import HOLDOUT_START_EPOCH, SIM_START_EPOCH, simulate
from src.generator.schema import GroundTruthEpisode, PaymentAttempt

MAIN_SEED = 42
HOLDOUT_SEED = 9001
DEFAULT_SIM_MINUTES = 4320  # 3 days


def generate(seed: int, sim_minutes: int, start_epoch: int) -> tuple[pl.DataFrame, pl.DataFrame]:
    events, ground_truth = simulate(seed=seed, sim_minutes=sim_minutes, start_epoch=start_epoch)

    # Schema-validate every row before it ships.
    for row in events:
        PaymentAttempt(**row)
    for row in ground_truth:
        GroundTruthEpisode(**row)

    events_df = pl.DataFrame(events, infer_schema_length=None)
    gt_df = pl.DataFrame(
        [{**row, "slice_filter": str(row["slice_filter"])} for row in ground_truth]
    )
    return events_df, gt_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--minutes", type=int, default=DEFAULT_SIM_MINUTES)
    args = parser.parse_args()

    data_dir = pathlib.Path("data") / ("holdout" if args.holdout else "main")
    data_dir.mkdir(parents=True, exist_ok=True)

    seed = HOLDOUT_SEED if args.holdout else MAIN_SEED
    start_epoch = HOLDOUT_START_EPOCH if args.holdout else SIM_START_EPOCH

    events_df, gt_df = generate(seed=seed, sim_minutes=args.minutes, start_epoch=start_epoch)

    events_df.write_parquet(data_dir / "events.parquet")
    gt_df.write_parquet(data_dir / "ground_truth.parquet")

    print(f"wrote {events_df.height} events to {data_dir / 'events.parquet'}")
    print(f"wrote {gt_df.height} episodes to {data_dir / 'ground_truth.parquet'}")


if __name__ == "__main__":
    main()
