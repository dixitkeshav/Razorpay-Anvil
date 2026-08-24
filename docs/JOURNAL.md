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

## Phase 4 — 2026-08-24

The longest debugging arc so far, all on one episode (D: a low-volume
regional incident, `upi x PSP-B x Rajasthan`). Each fix below was real and
each one exposed the next problem:

- **Missing dimension.** The plan's own lattice diagram (method -> +psp ->
  +issuer -> +region/+merchant) has no BIN dimension, but episode C is
  defined by a card BIN. Fixed by adding a derived `x_bin_prefix`
  dimension (`SUBSTR(x_bin, 1, 3)`) to `src/ingest/lattice_levels.py` —
  extending ingest/detection infrastructure is allowed; the frozen
  generator was never touched.
- **Parent-level dilution.** D's true cause affects ~85 attempts inside a
  window where the "upi" aggregate sees ~800 — its aggregate deficit
  rounds to 0, so the original "if parent deficit <= 0, give up" logic
  reported nothing to explain. Fixed by always running one round of
  per-dimension search regardless of the parent's own diluted deficit, and
  adopting whatever real localized deficit that round finds as the new
  reference instead of a false negative.
- **Premature stop after adoption.** Once adopted, that reference trivially
  "covers itself" (fraction=1.0), which tripped the normal
  coverage-reached stopping rule immediately — never checking whether a
  second dimension (the true cause needs two: psp AND region) would
  refine the cut further. Fixed by forcing one extra round after any
  adoption before the coverage gate is allowed to stop the search.
- **Volume-biased ranking.** Ranking candidates by raw excess-failure count
  picked a PSP with 42 attempts and a small real gap over the actual-cause
  PSP with 22 attempts and a much larger gap — deficit is volume-weighted,
  so more traffic can out-rank more damage. Fixed by ranking on p-value
  (statistical strength) instead.
- **Multiple comparisons.** Picking the single smallest p-value across ~37
  simultaneous dimension x value tests is exactly the trap detection's
  per-level BH exists to avoid — some unrelated slice will look
  significant by chance. Added the same BH correction to attribution's
  round-by-round candidate selection.
- **Borrowed baseline.** Even after BH, a specific merchant (M141, nothing
  to do with D) kept winning because it was tested against the *parent's*
  blanket baseline SR rather than its own — a merchant with a normally
  slightly-lower rate reads as "anomalous" against a global average it was
  never really part of. Fixed by giving every candidate its own
  pre/post-window historical baseline, computed from the same slice
  filter, falling back to the parent baseline only when a candidate has
  too little history of its own.
- **Not sustained.** M141 *still* won even against its own baseline. Split
  the window in half to check: M141's SR was 1.00 in the first half and
  0.59 in the second — a lucky/unlucky split, not a real incident. The
  true cause (Rajasthan x PSP-B) was degraded in *both* halves (0.78 and
  0.85). Added a sustained-degradation requirement — both halves must
  individually sit below the candidate's own baseline — as the final
  gate. Real incidents degrade the whole window; noise flukes concentrate
  in whichever half got unlucky.

After all six fixes, D correctly resolves to `{method: upi, region:
Rajasthan}` — a genuinely correct partial match. It doesn't recover `psp:
PSP-B` on top of that, because splitting the already-thin 85-attempt
Rajasthan sample three ways by PSP leaves too little evidence to justify
the extra claim — an honest "over-broad, not wrong" outcome for a
Hard-tier, low-volume episode, exactly the failure mode the tier is
supposed to produce. A, C, E, and both halves of G were correct without
needing any of these fixes to be episode-specific — none of the six
changes reference D, ep-A, or any other episode by name.
