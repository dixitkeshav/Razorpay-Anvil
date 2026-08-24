"""Hierarchical detector — L2. Walks the slice lattice top-down, only
drilling into a child once its parent fires, applying Benjamini-Hochberg
within each level. See anvil-build-plan.md §7 and docs/EPISODE-SPEC.md §2.

This module reads only the aggregated rollups from src/ingest/ — never the
raw events, and never simulation ground truth. Enforced by
tests/test_detector_ignores_ground_truth.py. It may not import src/llm/,
enforced by the same lint test.
"""

import polars as pl

from src.detection.cusum import cusum_sr
from src.detection.ewma import ewma_latency
from src.detection.hierarchical import (
    bh_significant,
    one_sample_higher_mean_pvalue,
    one_sample_lower_pvalue,
)
from src.ingest.lattice_levels import LEVELS
from src.ingest.rollup import rollup

LEVEL_ORDER = [
    "L1_method",
    "L2_method_psp",
    "L3_method_psp_issuer",
    "L4_region",
    "L4_merchant",
]

# L4_region and L4_merchant are siblings — both draw their parent set from
# L3, not from each other.
LEVEL_PARENT = {
    "L1_method": None,
    "L2_method_psp": "L1_method",
    "L3_method_psp_issuer": "L2_method_psp",
    "L4_region": "L3_method_psp_issuer",
    "L4_merchant": "L3_method_psp_issuer",
}


def _matches_parent(slice_values: dict, parent_slice: dict) -> bool:
    return all(slice_values.get(k) == v for k, v in parent_slice.items())


def _candidate_slice_frames(
    df: pl.DataFrame, dims: list[str], parents: list[dict] | None
) -> list[tuple[dict, pl.DataFrame]]:
    if not dims:
        return [({}, df)]
    slices = df.select(dims).unique().to_dicts()
    out = []
    for s in slices:
        if parents is not None and not any(_matches_parent(s, p) for p in parents):
            continue
        mask = None
        for k, v in s.items():
            col_mask = pl.col(k) == v
            mask = col_mask if mask is None else (mask & col_mask)
        out.append((s, df.filter(mask)))
    return out


def _alarm_windows(alarms: list[bool], minutes: list[int]) -> list[tuple[int, int]]:
    windows = []
    start = None
    for i, a in enumerate(alarms):
        if a and start is None:
            start = i
        elif not a and start is not None:
            windows.append((minutes[start], minutes[i - 1]))
            start = None
    if start is not None:
        windows.append((minutes[start], minutes[-1]))
    return windows


def _test_level(
    con, dims: list[str], parents: list[dict] | None, metric: str, alpha: float, **kwargs
) -> list[dict]:
    df = rollup(con, dims)
    candidates = _candidate_slice_frames(df, dims, parents)

    level_results: list[dict] = []
    for slice_key, group_df in candidates:
        group_df = group_df.sort("minute_bucket")
        minutes = group_df["minute_bucket"].to_list()
        n = group_df["attempts"].to_list()

        if metric == "sr":
            sr = group_df["success_rate"].to_list()
            alarms, baselines = cusum_sr(sr, n, **kwargs)
        else:
            latency = group_df["p95_latency_ms"].to_list()
            alarms, baselines = ewma_latency(latency, n, **kwargs)

        for t0, t1 in _alarm_windows(alarms, minutes):
            idx0, idx1 = minutes.index(t0), minutes.index(t1)
            window_n = sum(n[idx0 : idx1 + 1])
            baseline_at_start = baselines[idx0]

            if metric == "sr":
                window_successes = sum(
                    round(sr[j] * n[j]) for j in range(idx0, idx1 + 1)
                )
                pval = one_sample_lower_pvalue(window_successes, window_n, baseline_at_start)
                observed = window_successes / window_n if window_n else None
            else:
                window_values = [latency[j] for j in range(idx0, idx1 + 1) if n[j] > 0]
                observed = sum(window_values) / len(window_values) if window_values else None
                baseline_var = max(baseline_at_start * 0.25, 1.0)
                pval = one_sample_higher_mean_pvalue(
                    observed or 0.0, window_n, baseline_at_start, baseline_var
                )

            level_results.append(
                {
                    "slice": slice_key,
                    "window": (t0, t1),
                    "p_value": pval,
                    "observed": observed,
                    "baseline": baseline_at_start,
                }
            )

    pvals = [r["p_value"] for r in level_results]
    sig = bh_significant(pvals, alpha=alpha)
    return [r for r, s in zip(level_results, sig, strict=True) if s]


def detect_incidents(con, metric: str = "sr", alpha: float = 0.05, **kwargs) -> list[dict]:
    """Hierarchical BH-gated scan of the whole lattice for one metric.

    metric: "sr" (CUSUM on success rate) or "latency" (EWMA on P95
    latency). Returns every surviving incident across all levels, each
    tagged with its level, slice, alarm window, and p-value.
    """
    survivors_by_level: dict[str, list[dict]] = {}
    results: list[dict] = []

    for level_name in LEVEL_ORDER:
        parent_level = LEVEL_PARENT[level_name]
        parents = survivors_by_level[parent_level] if parent_level else None
        if parent_level and not parents:
            survivors_by_level[level_name] = []
            continue

        parent_slices = [r["slice"] for r in parents] if parents else None
        level_results = _test_level(
            con, LEVELS[level_name], parent_slices, metric=metric, alpha=alpha, **kwargs
        )
        for r in level_results:
            r["level"] = level_name
        survivors_by_level[level_name] = level_results
        results.extend(level_results)

    return results
