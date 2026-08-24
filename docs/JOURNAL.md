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

## Phase 3 — 2026-08-24

- First CUSUM pass used the textbook Binomial(n,p) variance formula
  (`se = sqrt(p(1-p)/n)`) to standardize each minute's deviation. At L1
  (per-method aggregates), this produced 7,364 "incidents" at the top level
  alone — almost entirely on `emi` (2% of traffic), where single-attempt
  minutes make the per-minute proportion statistic degenerate. Root cause
  wasn't just low n: a "method" slice pools several psp/issuer
  sub-populations with different true success rates, so its true
  minute-to-minute variance is a mixture, genuinely larger than
  Binomial(n,p) predicts — the textbook formula understated variance and
  inflated every z-score. Fixed by (a) requiring `min_n=5` attempts before
  a minute counts as evidence, and (b) replacing the theoretical variance
  with an empirically estimated one (EWMA of squared residuals), the same
  technique already used for the latency EWMA.
- Even after that fix, alarm counts stayed high because of chattering: the
  CUSUM statistic oscillated back and forth across the alarm threshold
  during a single genuine deviation, fragmenting one incident into dozens
  of 1-minute windows. Added hysteresis — an alarm now only clears once the
  statistic fully recovers to baseline (S=0), not merely once it climbs
  back above -h.
- A go/no-go bug, not a detector bug: my first false-alarm-rate check
  compared the detector's alarm windows (absolute epoch-minutes, from
  `created_at // 60`) directly against ground-truth `onset_min` (a
  simulation-relative offset from 0). Every comparison silently failed, so
  the diagnostic reported 0 real-episode hits at every threshold — looked
  like total detector failure. It was a units mismatch in the test script,
  not the detector; fixed by offsetting ground-truth minutes by
  `SIM_START_EPOCH // 60` before comparing.
- With those three fixes in place, grid-searched the CUSUM threshold `h`
  and EWMA `threshold_sigma` against the committed main seed: h=15 (not the
  textbook h=5) detects the easy-tier episode with zero false alarms across
  the full 3-day run; threshold_sigma=8 (not the textbook 3) gets the
  latency episode down to ~1 false alarm/day. Both defaults are documented
  in-code with the reasoning, not just the numbers.
