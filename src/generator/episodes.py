"""Episode schedule — the 7 injected episode types plus decoys.

Committed before the detector exists, per docs/EPISODE-SPEC.md and
CLAUDE.md rule #4. Episode *shapes* (which slice, what kind of effect, what
it tests) are fixed here; only onset timing and small parameter jitter vary
between the main seed and the held-out seed, via the numpy Generator passed
in — see docs/EPISODE-SPEC.md §7.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass
class EpisodeSpec:
    episode_id: str
    episode_type: str
    tier: str
    decoy: bool
    slice_filter: dict[str, str]
    onset_min: int
    plateau_start_min: int
    plateau_end_min: int
    recovery_end_min: int
    description: str
    sr_drop: float | None = None
    target_sr: float | None = None  # used by F: an absolute floor, not a delta
    latency_multiplier: float | None = None
    volume_multiplier: float | None = None
    oracle_confidence_override: float | None = None
    persistent: bool = False  # F only: effect active for the whole simulation
    extra: dict = field(default_factory=dict)

    def effect_fraction(self, t_min: int) -> float:
        if self.persistent:
            return 1.0
        if t_min < self.onset_min:
            return 0.0
        if t_min < self.plateau_start_min:
            span = max(self.plateau_start_min - self.onset_min, 1)
            return (t_min - self.onset_min) / span
        if t_min <= self.plateau_end_min:
            return 1.0
        if t_min <= self.recovery_end_min:
            span = max(self.recovery_end_min - self.plateau_end_min, 1)
            return 1.0 - (t_min - self.plateau_end_min) / span
        return 0.0

    def is_tagged(self, t_min: int) -> bool:
        """Whether an attempt at t_min should carry this episode's ground-truth id."""
        if self.persistent:
            return self.onset_min <= t_min <= self.recovery_end_min
        return self.onset_min <= t_min <= self.recovery_end_min

    def matches(self, ctx: dict) -> bool:
        for key, value in self.slice_filter.items():
            if key == "bin_prefix":
                if not (ctx.get("x_bin") or "").startswith(value):
                    return False
            elif ctx.get(key) != value:
                return False
        return True


def _slot(rng: np.random.Generator, center_min: int, jitter_min: int) -> int:
    return int(center_min + rng.integers(-jitter_min, jitter_min + 1))


def build_episode_set(rng: np.random.Generator, sim_minutes: int) -> list[EpisodeSpec]:
    """Build the episode + decoy schedule for one generation run.

    `rng` drives onset jitter only — episode shapes are fixed. Call with a
    fresh Generator (different seed) for the held-out set to get different
    timing without reusing the same episode instances.
    """
    n_slots = 9
    slot_width = sim_minutes // n_slots
    episodes: list[EpisodeSpec] = []

    def next_center(i: int) -> int:
        return slot_width * i + slot_width // 2

    # A — Bank degradation: HDFC x UPI, SR 94 -> 68 over 40 min. Easy — needs
    # a high-volume slot, so it takes slot 1 (a busy time of day) rather
    # than slot 0.
    onset = _slot(rng, next_center(1), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-A",
            episode_type="A_bank_degradation",
            tier="easy",
            decoy=False,
            slice_filter={"method": "upi", "x_issuer": "HDFC"},
            onset_min=onset,
            plateau_start_min=onset + 10,
            plateau_end_min=onset + 30,
            recovery_end_min=onset + 40,
            sr_drop=0.26,
            description="HDFC x UPI success rate degrades from ~94% to ~68% over 40 minutes",
        )
    )

    # B — PSP timeout: PSP-A, all banks. P95 800ms -> 4.8s, SR barely moves.
    # Medium. Filter is broad (psp only) so volume is high even off-peak —
    # takes slot 0.
    onset = _slot(rng, next_center(0), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-B",
            episode_type="B_psp_timeout",
            tier="medium",
            decoy=False,
            slice_filter={"x_psp": "PSP-A"},
            onset_min=onset,
            plateau_start_min=onset + 8,
            plateau_end_min=onset + 25,
            recovery_end_min=onset + 33,
            sr_drop=0.02,
            latency_multiplier=6.0,
            description=(
                "PSP-A P95 latency degrades from ~800ms to ~4.8s; success rate barely moves"
            ),
        )
    )

    # C — Card BIN issue: BIN 523xxx, SR 92 -> 41. Medium (deep-lattice attribution).
    onset = _slot(rng, next_center(2), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-C",
            episode_type="C_card_bin_issue",
            tier="medium",
            decoy=False,
            slice_filter={"method": "card", "bin_prefix": "523"},
            onset_min=onset,
            plateau_start_min=onset + 6,
            plateau_end_min=onset + 24,
            recovery_end_min=onset + 30,
            sr_drop=0.51,
            description="Card BIN 523xxx success rate collapses from ~92% to ~41%",
        )
    )

    # D — Regional: Rajasthan x UPI x PSP-B, SR 93 -> 72. Hard (low volume).
    onset = _slot(rng, next_center(3), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-D",
            episode_type="D_regional",
            tier="hard",
            decoy=False,
            slice_filter={"method": "upi", "x_psp": "PSP-B", "x_region": "Rajasthan"},
            onset_min=onset,
            plateau_start_min=onset + 10,
            plateau_end_min=onset + 28,
            recovery_end_min=onset + 36,
            sr_drop=0.21,
            description="Rajasthan x UPI x PSP-B success rate drops from ~93% to ~72%",
        )
    )

    # E — Merchant-specific: a travel-category merchant, cards. SR 91 -> 54. Medium.
    onset = _slot(rng, next_center(4), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-E",
            episode_type="E_merchant_specific",
            tier="medium",
            decoy=False,
            slice_filter={"method": "card", "x_merchant_id": "M122"},
            onset_min=onset,
            plateau_start_min=onset + 8,
            plateau_end_min=onset + 26,
            recovery_end_min=onset + 34,
            sr_drop=0.37,
            description="Merchant M122 (travel) card success rate drops from ~91% to ~54%",
        )
    )

    # F — Calibration drift: persistent slice bias, invisible to a changepoint
    # detector because there is no change — the oracle has always been wrong
    # here. L10 only.
    window_start = _slot(rng, next_center(5), 30)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-F",
            episode_type="F_calibration_drift",
            tier="l10",
            decoy=False,
            slice_filter={"method": "upi", "x_psp": "PSP-C", "x_issuer": "ICICI"},
            onset_min=window_start,
            plateau_start_min=window_start,
            plateau_end_min=window_start + 180,
            recovery_end_min=window_start + 180,
            target_sr=0.62,
            oracle_confidence_override=0.91,
            persistent=True,
            description=(
                "ICICI x UPI x PSP-C realised success rate ~62% sustained over 3 hours, "
                "oracle confidence held at ~0.91 throughout — calibration gap, not a changepoint. "
                "Well above the 14-minute minimum sustain threshold used to distinguish "
                "drift from noise."
            ),
        )
    )

    # G — Two concurrent causes: an A-shaped and a C-shaped episode overlapping
    # in time, on different slices. Attribution honesty test — expect the
    # detector to report over-broad rather than wrong. Hard.
    g_onset = _slot(rng, next_center(6), 20)
    episodes.append(
        EpisodeSpec(
            episode_id="ep-G1",
            episode_type="G_concurrent",
            tier="hard",
            decoy=False,
            slice_filter={"method": "upi", "x_issuer": "AXIS"},
            onset_min=g_onset,
            plateau_start_min=g_onset + 8,
            plateau_end_min=g_onset + 26,
            recovery_end_min=g_onset + 34,
            sr_drop=0.24,
            description="Concurrent cause 1/2: AXIS x UPI degrades",
        )
    )
    episodes.append(
        EpisodeSpec(
            episode_id="ep-G2",
            episode_type="G_concurrent",
            tier="hard",
            decoy=False,
            slice_filter={"method": "card", "bin_prefix": "523"},
            onset_min=g_onset + 10,
            plateau_start_min=g_onset + 16,
            plateau_end_min=g_onset + 30,
            recovery_end_min=g_onset + 36,
            sr_drop=0.30,
            description="Concurrent cause 2/2: card BIN 523xxx degrades, overlapping ep-G1",
        )
    )

    # Decoy 1 — volume spike, SR held constant. Must NOT fire the detector.
    onset = _slot(rng, next_center(7), 20)
    episodes.append(
        EpisodeSpec(
            episode_id="decoy-volume-spike",
            episode_type="decoy_volume_spike",
            tier="decoy",
            decoy=True,
            slice_filter={"x_merchant_category": "ecommerce"},
            onset_min=onset,
            plateau_start_min=onset + 5,
            plateau_end_min=onset + 20,
            recovery_end_min=onset + 25,
            volume_multiplier=3.0,
            description="Ecommerce traffic spikes 3x (flash-sale shaped); success rate unaffected",
        )
    )

    # Decoy 2 — merchant onboarding ramp: a brand-new, low-volume, noisy
    # merchant appearing mid-simulation. Must NOT fire the detector.
    onset = _slot(rng, next_center(8), 20)
    episodes.append(
        EpisodeSpec(
            episode_id="decoy-onboarding",
            episode_type="decoy_onboarding",
            tier="decoy",
            decoy=True,
            slice_filter={"x_merchant_id": "M900"},
            onset_min=onset,
            plateau_start_min=onset,
            plateau_end_min=sim_minutes,
            recovery_end_min=sim_minutes,
            description="New merchant M900 onboards mid-run: low, ramping volume, normal SR",
        )
    )

    return episodes
