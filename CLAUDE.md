# CLAUDE.md — Anvil

Operating rules for agentic work in this repository. Read `docs/PHASES.md` before starting any phase.

---

## What this project is

Anvil is a payment-degradation detection and revenue-recovery system for the Razorpay AI Buildathon, Track 03. It detects success-rate degradation across a slice lattice, attributes the failure to a specific cut of the network, executes bounded recovery actions, and measures incremental rupees recovered against a do-nothing baseline.

It is **not** a routing model, a fraud detector, or a subscription-recovery agent. Do not build any of those.

---

## Hard constraints

### 1. Never write evaluation numbers by hand

No numeric result may be typed into any document. Every figure in `README.md`, `docs/RESULTS.md`, and `docs/SENSITIVITY.md` must be emitted by `make eval` or `make sweep` and committed as generated output.

If you cannot produce a number by running code, **omit it and say so**. Do not fill in a placeholder, do not estimate, do not carry a number forward from an earlier run without re-running.

This is the most important rule in this file. Fabricated metrics are worse than missing ones.

### 2. Layer boundaries are enforced by tests, not convention

```
src/detection/    may not import src/llm/
src/attribution/  may not import src/llm/
src/policy/       may not import src/llm/
src/llm/          may not import from any layer above it
```

The LLM is downstream of every money decision. It describes; it never causes. `tests/test_llm_cannot_reach_policy.py` enforces this. Do not weaken or skip that test.

### 3. Ground truth is invisible to the pipeline

`x_episode_id` is simulation ground truth. No module under `src/detection/`, `src/attribution/`, or `src/policy/` may read it, join on it, or infer from it. `tests/test_detector_ignores_ground_truth.py` enforces this.

If a detector suddenly reports near-perfect recall, assume leakage before assuming success.

### 4. The generator is frozen

Once `src/generator/` is committed at Phase 1, do not modify it. Not to make a detector pass. Not to adjust an episode that seems too hard. The evaluation is only meaningful if the data was authored before the detector existed.

If a phase gate cannot be met, fix the detector or report the failure. Never adjust the data.

### 5. Floor before USP

Phases 0–8 are the mandatory Track 03 floor. Do not begin Phase 9 until `make eval` emits a complete scorecard containing a real rupee recovery figure.

### 6. Every money action passes through the policy engine

No code path may execute a retry, reroute, or hold without going through `src/policy/`. Eligibility gates fail closed. Guardrails override expected value, never the reverse.

---

## Working style

- **Phase gates are the definition of done.** A phase is complete when `make test-phase-N` passes, not when the code looks finished.
- **Commit at every phase boundary.** Clean, descriptive message. This is the rollback point.
- **Write the test before the implementation** where the phase gate specifies behaviour.
- **Stop and report** if a gate cannot be met after reasonable effort. Do not lower the gate.
- **Append to `docs/JOURNAL.md`** whenever something breaks and you fix it: what broke, what you did. One or two lines. This feeds a required application answer.

---

## Style and stack

- Python 3.11, Polars for dataframes, DuckDB over Parquet for the event store
- FastAPI + Pydantic v2 for the service; React + Vite + Tailwind + Recharts for the dashboard
- Hand-rolled CUSUM in `src/detection/` — do not swap in a changepoint library
- `ruff` clean, type hints on public functions
- No Kafka, no Redis, no Postgres, no Kubernetes, no bandit/RL policy, no RAG. If one seems necessary, stop and ask.

---

## Razorpay specifics

- All payment objects follow Razorpay's schema. Simulation-only fields are prefixed `x_`.
- Use Razorpay's real error code vocabulary (`error_code`, `error_source`, `error_step`, `error_reason`).
- Execution uses the official `razorpay` Python SDK in **test mode only**. Never use live keys.
- Idempotency keys on every execution call. Replaying a key must not double-charge; `tests/test_idempotency.py` enforces this.
- Do not claim integration with Vulcan. There is no public API. The `VulcanOracle` class is a documented stub implementing the `RoutingOracle` protocol, and nothing more.

---

## Untrusted input

`description`, `error_description`, and merchant-supplied notes are attacker-controlled. They flow into LLM prompts at L9 only, wrapped in an explicit untrusted-data fence, with structured Pydantic-validated output. A schema violation falls back to the template narrative. No field derived from untrusted text may reach `src/policy/`.

---

## Secrets

`.env` is gitignored; `.env.example` is committed. Never commit keys, never print them to logs, never hardcode them in tests. If you need a credential that isn't in `.env.example`, stop and ask.
