"""Stratified recall and decoy false-alarm evaluation — Phase 13.

Uses simulation ground truth to score the detector. That is legitimate
here: this is evaluation code, not src/detection/, src/attribution/, or
src/policy/, none of which ever read x_episode_id — see CLAUDE.md rule #3
and tests/test_detector_ignores_ground_truth.py, which enforces it on the
pipeline modules, not on evaluation.

Headline metrics come from the held-out set only, per
docs/EPISODE-SPEC.md §7 — this module is meant to be called with the
held-out ground truth, not the main seed's.
"""

import ast

import duckdb
import polars as pl

from src.detection.detector import detect_incidents

# Dimensions the lattice actually tests (src.ingest.lattice_levels /
# src.attribution CANDIDATE_DIMS) that a decoy's own slice_filter can use.
# decoy-volume-spike's dimension (x_merchant_category) isn't one of them —
# no lattice level groups by category, so a match/no-match verdict for it
# would be meaningless rather than just conservative. Reported as
# not-applicable instead of a misleading count.
TESTABLE_DECOY_DIMS = {"method", "x_psp", "x_issuer", "x_region", "x_merchant_id", "x_bin_prefix"}


def _normalize_slice(raw: dict) -> dict:
    return {("x_bin_prefix" if k == "bin_prefix" else k): v for k, v in raw.items()}


def _slice_consistent(detected_slice: dict, true_slice: dict) -> bool:
    """True if every dimension `detected_slice` names agrees with
    `true_slice` — a correct, possibly partial, match. A dimension absent
    from `true_slice` is not a conflict (over-broad, not wrong)."""
    return all(true_slice.get(k) == v for k, v in detected_slice.items() if k in true_slice)


def evaluate_recall(
    con: duckdb.DuckDBPyConnection, gt_df: pl.DataFrame, epoch_min_offset: int
) -> dict:
    incidents = detect_incidents(con, metric="sr")

    per_episode = []
    for row in gt_df.iter_rows(named=True):
        raw_filter = row["slice_filter"]
        true_slice = _normalize_slice(
            ast.literal_eval(raw_filter) if isinstance(raw_filter, str) else raw_filter
        )
        window = (epoch_min_offset + row["onset_min"], epoch_min_offset + row["recovery_end_min"])

        testable = bool(set(true_slice.keys()) & TESTABLE_DECOY_DIMS) or not row["decoy"]
        detected = False
        if testable:
            for inc in incidents:
                overlaps = inc["window"][0] <= window[1] and inc["window"][1] >= window[0]
                if overlaps and _slice_consistent(inc["slice"], true_slice):
                    detected = True
                    break

        per_episode.append(
            {
                "episode_id": row["episode_id"],
                "tier": row["tier"],
                "decoy": row["decoy"],
                "testable": testable,
                "detected": detected,
            }
        )

    real_episodes = [e for e in per_episode if not e["decoy"] and e["tier"] != "l10"]
    decoys = [e for e in per_episode if e["decoy"]]

    recall_by_tier: dict[str, dict] = {}
    for tier in sorted({e["tier"] for e in real_episodes}):
        tier_eps = [e for e in real_episodes if e["tier"] == tier]
        recall_by_tier[tier] = {
            "total": len(tier_eps),
            "detected": sum(e["detected"] for e in tier_eps),
        }

    testable_decoys = [e for e in decoys if e["testable"]]

    return {
        "per_episode": per_episode,
        "recall_by_tier": recall_by_tier,
        "decoys_total": len(decoys),
        "decoys_testable": len(testable_decoys),
        "decoys_falsely_flagged": sum(e["detected"] for e in testable_decoys),
    }
