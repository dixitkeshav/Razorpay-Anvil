"""Impact estimator — L4. Affected attempts, at-risk GMV, per-merchant
breakdown for an attributed incident (a slice cut + a time window).

Reads only aggregate SQL over the `events` view via src/ingest/.
"""

import duckdb

from src.ingest.lattice_levels import dim_expr


def _where(cut: dict, window: tuple[int, int]) -> tuple[str, list]:
    clauses = ["(created_at // 60) BETWEEN ? AND ?"]
    params: list = [window[0], window[1]]
    for key, value in cut.items():
        clauses.append(f"{dim_expr(key)} = ?")
        params.append(value)
    return " AND ".join(clauses), params


def estimate_impact(con: duckdb.DuckDBPyConnection, cut: dict, window: tuple[int, int]) -> dict:
    """Affected-attempt count and at-risk GMV for the given cut+window,
    plus a per-merchant breakdown of the same population.

    "Affected" here means every attempt inside the identified slice+window
    — the same population attribution's minimal cut names as the incident.
    Accuracy of this estimate is therefore inherited directly from
    attribution: if the cut is right, the count is right.
    """
    where_sql, params = _where(cut, window)
    sql = f"""
        SELECT COUNT(*) AS attempts,
               SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) AS successes,
               SUM(amount) AS at_risk_gmv
        FROM events
        WHERE {where_sql}
    """
    attempts, successes, gmv = con.execute(sql, params).fetchone()

    merchant_sql = f"""
        SELECT x_merchant_id,
               COUNT(*) AS attempts,
               SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) AS successes,
               SUM(amount) AS at_risk_gmv
        FROM events
        WHERE {where_sql}
        GROUP BY x_merchant_id
        ORDER BY at_risk_gmv DESC
    """
    per_merchant = [
        {
            "merchant_id": row[0],
            "attempts": row[1],
            "successes": row[2] or 0,
            "at_risk_gmv": row[3] or 0,
        }
        for row in con.execute(merchant_sql, params).fetchall()
    ]

    return {
        "cut": dict(cut),
        "window": window,
        "affected_attempts": attempts or 0,
        "affected_successes": successes or 0,
        "at_risk_gmv": gmv or 0,
        "per_merchant": per_merchant,
    }
