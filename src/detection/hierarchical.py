"""Significance testing for the hierarchical lattice walk: per-slice
p-values against a slice's own baseline, and Benjamini-Hochberg correction
applied within each level's test count. See docs/EPISODE-SPEC.md §2 and
anvil-build-plan.md §7 for why per-level BH (not Bonferroni across the full
lattice) is the right correction here.
"""

from scipy import stats
from statsmodels.stats.multitest import multipletests


def one_sample_lower_pvalue(successes: int, n: int, baseline_p: float) -> float:
    """One-sided test: is the observed success proportion significantly
    *lower* than the slice's own baseline_p? Small p means yes."""
    if n == 0 or not (0 < baseline_p < 1):
        return 1.0
    p_hat = successes / n
    se = (baseline_p * (1 - baseline_p) / n) ** 0.5
    if se == 0:
        return 1.0
    z = (p_hat - baseline_p) / se
    return float(stats.norm.cdf(z))


def one_sample_higher_mean_pvalue(
    window_mean: float, window_n: int, baseline_mean: float, baseline_var: float
) -> float:
    """One-sided test: is the observed mean significantly *higher* than the
    slice's own baseline mean? Small p means yes."""
    if window_n == 0 or baseline_var <= 0:
        return 1.0
    se = (baseline_var / window_n) ** 0.5
    if se == 0:
        return 1.0
    z = (window_mean - baseline_mean) / se
    return float(1 - stats.norm.cdf(z))


def bh_significant(pvalues: list[float], alpha: float = 0.05) -> list[bool]:
    """Benjamini-Hochberg step-up, applied to exactly the p-values passed in
    — the caller is responsible for scoping that list to one lattice level,
    which is what keeps the correction from destroying power the way
    Bonferroni across the whole lattice would."""
    if not pvalues:
        return []
    reject, _, _, _ = multipletests(pvalues, alpha=alpha, method="fdr_bh")
    return list(reject)
