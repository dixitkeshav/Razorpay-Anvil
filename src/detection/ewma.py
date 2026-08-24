"""One-sided EWMA control chart for a *rise* in P95 latency.

Same adaptive-baseline-freeze pattern as the CUSUM detector — see
src/detection/cusum.py.
"""


def ewma_latency(
    latency: list[float],
    n: list[int],
    lam: float = 0.2,
    threshold_sigma: float = 8.0,
    warmup: int = 30,
    baseline_lambda: float = 0.02,
    min_n: int = 5,
) -> tuple[list[bool], list[float]]:
    """Flag a sustained rise in a per-minute latency statistic (e.g. P95).

    threshold_sigma=8 (rather than the textbook 3) was chosen the same way
    as cusum_sr's h — grid search against the committed main seed for
    ~1 false alarm/day while still catching the latency episode. See
    docs/JOURNAL.md.

    `latency`/`n` are per-minute latency and attempt count, in time order.
    Minutes with fewer than `min_n` attempts are skipped — same rationale
    as cusum_sr's min_n.

    Exiting an alarm requires the EWMA to drop back under a lower hysteresis
    band (1 sigma above baseline) rather than merely dipping under the
    entry threshold — the same chattering fix as cusum_sr's in-alarm
    latch, for the same reason.

    Returns (alarms, baselines) — same contract as cusum_sr.
    """
    alarms: list[bool] = [False] * len(latency)
    baselines: list[float] = [float("nan")] * len(latency)

    baseline_mean: float | None = None
    baseline_var = 1.0
    ewma: float | None = None
    n_obs = 0
    in_alarm = False

    for i, (val, count) in enumerate(zip(latency, n, strict=True)):
        if count < min_n:
            continue
        if baseline_mean is None:
            baseline_mean = val
            baseline_var = max(val * 0.25, 1.0)
            ewma = val
            baselines[i] = baseline_mean
            continue

        baselines[i] = baseline_mean
        ewma = lam * val + (1 - lam) * ewma
        n_obs += 1
        if n_obs <= warmup:
            baseline_mean = (1 - baseline_lambda) * baseline_mean + baseline_lambda * val
            baseline_var = (1 - baseline_lambda) * baseline_var + baseline_lambda * (
                val - baseline_mean
            ) ** 2
            continue

        sigma_ewma = (baseline_var**0.5) * (lam / (2 - lam)) ** 0.5
        upper = baseline_mean + threshold_sigma * sigma_ewma
        lower = baseline_mean + 1.0 * sigma_ewma

        if ewma > upper:
            in_alarm = True
        elif ewma <= lower:
            in_alarm = False
        alarms[i] = in_alarm

        if not in_alarm:
            baseline_mean = (1 - baseline_lambda) * baseline_mean + baseline_lambda * val
            baseline_var = (1 - baseline_lambda) * baseline_var + baseline_lambda * (
                val - baseline_mean
            ) ** 2

    return alarms, baselines
