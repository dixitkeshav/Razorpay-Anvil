"""Incident state machine — L4.

Documented FSM (this is the table the Phase 5 gate checks transitions
against):

    NORMAL     -> WATCH
    WATCH      -> DEGRADED, NORMAL
    DEGRADED   -> SEVERE, RECOVERING
    SEVERE     -> RECOVERING
    RECOVERING -> NORMAL, DEGRADED, SEVERE   (relapse)

Every state also has a self-loop (staying put is always legal). No other
edge is permitted. In particular NORMAL cannot jump straight to DEGRADED
or SEVERE, and WATCH cannot jump straight to SEVERE — escalation moves at
most one step per minute along [NORMAL, WATCH, DEGRADED, SEVERE], even if
the underlying severity would justify skipping stages. This is enforced by
construction (see `_step`), not just asserted after the fact: the state
machine is rate-limited on escalation the same way a real ops runbook
would be, so a single noisy minute can't cause a state to leap from
NORMAL straight to SEVERE.
"""

from enum import StrEnum


class IncidentState(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    SEVERE = "SEVERE"
    RECOVERING = "RECOVERING"


ESCALATION_ORDER = [
    IncidentState.NORMAL,
    IncidentState.WATCH,
    IncidentState.DEGRADED,
    IncidentState.SEVERE,
]

ALLOWED_TRANSITIONS: dict[IncidentState, set[IncidentState]] = {
    IncidentState.NORMAL: {IncidentState.NORMAL, IncidentState.WATCH},
    IncidentState.WATCH: {IncidentState.WATCH, IncidentState.DEGRADED, IncidentState.NORMAL},
    IncidentState.DEGRADED: {
        IncidentState.DEGRADED,
        IncidentState.SEVERE,
        IncidentState.RECOVERING,
    },
    IncidentState.SEVERE: {IncidentState.SEVERE, IncidentState.RECOVERING},
    IncidentState.RECOVERING: {
        IncidentState.RECOVERING,
        IncidentState.NORMAL,
        IncidentState.DEGRADED,
        IncidentState.SEVERE,
    },
}


def _target_state(
    alarm: bool, drop_pp: float, watch_threshold: float, severe_threshold: float
) -> IncidentState:
    """drop_pp is the primary signal; alarm only ever *refines severity*
    once there's already a real drop, never triggers on its own. The
    CUSUM alarm this is derived from has no lower floor on its
    accumulator, so it can stay latched "true" long after drop_pp has
    returned to ~0 -- treating a latched alarm as sufficient on its own
    would keep manufacturing WATCH/DEGRADED out of an already-recovered
    metric. See docs/JOURNAL.md.
    """
    if drop_pp <= watch_threshold:
        return IncidentState.NORMAL
    if not alarm:
        return IncidentState.WATCH
    return IncidentState.SEVERE if drop_pp > severe_threshold else IncidentState.DEGRADED


def _severity_from_drop(
    drop_pp: float, watch_threshold: float, severe_threshold: float
) -> IncidentState:
    """Severity from the current drop alone, ignoring the (possibly stale)
    CUSUM alarm flag -- used to decide a genuine relapse out of RECOVERING,
    so a residually-latched alarm can't manufacture a false relapse on a
    metric that is actually still fine. See docs/JOURNAL.md."""
    if drop_pp > severe_threshold:
        return IncidentState.SEVERE
    if drop_pp > watch_threshold:
        return IncidentState.DEGRADED
    return IncidentState.NORMAL


def _step(
    state: IncidentState,
    target: IncidentState,
    drop_pp: float,
    improving: bool,
    watch_threshold: float,
    severe_threshold: float,
) -> IncidentState:
    if state in (IncidentState.DEGRADED, IncidentState.SEVERE):
        # The CUSUM alarm this is derived from has no lower floor on its
        # accumulator, so after a long or severe drop it can stay latched
        # "true" for far longer than the drop itself lasted, even once the
        # metric is already fully back to its own baseline (drop_pp ~ 0)
        # -- at that point there is nothing left to trend "improving"
        # against, so the improving check alone would leave the FSM stuck
        # reporting DEGRADED on a metric that has plainly recovered. See
        # docs/JOURNAL.md.
        if improving or drop_pp <= watch_threshold:
            return IncidentState.RECOVERING
        idx = ESCALATION_ORDER.index(state)
        target_idx = ESCALATION_ORDER.index(target)
        if target_idx > idx:
            return ESCALATION_ORDER[idx + 1]
        return state

    if state == IncidentState.RECOVERING:
        if drop_pp <= watch_threshold:
            return IncidentState.NORMAL
        severity = _severity_from_drop(drop_pp, watch_threshold, severe_threshold)
        if not improving and severity in (IncidentState.DEGRADED, IncidentState.SEVERE):
            return severity  # a genuine relapse -- both are directly-allowed edges
        return IncidentState.RECOVERING

    # state in (NORMAL, WATCH): step at most one level toward target
    idx = ESCALATION_ORDER.index(state)
    target_idx = ESCALATION_ORDER.index(target) if target != IncidentState.RECOVERING else idx
    if target_idx > idx:
        return ESCALATION_ORDER[idx + 1]
    if target_idx < idx:
        return ESCALATION_ORDER[idx - 1]
    return state


def run_fsm(
    sr: list[float],
    baselines: list[float],
    alarms: list[bool],
    watch_threshold: float = 0.03,
    severe_threshold: float = 0.15,
    smoothing_lambda: float = 0.3,
) -> list[IncidentState]:
    """Classify each minute's incident state from the same per-minute
    series src.detection.cusum.cusum_sr already computes: success rate,
    the CUSUM baseline in effect, and the alarm flag. Minutes with no
    baseline yet (CUSUM still warming up) keep the current state.
    """
    states: list[IncidentState] = []
    state = IncidentState.NORMAL
    smoothed_drop: float | None = None

    for rate, baseline, alarm in zip(sr, baselines, alarms, strict=True):
        if baseline != baseline:  # NaN -- no baseline established yet
            states.append(state)
            continue

        drop_pp = max(baseline - rate, 0.0)
        prev_smoothed = smoothed_drop
        smoothed_drop = (
            drop_pp
            if smoothed_drop is None
            else (1 - smoothing_lambda) * smoothed_drop + smoothing_lambda * drop_pp
        )
        improving = prev_smoothed is not None and smoothed_drop < prev_smoothed - 1e-9

        target = _target_state(alarm, drop_pp, watch_threshold, severe_threshold)
        new_state = _step(state, target, drop_pp, improving, watch_threshold, severe_threshold)

        assert new_state in ALLOWED_TRANSITIONS[state], f"{state} -> {new_state} not permitted"
        state = new_state
        states.append(state)

    return states
