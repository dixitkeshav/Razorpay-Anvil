# Anvil

**Razorpay AI Buildathon · Track 03 (AI Revenue Recovery)**

> Razorpay's Vulcan makes millions of routing decisions a day. Anvil watches
> the ground underneath them — detecting when payment performance degrades,
> attributing the failure to a specific slice of the network, executing a
> bounded recovery, and proving in rupees how much of that revenue came back.

Anvil is not a routing model, a fraud detector, or a subscription-recovery
agent. See `docs/NON-GOALS.md` for the full list of what this deliberately
is not, and why.

Build status: **Documentation complete (Phase 14).** `docs/RESULTS.md` and
`docs/SENSITIVITY.md` are generated from a held-out set — fresh seed,
redrawn episode timing, never used to tune the detector or attribution —
and every number reproduces from a clean clone with the two commands
below, no credentials required. Phase 15 (video, submission) is next.

---

## How this meets the Track 03 bar

| # | Bar requirement | Anvil deliverable | Evidence |
|---|---|---|---|
| 1 | Detects revenue at risk | CUSUM detector on success rate + EWMA on P95 latency | `docs/RESULTS.md` — stratified recall by tier, held-out set |
| 2 | Determines the right intervention | Policy engine: eligibility → expected value → guardrails | Per-action rationale in ledger, `tests/test_policy_gates.py` |
| 3 | Executes a bounded recovery workflow | Razorpay test-mode execution with idempotency | `tests/test_idempotency.py` — a real test-mode order, and a real replay proven not to double-charge |
| 4 | Measured money recovered across a batch | Counterfactual replay, agent-on vs agent-off | `docs/RESULTS.md` — net incremental recovery, held-out set |
| 5 | Compliant escalation | Amount thresholds, low-confidence escalation, mandate rules, no-eligible-action fallback | `docs/RESULTS.md` escalation table, `tests/test_escalation_thresholds.py` |
| 6 | Stopping rules | Max retries, cooldowns, circuit-break on SEVERE state | `docs/POLICY.md` + `tests/test_stopping_rules.py` |
| 7 | Audit trail | Append-only Recovery Ledger, every action traceable | `tests/test_ledger_append_only.py`; browsable in the dashboard and over MCP (`query_recovery_ledger`) |

Every row in the "Evidence" column above is real, generated output — the
figures in `docs/RESULTS.md` come from `make eval` against the held-out
set (CLAUDE.md rule #1), and every test named above is in this repo and
passing.

---

## Quickstart

Every number in `docs/RESULTS.md` and `docs/SENSITIVITY.md` reproduces
from a clean clone with two commands, no credentials required — verified
directly: `.env` removed, `.venv` deleted, run both, diffed the output
against what's committed, byte-identical apart from the generation
timestamp.

```bash
make install
make reproduce
```

For everything else (the full test suite, including two tests that need
real Razorpay test-mode credentials and skip cleanly without them):

```bash
cp .env.example .env   # optional — fill in Razorpay test-mode keys + Groq key
make install
make test               # full suite, all phase gates through Phase 13
```

`make reproduce` chains `seed`, `eval`, and `sweep`. `eval` and `sweep`
regenerate the held-out set in-memory themselves (same seed,
deterministic) rather than reading `make holdout`'s output off disk —
`make holdout` exists separately to put the held-out parquet files on
disk for anyone who wants to inspect them directly.

---

## Dashboard

```bash
docker compose up --build
```

Ops overview at `http://localhost:5173`, API at `http://localhost:8000`.
Both compute their state once, on first request, from the committed main
seed — the same deterministic pipeline behind `make eval`. Click into any
incident for the full detail view: attribution trace, affected merchants,
and the Recovery Ledger.

The Anvil MCP server (`src/mcp/server.py`) exposes the same incident data
over the Model Context Protocol — `get_incident`, `explain_attribution`,
`query_recovery_ledger` — for Claude Desktop, Claude Code, or any other
MCP client:

```bash
.venv/bin/python -m src.mcp.server
```

---

## Repo layout

See `docs/ARCHITECTURE.md` for the as-built layered architecture (L0 event
source → L10 decision-quality monitor) and how the trust boundary and the
ground-truth/LLM isolation are each enforced by a test. `anvil-build-plan.md`
§13 and `docs/PHASES.md` have the original plan and the per-phase build
order it was built against.

## Docs

- `docs/ARCHITECTURE.md` — the layered pipeline, the trust boundary, and how each is enforced
- `docs/PHASES.md` — the phase-by-phase build plan and gates
- `docs/EPISODE-SPEC.md` — committed before the generator, frozen after
- `docs/OUTCOME-MODEL.md` — every recovery-economics assumption, named and sourced
- `docs/NON-GOALS.md` — what was deliberately not built, and why
- `docs/POLICY.md` — policy engine gates, guardrails, stopping rules (Phase 6)
- `docs/RESULTS.md` — generated scorecard, held-out set (Phase 13)
- `docs/SENSITIVITY.md` — generated sensitivity sweep, held-out set (Phase 13)
- `docs/JOURNAL.md` — what broke, what we did, as it happens
