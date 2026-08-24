"""1-minute-bucket x slice-lattice rollups — L1. attempts, successes, SR,
P50/P95/P99 latency, timeout_rate, retry_rate.
"""

import duckdb
import polars as pl

from src.ingest.lattice_levels import ALLOWED_DIMS, dim_expr

_METRICS_SQL = """
    COUNT(*) AS attempts,
    SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) AS successes,
    SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END)::DOUBLE / COUNT(*) AS success_rate,
    QUANTILE_CONT(x_latency_ms, 0.5) AS p50_latency_ms,
    QUANTILE_CONT(x_latency_ms, 0.95) AS p95_latency_ms,
    QUANTILE_CONT(x_latency_ms, 0.99) AS p99_latency_ms,
    SUM(CASE WHEN error_reason LIKE '%timeout%' THEN 1 ELSE 0 END)::DOUBLE / COUNT(*)
        AS timeout_rate,
    SUM(CASE WHEN x_attempt_number > 1 THEN 1 ELSE 0 END)::DOUBLE / COUNT(*) AS retry_rate
"""

EMPTY_STATS = {
    "attempts": 0,
    "successes": 0,
    "success_rate": None,
    "p50_latency_ms": None,
    "p95_latency_ms": None,
    "p99_latency_ms": None,
    "timeout_rate": None,
    "retry_rate": None,
}


def _validate_dims(dims: list[str]) -> None:
    unknown = set(dims) - ALLOWED_DIMS
    if unknown:
        raise ValueError(f"unknown slice dimension(s): {unknown}")


def rollup(con: duckdb.DuckDBPyConnection, dims: list[str]) -> pl.DataFrame:
    """Rollup at one lattice level: 1-minute buckets x the given dims."""
    _validate_dims(dims)
    group_exprs = ", ".join(["(created_at // 60)", *(dim_expr(d) for d in dims)])
    select_dims = (", ".join(f"{dim_expr(d)} AS {d}" for d in dims) + ",") if dims else ""
    sql = f"""
        SELECT
            (created_at // 60) AS minute_bucket,
            {select_dims}
            {_METRICS_SQL}
        FROM events
        GROUP BY {group_exprs}
        ORDER BY {group_exprs}
    """
    return con.execute(sql).pl()


def slice_stats(
    con: duckdb.DuckDBPyConnection, minute_bucket: int, slice_filter: dict[str, str]
) -> dict:
    """Stats for one exact slice at one exact minute bucket."""
    _validate_dims(list(slice_filter.keys()))
    where_clauses = ["(created_at // 60) = ?"]
    params: list = [minute_bucket]
    for key, value in slice_filter.items():
        where_clauses.append(f"{dim_expr(key)} = ?")
        params.append(value)
    where_sql = " AND ".join(where_clauses)
    sql = f"SELECT {_METRICS_SQL} FROM events WHERE {where_sql}"

    result = con.execute(sql, params).pl()
    if result.height == 0 or result["attempts"][0] == 0:
        return dict(EMPTY_STATS)
    return result.row(0, named=True)
