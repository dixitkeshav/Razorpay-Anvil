"""Decision-quality monitor — L10. Compares the routing oracle's implied
confidence (`x_route_confidence`) against realised outcomes, per slice,
over time.

This is a different signal from L2 detection. A CUSUM changepoint
detector compares a slice against *its own history* — if a slice's true
success rate has always been low, relative to what the oracle believes,
there is no changepoint to find, because nothing changed. The only way to
see that failure mode is to compare the oracle's own belief against
reality directly, which is what this module does. See
anvil-build-plan.md §6 and docs/EPISODE-SPEC.md episode F.

Reads `x_route_confidence` from the `events` view — an ops-extension
field documenting what the oracle believed, not simulation ground truth
(unlike `x_episode_id`, which this module never reads).
"""

import duckdb
import polars as pl

from src.ingest.lattice_levels import dim_expr


def _rollup_with_confidence(con: duckdb.DuckDBPyConnection, dims: list[str]) -> pl.DataFrame:
    select_dims = (", ".join(f"{dim_expr(d)} AS {d}" for d in dims) + ",") if dims else ""
    group_exprs = ", ".join(["(created_at // 60)", *(dim_expr(d) for d in dims)])
    sql = f"""
        SELECT
            (created_at // 60) AS minute_bucket,
            {select_dims}
            COUNT(*) AS attempts,
            SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END)::DOUBLE / COUNT(*)
                AS success_rate,
            AVG(x_route_confidence) AS mean_confidence
        FROM events
        GROUP BY {group_exprs}
        ORDER BY {group_exprs}
    """
    return con.execute(sql).pl()


def detect_calibration_drift(
    con: duckdb.DuckDBPyConnection,
    dims: list[str],
    gap_threshold: float = 0.15,
    min_sustained_minutes: int = 14,
    min_attempts_per_minute: int = 5,
    smoothing_window: int = 10,
) -> list[dict]:
    """Flags every (slice, contiguous window) where a rolling-mean-smoothed
    gap between the oracle's mean confidence and the realised success rate
    stays at or above `gap_threshold` for at least `min_sustained_minutes`
    consecutive qualifying minutes. `min_sustained_minutes=14` matches the
    threshold named in anvil-build-plan.md §6 — episode F is built to run
    for 180 minutes, well above it (see docs/JOURNAL.md Phase 1).

    The gap is smoothed, not thresholded raw, because confidence tracks
    the true underlying rate closely while a raw per-minute success rate
    is a noisy small-sample estimate of that same rate — so the raw gap
    inherits nearly all of the success rate's own sampling noise. A first
    version thresholding the raw per-minute gap produced 619 spurious
    "incidents" on the committed main seed, the same false-alarm-storm
    failure mode as the original CUSUM tuning in Phase 3, for the same
    underlying reason (small n, high per-minute variance).

    Smoothing is a bounded rolling mean over the last `smoothing_window`
    qualifying minutes, not an EWMA. An EWMA was tried first and rejected:
    its unbounded memory kept a "run" alive for hundreds of minutes after
    the raw gap had already returned to baseline, because a value that
    climbed high early on decayed too slowly to ever cross back below
    threshold within the observed window — producing runs whose *reported*
    aggregate gap (computed from the genuinely elevated raw minutes only)
    came out far below the threshold that supposedly triggered them, which
    is incoherent as a report. A bounded window has no such memory: once
    the last `smoothing_window` qualifying minutes are back near baseline,
    the rolling mean is too, immediately. See docs/JOURNAL.md.

    Minutes with fewer than `min_attempts_per_minute` attempts are
    skipped as evidence entirely (not counted as breaking a run, not
    counted as extending one, and excluded from the reported window's own
    aggregates) — same low-volume-noise rationale as
    src.detection.cusum's `min_n`.
    """
    df = _rollup_with_confidence(con, dims)
    results: list[dict] = []

    if not dims:
        groups = [({}, df)]
    else:
        groups = [
            (dict(zip(dims, key if isinstance(key, tuple) else (key,), strict=True)), group)
            for key, group in df.group_by(dims)
        ]

    for slice_key, group in groups:
        group = group.sort("minute_bucket")
        minutes = group["minute_bucket"].to_list()
        sr = group["success_rate"].to_list()
        conf = group["mean_confidence"].to_list()
        n = group["attempts"].to_list()

        qualifying = [i for i in range(len(minutes)) if n[i] >= min_attempts_per_minute]
        if not qualifying:
            continue

        recent_gaps: list[float] = []
        run_indices: list[int] = []

        for i in qualifying:
            gap = conf[i] - sr[i]
            recent_gaps.append(gap)
            if len(recent_gaps) > smoothing_window:
                recent_gaps.pop(0)
            smoothed_gap = sum(recent_gaps) / len(recent_gaps)

            if smoothed_gap >= gap_threshold:
                run_indices.append(i)
            else:
                _maybe_report_run(
                    results, run_indices, slice_key, minutes, n, sr, conf, min_sustained_minutes
                )
                run_indices = []

        _maybe_report_run(
            results, run_indices, slice_key, minutes, n, sr, conf, min_sustained_minutes
        )

    return results


def _maybe_report_run(
    results: list[dict],
    indices: list[int],
    slice_key: dict,
    minutes: list[int],
    n: list[int],
    sr: list[float],
    conf: list[float],
    min_sustained_minutes: int,
) -> None:
    if not indices:
        return
    run_minutes = [minutes[i] for i in indices]
    run_n = [n[i] for i in indices]
    run_sr = [sr[i] for i in indices]
    run_conf = [conf[i] for i in indices]
    duration = run_minutes[-1] - run_minutes[0] + 1
    total_attempts = sum(run_n)
    if duration < min_sustained_minutes:
        return
    weighted_sr = sum(s * a for s, a in zip(run_sr, run_n, strict=True)) / total_attempts
    weighted_conf = sum(c * a for c, a in zip(run_conf, run_n, strict=True)) / total_attempts
    results.append(
        {
            "slice": dict(slice_key),
            "window": (run_minutes[0], run_minutes[-1]),
            "duration_minutes": duration,
            "attempts": total_attempts,
            "realised_success_rate": weighted_sr,
            "mean_oracle_confidence": weighted_conf,
            "calibration_gap": weighted_conf - weighted_sr,
        }
    )
