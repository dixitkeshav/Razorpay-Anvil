# Journal

Two lines a day: what broke, what we did. Feeds the application's "what
broke, and how you got out" question — see `anvil-build-plan.md` §15. Real
entries only, written as they happen.

---

## Phase 0 — 2026-08-24

- Scaffolded repo structure, `docs/PHASES.md`, `docs/EPISODE-SPEC.md`,
  `docs/OUTCOME-MODEL.md`, `docs/NON-GOALS.md`, Makefile, docker-compose,
  Phase 0 gate test (`tests/test_phase0_razorpay_auth.py`). Nothing broke
  yet — this entry exists to establish the format from day one.
- Switched the LLM dependency from Anthropic to Groq per user preference —
  `pyproject.toml` and `.env.example` updated before any code depended on
  either.

## Phase 1 — 2026-08-24

- First generator run produced technically-valid but statistically useless
  episodes: `ep-A` (Easy tier, meant to be a high-volume slice) landed at
  its scheduled slot in the diurnal trough (~4am) purely by chance from how
  9 evenly-spaced time slots map onto a 24-hour cycle, leaving only 54
  tagged attempts over the whole episode window — far too few to be
  "recoverable" in any meaningful statistical sense, and inconsistent with
  its own tier definition (Easy = high volume). Root cause: `next_center()`
  spaces episodes 480 minutes apart, and 480 divides 1440 evenly, so every
  3rd slot lands at the same time of day — episode-to-slot assignment was
  effectively picking time-of-day, not just spacing, and nobody had
  checked that. Fixed by swapping which slot indices `ep-A` (needs volume)
  and `ep-B` (broad psp-only filter, tolerates a trough fine) use, and by
  raising the base arrival rate (35/min -> 120/min) so even off-peak slices
  clear a believable sample size. Also widened `ep-F`'s persistent
  calibration-drift window from 14 to 180 minutes — the 14-minute figure in
  the build plan was a detection *threshold*, not a target duration, and at
  120/min a narrow 3-way slice over only 14 minutes couldn't produce the
  ~340-attempt sample the positioning doc uses as its own example.
