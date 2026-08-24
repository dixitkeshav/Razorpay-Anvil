# Anvil — Phased Build Plan

Source of truth for what "done" means at each phase. See `CLAUDE.md` for the
hard constraints that apply across every phase (no hand-written eval numbers,
layer boundaries, frozen generator, invisible ground truth, floor before USP).

Each phase ends in a machine-checkable gate: `make test-phase-N`. A phase is
complete when that gate passes — not when the code looks finished. Commit at
every phase boundary.

---

## FLOOR (Phases 0–8) — mandatory Track 03 submission

| Phase | Goal | Gate — `make test-phase-N` passes when |
|---|---|---|
| **0** | Scaffold: repo, Docker, Makefile, `CLAUDE.md`, `EPISODE-SPEC.md`, `OUTCOME-MODEL.md`, Razorpay test-mode keys | A test creates a real test-mode order via the Razorpay SDK and asserts a valid `order_id`. |
| **1** | Event generator: base traffic, diurnal curve, 7 episode types, decoys, difficulty tiers | `make seed` emits ≥100k events; every injected episode is recoverable from ground truth; schema validates |
| **2** | DuckDB ingestion + slice-lattice rollups | Query returns SR/P95/timeout-rate for any slice × minute; matches a hand-computed fixture |
| **3** | CUSUM on SR + EWMA on P95 + hierarchical BH | Detects all easy-tier episodes; fires at ≤2 false alarms/day on a clean stretch; passes the no-ground-truth lint test |
| **4** | Attribution: contribution decomposition, minimal explanatory cut | Names the correct slice on episodes A, C, D, E; reports over-broad rather than wrong on G |
| **5** | Impact estimator + incident state machine | Affected-attempt count within 5% of truth; state transitions follow the documented FSM |
| **6** | Policy engine: gates, EV, guardrails, stopping rules, escalation | Every gate has a passing unit test; no action can bypass `[3]`; escalation triggers on all four documented conditions |
| **7** | Execution (Razorpay test-mode + simulator) + Recovery Ledger | Ledger is append-only; replaying the same idempotency key does not double-charge; ≥1 real test-mode recovery completes |
| **8** | Counterfactual replay + scorecard | `make eval` emits `docs/RESULTS.md` with a real ₹ figure, agent-on vs agent-off, from the same seed |

> ⛔ **FLOOR COMPLETE.** A valid Track 03 submission exists at this point.
> Verify `make eval` output before proceeding. If the schedule collapses,
> stop here and still submit.

---

## USP (Phases 9–12) — the memorable layer

| Phase | Goal | Gate |
|---|---|---|
| **9** | LLM layer: error normalisation, incident narrative, response cache, injection defense | `test_llm_cannot_reach_policy.py` passes; injection fixture produces inert narrative + unchanged ledger; full suite passes with network disabled |
| **10** | Decision-quality monitor (L10) | Detects episode F, which every L2 detector misses; calibration gap reported per slice |
| **11** | Anvil MCP server: `get_incident`, `explain_attribution`, `query_recovery_ledger` | Claude Desktop or Claude Code connects and successfully calls all three tools |
| **12** | Dashboard: Ops overview + Incident detail with failure analysis embedded | Loads from a clean `docker compose up`; renders a full incident end to end |

> ⛔ **FEATURE FREEZE after Phase 12.** Nothing new gets added after this line.

---

## CLOSE (Phases 13–15)

| Phase | Goal | Gate |
|---|---|---|
| **13** | Held-out generation, full eval, sensitivity sweep, failure taxonomy | `make holdout && make eval && make sweep` from a clean clone; every README number is generated output |
| **14** | README, ARCHITECTURE, NON-GOALS, POLICY, journal cleanup | A stranger clones and reproduces your numbers with two commands |
| **15** | Record and edit the 5-minute video; submit the form | Submitted, with a day of buffer |

---

## Rules that apply to every phase

1. Never write evaluation numbers by hand. Every figure comes from `make eval` / `make sweep`.
2. `src/detection/`, `src/attribution/`, `src/policy/` may not import `src/llm/`.
3. No module under `src/detection/`, `src/attribution/`, `src/policy/` may read `x_episode_id`.
4. `src/generator/` is frozen once committed at Phase 1.
5. Do not begin Phase 9 until `make eval` emits a complete scorecard with a real rupee figure.
6. Every money action passes through `src/policy/`.

See `CLAUDE.md` for full detail and rationale on each.
