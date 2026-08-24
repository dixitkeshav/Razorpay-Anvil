"""Hand-rolled one-sided CUSUM for a *decrease* in success rate.

Standardized-residual CUSUM against an adaptive baseline that freezes while
an alarm is active, so a live incident cannot drag its own baseline down.
Per CLAUDE.md: this stays hand-rolled, no changepoint library.

Never reads simulation ground truth — see
tests/test_detector_ignores_ground_truth.py.
"""


def cusum_sr(
    sr: list[float],
    n: list[int],
    k: float = 0.5,
    h: float = 15.0,
    warmup: int = 30,
    baseline_lambda: float = 0.02,
    min_n: int = 5,
) -> tuple[list[bool], list[float]]:
    """Flag a sustained drop in success rate for one slice's time series.

    h=15 (rather than the textbook k=0.5/h=5 combination) was chosen by
    grid search against the committed main seed: h=5 gives an average run
    length short enough to produce >100 false alarms/day when monitoring
    several slices continuously across a multi-day run; h=15 detects the
    easy-tier episode with zero false alarms on the same data. See
    docs/JOURNAL.md.

    `sr`/`n` are per-minute success rate and attempt count, in time order.
    Minutes with fewer than `min_n` attempts are skipped as evidence: a
    per-minute proportion computed from 1-2 attempts is not well
    approximated by a normal z-statistic, and treating it as such is what
    caused a false-alarm storm on the lowest-volume method (emi, 2% of
    traffic) during tuning — see docs/JOURNAL.md.

    Returns (alarms, baselines): a bool per input minute (True while the
    CUSUM statistic is in alarm state) and the baseline mean that was in
    effect *before* each minute was scored, so callers can quantify how far
    a flagged window fell from the slice's own history.

    Exiting an alarm requires S to fully recover to 0, not merely to climb
    back above -h. Without that hysteresis, S chatters back and forth
    across -h during a genuine incident and one incident fragments into
    dozens of 1-minute windows — see docs/JOURNAL.md.

    The per-minute variance is estimated empirically (an EWMA of squared
    residuals), not from the textbook Binomial(n, p) formula. A slice like
    "method" pools several different psp/issuer sub-populations, each with
    its own true rate, so its minute-to-minute rate is a mixture with real
    variance above what p(1-p)/n predicts — using the textbook formula
    understated that variance, inflated z, and produced a false-alarm storm
    during tuning. See docs/JOURNAL.md.
    """
    alarms: list[bool] = [False] * len(sr)
    baselines: list[float] = [float("nan")] * len(sr)

    baseline_mean: float | None = None
    baseline_var = 1e-4
    s = 0.0
    n_obs = 0
    in_alarm = False

    for i, (rate, count) in enumerate(zip(sr, n, strict=True)):
        if count < min_n:
            continue
        if baseline_mean is None:
            baseline_mean = rate
            baseline_var = 1e-3
            baselines[i] = baseline_mean
            continue

        baselines[i] = baseline_mean
        n_obs += 1
        if n_obs <= warmup:
            resid = rate - baseline_mean
            baseline_mean = (1 - baseline_lambda) * baseline_mean + baseline_lambda * rate
            baseline_var = (1 - baseline_lambda) * baseline_var + baseline_lambda * resid**2
            continue

        sigma = max(baseline_var, 1e-6) ** 0.5
        z = (rate - baseline_mean) / sigma
        s = min(0.0, s + z + k)

        if s < -h:
            in_alarm = True
        elif s >= 0.0:
            in_alarm = False
        alarms[i] = in_alarm

        if not in_alarm:
            resid = rate - baseline_mean
            baseline_mean = (1 - baseline_lambda) * baseline_mean + baseline_lambda * rate
            baseline_var = (1 - baseline_lambda) * baseline_var + baseline_lambda * resid**2

    return alarms, baselines
