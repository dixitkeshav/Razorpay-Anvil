# Architecture

Anvil is a layered pipeline: each layer reads only the layer(s) below it,
and every layer boundary that matters for trust or money is enforced by a
test, not a comment. See CLAUDE.md for the hard constraints this document
assumes throughout.

```
L0  EVENT SOURCE          src/generator/     frozen after Phase 1
L1  AGGREGATION            src/ingest/        DuckDB over Parquet
L2  DETECTION               src/detection/     hand-rolled CUSUM + EWMA, no ground truth, no LLM
L3  ATTRIBUTION              src/attribution/   minimal explanatory cut, no ground truth, no LLM
L4  IMPACT                   src/impact/        affected attempts/GMV, incident state machine
L5  POLICY                   src/policy/        THE TRUST BOUNDARY — every money action passes through here
L6  EXECUTION                 src/execution/     Razorpay test-mode adapter + outcome simulator
L7  LEDGER                    src/ledger/        append-only, immutable, frozen entries
L8  EVALUATION                 src/evaluation/    counterfactual replay, sensitivity sweep, recall
L9  LLM                        src/llm/           downstream of every money decision, read-only, terminal
L10 DECISION-QUALITY MONITOR    src/quality/       oracle-confidence vs realised-outcome, per slice
```

Two client surfaces sit on top of the same core: the dashboard (`web/` +
`src/api/`) for humans, and the MCP server (`src/mcp/`) for agents. Both
are thin — they read from the same pipeline functions the tests exercise
directly, and neither one contains logic that isn't already gated by a
phase test below it.

---

## The trust boundary

L5 (`src/policy/`) is the only code path that may execute a retry,
reroute, or hold. `src/execution/executor.py::execute()` is the only
function that calls the Razorpay adapter or the outcome simulator, and it
is only ever called with a `Decision` that came out of
`src/policy/engine.py::decide()`. There is no other path from a detected
incident to a money-moving action anywhere in this codebase — see
CLAUDE.md rule #6.

Within `decide()`, the ordering is fixed and tested
(`tests/test_policy_gates.py`): eligibility gates run first and fail
closed, expected value is computed only for what survives, and guardrails
run last and always win over EV — never the reverse. `docs/POLICY.md` has
the full gate/guardrail/escalation table.

---

## Ground truth is invisible to the pipeline

`x_episode_id` (which injected episode, if any, produced a given attempt)
exists only in the generator's output and the evaluation layer. No module
under `src/detection/`, `src/attribution/`, or `src/policy/` may read it —
enforced two ways:

- `tests/test_detector_ignores_ground_truth.py` greps every file in those
  three directories for the literal string, dynamically, so it keeps
  protecting new files as they're added.
- The same test file also greps for `src.llm`, a cheap first check; the
  authoritative version is next.

## The LLM is downstream, read-only, terminal

L9 (`src/llm/`) normalizes error text and writes incident narratives. It
is called *after* a decision has already been made and *after* the ledger
entry for it already exists — nothing it produces can change either one,
because nothing downstream of it reads its output back into the pipeline.

This is proven two ways, not asserted once:

- `tests/test_llm_cannot_reach_policy.py` parses every file under `src/`
  with Python's own `ast` module, builds the real import graph, and walks
  reachability from `src/detection/`, `src/attribution/`, and
  `src/policy/` — confirming no path, direct or transitive through any
  intermediate module, reaches `src/llm/`.
- `tests/test_injection_defense.py` runs a full `decide()` +
  `execute()` pipeline, captures the resulting ledger entries, then feeds
  adversarial prompt-injection payloads through `src/llm/normalize.py` and
  `src/llm/narrative.py` — including ones a compromised model might
  actually return, via a monkeypatched network call — and asserts the
  ledger is byte-for-byte unchanged afterward. Every LLM call also falls
  back to a deterministic template on any schema violation or network
  failure (`src/llm/schemas.py`, Pydantic-validated), and the whole test
  file runs with no network calls at all — proven directly, not just
  claimed, by monkeypatching the network call to raise if it's ever
  reached in the offline path.

---

## The slice lattice

Detection and attribution both operate over the same dimensions —
`method`, `x_psp`, `x_issuer`, `x_region`, `x_merchant_id`, and (added in
Phase 4) the derived `x_bin_prefix` — walked hierarchically rather than
as a full cross-product, with Benjamini-Hochberg correction applied
*within* each level rather than Bonferroni across the whole lattice (see
`docs/JOURNAL.md` Phase 3 for what Bonferroni-style over-correction would
have cost). `src/ingest/lattice_levels.py` defines the levels;
`src/detection/detector.py` only drills into a child once its parent
fires, which is what keeps the total number of statistical tests in the
tens rather than the thousands.

Attribution (`src/attribution/decomposition.py`) is a separate, more
flexible mechanism: given a detected parent slice, it greedily adds the
single dimension that most improves statistical significance
(BH-corrected within each round, ranked by p-value not raw magnitude —
see `docs/JOURNAL.md` Phase 4 for why magnitude-ranking silently favored
volume over severity), continuing until the cut explains enough of the
parent's excess-failure deficit or no further dimension helps. The result
can be a genuinely partial cut — "over-broad, not wrong" is a designed
outcome for low-volume (Hard-tier) episodes, not a failure mode to hide.

---

## Why these specific numbers are trustworthy

Every threshold in `src/detection/`, `src/attribution/`, and
`src/quality/` that isn't a first-principles statistical formula was
tuned by grid search against the committed main seed, with the tuning
reasoning left in the code (docstrings, not just commit messages) and the
debugging story in `docs/JOURNAL.md`. Headline recall and money figures
come from a held-out set generated with a different seed and redrawn
episode timing, never used during any of that tuning — see
`docs/EPISODE-SPEC.md` §7 for the circularity protocol this is meant to
satisfy, and `docs/RESULTS.md` for what that held-out run actually found,
including where it doesn't detect an episode.

## What Anvil is not

See `docs/NON-GOALS.md` for the full list of tools and approaches
considered and rejected, and why each one didn't fit — that document is a
direct answer to "the right tool in the right place, and where you chose
not to use one."
