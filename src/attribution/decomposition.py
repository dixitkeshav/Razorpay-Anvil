"""Attribution — L3. Contribution decomposition to find the minimal
explanatory cut for a detected incident.

Given a parent slice + time window (from detection) and that slice's own
baseline success rate, greedily extends the slice filter with whichever
additional dimension+value explains the most of the parent's excess-failure
deficit, one dimension per round, until the cut explains a target fraction
of the original deficit or no further dimension helps. This handles both
single-cause episodes (one dimension dominates immediately) and
intersection causes (two dimensions are jointly required, neither alone
sufficient) — see docs/EPISODE-SPEC.md episode D.

Reads only aggregate SQL over the `events` view via src/ingest/ — never
simulation ground truth. Enforced by
tests/test_detector_ignores_ground_truth.py. May not import src/llm/,
enforced by the same lint test.
"""

import duckdb

from src.detection.hierarchical import bh_significant, one_sample_lower_pvalue
from src.ingest.lattice_levels import dim_expr

CANDIDATE_DIMS = ["x_psp", "x_issuer", "x_region", "x_merchant_id", "x_bin_prefix"]


def _where(
    slice_filter: dict, window: tuple[int, int], extra: str | None = None
) -> tuple[str, list]:
    clauses = ["(created_at // 60) BETWEEN ? AND ?"]
    params: list = [window[0], window[1]]
    for key, value in slice_filter.items():
        clauses.append(f"{dim_expr(key)} = ?")
        params.append(value)
    if extra:
        clauses.append(extra)
    return " AND ".join(clauses), params


def _deficit_for_filter(
    con: duckdb.DuckDBPyConnection, slice_filter: dict, window: tuple[int, int], baseline_sr: float
) -> tuple[float, int]:
    where_sql, params = _where(slice_filter, window)
    sql = f"""
        SELECT COUNT(*) AS attempts,
               SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) AS successes
        FROM events
        WHERE {where_sql}
    """
    attempts, successes = con.execute(sql, params).fetchone()
    successes = successes or 0
    if not attempts:
        return 0.0, 0
    deficit = max(attempts * baseline_sr - successes, 0.0)
    return deficit, attempts


def _decompose_by_dim(
    con: duckdb.DuckDBPyConnection,
    slice_filter: dict,
    dim: str,
    window: tuple[int, int],
    fallback_baseline_sr: float,
    min_hist_attempts: int = 30,
) -> list[dict]:
    """One candidate per value of `dim`, compared against *its own*
    pre/post-window history within the same slice_filter — not a single
    baseline borrowed from the parent. A merchant or region can have a
    genuinely different steady-state rate than the parent's average, and
    testing it against the parent's rate instead of its own flags that
    normal difference as a false "deficit". Falls back to
    `fallback_baseline_sr` only when a candidate has too little history of
    its own (`min_hist_attempts`) to estimate a baseline reliably.

    Also requires the degradation to be *sustained*: both halves of the
    window must individually show a success rate below the candidate's own
    baseline. A real incident degrades the whole window; a noise fluke
    concentrates in whichever half got unlucky (e.g. SR 1.00 in the first
    half, 0.59 in the second) while averaging out to something that still
    looks significant over the full window. Caught this the hard way while
    tuning against the low-volume regional episode in the committed main
    seed, where a same-window, similarly-sized but unrelated slice had a
    smaller (more "significant") p-value than the true cause purely from
    an unlucky split — see docs/JOURNAL.md.
    """
    filter_clauses = [f"{dim_expr(k)} = ?" for k in slice_filter]
    filter_clauses.append(f"{dim_expr(dim)} IS NOT NULL")
    where_sql = " AND ".join(filter_clauses)
    params = list(slice_filter.values())

    mid = (window[0] + window[1]) // 2
    in_window = f"(created_at // 60) BETWEEN {window[0]} AND {window[1]}"
    in_first_half = f"(created_at // 60) BETWEEN {window[0]} AND {mid}"
    in_second_half = f"(created_at // 60) BETWEEN {mid + 1} AND {window[1]}"
    sql = f"""
        SELECT {dim_expr(dim)} AS value,
               SUM(CASE WHEN {in_window} THEN 1 ELSE 0 END) AS window_attempts,
               SUM(CASE WHEN {in_window} AND status = 'captured' THEN 1 ELSE 0 END)
                   AS window_successes,
               SUM(CASE WHEN NOT ({in_window}) THEN 1 ELSE 0 END) AS hist_attempts,
               SUM(CASE WHEN NOT ({in_window}) AND status = 'captured' THEN 1 ELSE 0 END)
                   AS hist_successes,
               SUM(CASE WHEN {in_first_half} THEN 1 ELSE 0 END) AS h1_attempts,
               SUM(CASE WHEN {in_first_half} AND status = 'captured' THEN 1 ELSE 0 END)
                   AS h1_successes,
               SUM(CASE WHEN {in_second_half} THEN 1 ELSE 0 END) AS h2_attempts,
               SUM(CASE WHEN {in_second_half} AND status = 'captured' THEN 1 ELSE 0 END)
                   AS h2_successes
        FROM events
        WHERE {where_sql}
        GROUP BY {dim_expr(dim)}
    """
    out = []
    for (
        value,
        w_attempts,
        w_successes,
        h_attempts,
        h_successes,
        h1_attempts,
        h1_successes,
        h2_attempts,
        h2_successes,
    ) in con.execute(sql, params).fetchall():
        if not w_attempts:
            continue
        w_successes = w_successes or 0
        if h_attempts and h_attempts >= min_hist_attempts:
            own_baseline = (h_successes or 0) / h_attempts
        else:
            own_baseline = fallback_baseline_sr

        h1_sr = (h1_successes or 0) / h1_attempts if h1_attempts else None
        h2_sr = (h2_successes or 0) / h2_attempts if h2_attempts else None
        sustained = (h1_sr is None or h1_sr < own_baseline) and (
            h2_sr is None or h2_sr < own_baseline
        )
        if not sustained:
            continue

        deficit = max(w_attempts * own_baseline - w_successes, 0.0)
        out.append(
            {
                "value": value,
                "attempts": w_attempts,
                "successes": w_successes,
                "baseline": own_baseline,
                "deficit": deficit,
            }
        )
    return out


def find_minimal_cut(
    con: duckdb.DuckDBPyConnection,
    parent_slice: dict,
    window: tuple[int, int],
    baseline_sr: float,
    candidate_dims: list[str] = CANDIDATE_DIMS,
    coverage: float = 0.8,
    max_extra_dims: int = 3,
    min_retain_fraction: float = 0.5,
    alpha: float = 0.05,
) -> dict:
    """Greedily extend `parent_slice` to the minimal cut explaining
    `coverage` of a target excess-failure deficit within `window`.

    "Deficit" for a (sub)slice is its excess failures relative to what the
    parent's own baseline success rate would predict:
    attempts * baseline_sr - successes, floored at 0. Each round's
    candidates are conditioned on the filter accumulated so far, so round 2
    already measures (round-1 cut AND round-2 dimension)'s own deficit, not
    an independent contribution — narrowing the cut can only ever explain
    the same or less of the target, never more.

    The target deficit is normally the parent-level deficit. But a
    parent-level aggregate can be diluted to ~0 by an episode confined to a
    genuinely low-volume slice (see docs/EPISODE-SPEC.md's Hard tier), even
    though a real, localized problem exists underneath it. So the first
    round always runs regardless of the parent-level deficit; if it finds a
    real localized deficit where the aggregate saw none, the target adopts
    that sub-slice's own deficit as the new reference rather than reporting
    a false "nothing to explain" — see docs/JOURNAL.md. Because that
    adopted target trivially covers itself, an extra round beyond the
    normal `coverage` gate always runs once after an adoption, to check
    whether a further dimension still explains at least
    `min_retain_fraction` of it (a real refinement) rather than stopping on
    the self-referential 1.0.

    Within a round, candidates are ranked by statistical strength (smallest
    p-value from a one-sample proportion z-test against `baseline_sr` —
    src.detection.hierarchical.one_sample_lower_pvalue), not by raw
    deficit, and a candidate below significance (`alpha`) is dropped
    entirely. Ranking by raw deficit was tried first and rejected: deficit
    is volume-weighted, so a mildly-affected high-volume split can
    outscore a severely-affected low-volume one purely on attempt count —
    on the low-volume regional episode in the committed main seed, a PSP
    with 42 attempts and a real but small gap outranked the actual-cause
    PSP with 22 attempts and a much larger gap, purely because it had
    almost double the volume. p-value ranking picks the split whose own
    rate is furthest below baseline in relative terms, not whichever split
    happened to carry more traffic. See docs/JOURNAL.md.
    """
    original_deficit, original_attempts = _deficit_for_filter(
        con, parent_slice, window, baseline_sr
    )
    result = {
        "cut": dict(parent_slice),
        "coverage": 0.0,
        "original_deficit": original_deficit,
        "original_attempts": original_attempts,
        "trace": [],
    }

    current_filter = dict(parent_slice)
    remaining_dims = [d for d in candidate_dims if d not in current_filter]
    target_deficit = original_deficit if original_deficit > 0 else None

    for _ in range(max_extra_dims):
        round_candidates = []
        for dim in remaining_dims:
            for candidate in _decompose_by_dim(con, current_filter, dim, window, baseline_sr):
                if candidate["deficit"] <= 0:
                    continue
                pval = one_sample_lower_pvalue(
                    candidate["successes"], candidate["attempts"], candidate["baseline"]
                )
                round_candidates.append(
                    {
                        "dim": dim,
                        "value": candidate["value"],
                        "pvalue": pval,
                        "deficit": candidate["deficit"],
                        "attempts": candidate["attempts"],
                    }
                )

        # BH-correct across every candidate value tried this round (every
        # dim x value pair is one simultaneous test) -- picking the single
        # smallest raw p-value across dozens of candidates is exactly the
        # multiple-comparisons trap the plan's per-level BH exists to avoid
        # at the detection layer; attribution needs the same discipline.
        sig = bh_significant([c["pvalue"] for c in round_candidates], alpha=alpha)
        survivors = [c for c, s in zip(round_candidates, sig, strict=True) if s]

        best = min(survivors, key=lambda c: c["pvalue"], default=None)

        if best is None:
            break  # nothing left shows any localized deficit

        just_adopted = target_deficit is None
        if just_adopted:
            target_deficit = best["deficit"]

        fraction = best["deficit"] / target_deficit
        if not just_adopted and fraction < min_retain_fraction:
            break  # this dimension fragments the signal, doesn't explain it

        best["fraction"] = fraction
        current_filter[best["dim"]] = best["value"]
        remaining_dims.remove(best["dim"])
        result["trace"].append(best)
        result["coverage"] = fraction

        if fraction >= coverage and not just_adopted:
            break

    result["cut"] = current_filter
    result["target_deficit"] = target_deficit if target_deficit is not None else 0.0
    return result


def attribute(con: duckdb.DuckDBPyConnection, incident: dict, **kwargs) -> dict:
    """Convenience wrapper: attribute a detection incident dict (as
    returned by src.detection.detector.detect_incidents) directly."""
    return find_minimal_cut(
        con,
        parent_slice=incident["slice"],
        window=incident["window"],
        baseline_sr=incident["baseline"],
        **kwargs,
    )
