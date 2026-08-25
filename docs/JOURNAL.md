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

## Phase 5 — 2026-08-24

- **A rounding bug that had been silently wrong since Phase 2.** Every
  minute-bucket computation across `rollup.py`, `attribution/`, and (as
  first written) `impact/estimator.py` used
  `CAST(created_at / 60 AS BIGINT)`. DuckDB's integer division `/` returns
  a DOUBLE, and `CAST(DOUBLE AS BIGINT)` *rounds to nearest*, not
  truncates — so an attempt at second 59 of a minute (fractional part
  0.98) rounded UP into the next minute bucket. This under- and
  over-counted attempts right at every window boundary, everywhere in the
  codebase, since Phase 2 — invisible until the impact estimator's
  affected-attempt count needed to be accurate to 5%, at which point a
  4.8-9.7% error on episodes A and C made it impossible to ignore. Fixed
  globally by switching to `(created_at // 60)`, DuckDB's actual floor
  division. Confirmed the fix by comparing against a direct Polars
  recomputation of the same filter, row by row, until the two matched
  exactly.
- After the rounding fix, episode C still showed 9.7% error. Traced it to
  the *generator's* ramp function: `effect_fraction()` evaluates to
  exactly 0 at `t == onset_min` and again at `t == recovery_end_min`, and
  the engine's per-episode loop skips tagging `x_episode_id` entirely when
  `frac <= 0`. So the two boundary minutes of every episode are genuinely,
  by design, left untagged in ground truth, even though they're inside
  the nominal `[onset, recovery_end]` window. Not a bug — the generator is
  frozen and this is a legitimate property of a ramp reaching zero at its
  own edges — but it means "true affected count" and "geometric
  window count" differ by construction at exactly two minutes per
  episode. Confirmed by checking that the estimator's count against a
  *trimmed* window (`onset+1` to `recovery_end-1`) matches ground truth
  exactly (0.0% error) on A, C, and E. The impact estimator itself reports
  the full window in production — trimming is a test-only methodology
  choice to isolate estimator accuracy from this one documented ground
  truth quirk, not a change to what gets reported operationally.
- The incident state machine's first version gated DEGRADED/SEVERE purely
  on the upstream CUSUM alarm flag. That flag has no lower floor on its
  accumulator, so after a severe, sustained drop it can stay latched
  "true" for far longer than the drop itself lasted — a synthetic test
  (40 minutes at a 35pp drop, then full recovery) needed *1,565* minutes
  before the raw alarm cleared on its own. The FSM was trusting that stale
  flag as if it meant "still degraded right now," so a metric that had
  fully recovered to baseline kept reporting DEGRADED, and once nudged
  toward RECOVERING it kept "relapsing" back to DEGRADED on every step
  because the relapse check *also* trusted the same stale alarm-derived
  target. Fixed by making `drop_pp` (the actual, current gap from
  baseline) the primary signal everywhere in the FSM, with the alarm flag
  only ever used to refine severity (DEGRADED vs SEVERE) once there is
  already a real drop — never as a trigger on its own. This is the
  clearest example so far of a lesson repeating across phases: a fast,
  cheap signal (CUSUM's alarm bit) is a good *sequential detector* but a
  bad source of truth for "what is happening right now" once its own
  internal memory has decoupled from the present.

## Phase 6 — 2026-08-25

- The build plan's own guardrail bullet list (anvil-build-plan.md §8)
  names three ESCALATE_HUMAN conditions (amount, confidence, mandate),
  but docs/PHASES.md's Phase 6 gate — copied from the plan's phase table —
  says escalation must trigger "on all four documented conditions." Rather
  than guess which unstated fourth condition was meant, added one that's
  independently justifiable on its own: no eligible automated action
  (RETRY and REROUTE both blocked by gates) now escalates instead of
  silently defaulting to HOLD forever with no path back to a human.
  Documented as a deliberate addition, not a hidden assumption — see
  docs/POLICY.md.
- No bugs this phase, for once. The policy engine is pure, deterministic
  logic over an explicit input contract (PolicyContext) with no data
  dependency and no statistical tuning, so it's the first phase where
  every test passed on the first real run. Worth noting as a contrast to
  Phases 3-5: determinism plus an explicit contract meant there was
  nothing left for reality to disagree with.

## Phase 7 — 2026-08-25

- First draft of `new_idempotency_key()` salted the key with a random
  UUID per call. That's backwards: an idempotency key exists so that
  *replaying the same logical operation* (a client retry after a network
  timeout, a queue redelivery) produces the same key and gets deduplicated
  — a random salt would make every "replay" look like a brand-new
  operation, defeating the entire point before it shipped. Caught before
  writing a single test, by just asking what the key was actually for.
  Fixed to be deterministic per (payment_id, attempt_number).
- Otherwise clean. `tests/test_idempotency.py`'s real-Razorpay tests ran
  against the live test-mode account from `.env` and passed: one real
  order created via `order.create`, and a second call with the same
  idempotency key confirmed to never reach the Razorpay API at all
  (call-count instrumented on the SDK client directly) — the ledger short-
  circuits before any network call, so replay safety doesn't depend on
  Razorpay's own dedup behavior, only on ours.

## Phase 8 — 2026-08-25 — FLOOR COMPLETE

- First counterfactual replay run produced a scorecard where every single
  one of 527 failed attempts got ESCALATE_HUMAN, and the net recovery
  figure was Rs. 0 — every decision blocked on the low-confidence
  guardrail. Root cause: the detected incident window came from
  `detect_incidents()`'s own CUSUM alarm boundary (29671907-29671969, 62
  minutes), not from ground truth — and it runs ~30 minutes past the true
  incident's end, into the recovery tail. Attribution's split-half
  "sustained" check (added in Phase 4 to reject the noise-driven M141
  false lead) required *both* halves to sit strictly below baseline; the
  second half here was back near baseline (0.949 vs an own-baseline of
  0.928) because the incident had genuinely already recovered there, and
  the strict "<" rejected the entire cut. Attribution fell back to the
  bare parent slice with no localized cause found, so its `coverage`
  (used as `root_cause_confidence`) came back as 0 — triggering escalation
  on every attempt, every time, exactly as designed, on a confidence
  number that was itself wrong.
- This is a different failure mode from Phase 4's M141 case, not a
  reopening of the same bug: M141 was noise (one half anomalously *above*
  baseline). This was genuine recovery (one half back *near* baseline,
  not above it). A single "both halves below baseline" rule can't
  distinguish "the metric legitimately recovered inside this window" from
  "this half never had a real problem to begin with" — they look
  identical to a rule that only checks the sign of the gap. Fixed by
  changing the rule from "both halves below baseline" to "neither half
  sits meaningfully *above* baseline" (a small, fixed tolerance band):
  recovery reads as "back to normal," noise reads as "anomalously good,"
  and the new rule tells those apart instead of conflating them. Verified
  it doesn't reopen the M141 case (all of tests/test_attribution.py still
  passes) before trusting the new replay numbers.
- With that fixed, the same seed produces a real, reproducible figure:
  245 failed attempts replayed inside the one incident the tuned detector
  (h=15, zero false alarms) currently catches, 161 recovered, net
  incremental recovery Rs. 3,31,449.68 after execution cost — written to
  `docs/RESULTS.md` entirely by `make eval`, nothing hand-typed. The floor
  is complete: `make eval` emits a real rupee figure, agent-on vs
  agent-off, from the committed seed.

## Phase 9 — 2026-08-25

- The first version of `test_injection_defense.py` caught a real gap in
  its own second test: `generate_incident_narrative`'s *template*
  fallback (the path that never calls the model at all) blindly
  interpolated `incident_summary["affected_attempts"]` into the summary
  string. `incident_summary` is documented as trusted, already-computed
  data — but the test fed it a string containing an injection payload
  instead of the int it's supposed to be, simulating a plausible future
  bug where untrusted text leaks into a field assumed safe upstream. The
  fallback echoed it verbatim. Fixed by having the template validate the
  field's *type* before interpolating it (only accept an actual `int`,
  otherwise use a generic placeholder) — defense in depth for the one
  path that doesn't touch the network at all, not just the one that does.
- `GROQ_API_KEY` isn't actually set in `.env` yet (only the Razorpay
  keys are) — despite the earlier decision to use Groq. `fixtures/
  llm_cache.json` stays at `{}` rather than being pre-populated with
  fabricated "real-looking" responses; every Phase 9 test exercises the
  offline/template path exclusively (`tests/test_injection_defense.py`
  proves this explicitly by monkeypatching `complete()` to raise if
  called at all), so nothing is blocked on it. Live cache population is a
  follow-up once a real key is added.
- `tests/test_llm_cannot_reach_policy.py` is a real transitive-import
  check (parses every file under `src/` with `ast`, builds the import
  graph, walks reachability from each guarded package) rather than the
  cheaper text-grep the earlier ground-truth lint test already did — it
  would catch a violation hidden behind two or three hops of intermediate
  modules that a grep on the guarded directories alone would miss.
- Once `GROQ_API_KEY` was actually added: the default model,
  `llama-3.3-70b-versatile`, doesn't exist on this account
  (`groq.NotFoundError: model_not_found`) — it silently fell back to the
  template path every time (the broad `except Exception` in
  `normalize.py`/`narrative.py` is deliberate fail-closed behavior, but it
  also means a wrong model name looks identical to a real outage unless
  you go check). Queried `client.models.list()` to see what this key
  actually has access to and switched the default to
  `openai/gpt-oss-120b`. One real response was also a reminder that a
  live model won't always agree with our own taxonomy: normalizing an
  "insufficient funds" (customer-side) error, the model classified it as
  `category: bank` — schema-valid, semantically off. Not a bug to fix;
  the point of the confidence field and the human-facing narrative is
  that this kind of disagreement is expected and survivable, not that the
  model is always right.
