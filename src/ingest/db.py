"""DuckDB-over-Parquet event store. Single file, zero infra — see
anvil-build-plan.md §10 for why this instead of Postgres/Kafka.
"""

import duckdb
import polars as pl


def connect(parquet_paths: list[str] | None = None) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    if parquet_paths:
        quoted = ", ".join(f"'{p}'" for p in parquet_paths)
        con.execute(f"CREATE OR REPLACE VIEW events AS SELECT * FROM read_parquet([{quoted}])")
    return con


def register_events(con: duckdb.DuckDBPyConnection, events_df: pl.DataFrame) -> None:
    """Point the `events` view at an in-memory frame — used by tests and by
    anything replaying a held-out set that hasn't been written to disk."""
    con.register("events_df", events_df)
    con.execute("CREATE OR REPLACE VIEW events AS SELECT * FROM events_df")
