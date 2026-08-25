# Anvil

**Razorpay AI Buildathon · Track 03 (AI Revenue Recovery)**

> Razorpay's Vulcan makes millions of routing decisions a day. Anvil watches
> the ground underneath them — detecting when payment performance degrades,
> attributing the failure to a specific slice of the network, executing a
> bounded recovery, and proving in rupees how much of that revenue came back.

Anvil is not a routing model, a fraud detector, or a subscription-recovery
agent. See `docs/NON-GOALS.md` for the full list of what this deliberately
is not, and why.

Build status: **Held-out evaluation complete (Phase 13).** `docs/RESULTS.md`
and `docs/SENSITIVITY.md` are generated from a held-out set — fresh seed,
redrawn episode timing, never used to tune the detector or attribution —
via `make holdout && make eval && make sweep`. Feature freeze has been in
effect since Phase 12; Phases 14-15 (docs polish, submission) are next.

---

## How this meets the Track 03 bar

| # | Bar requirement | Anvil deliverable | Evidence |
|---|---|---|---|
| 1 | Detects revenue at risk | CUSUM detector on success rate + EWMA on P95 latency | `docs/RESULTS.md` — recall, time-to-detect |
| 2 | Determines the right intervention | Policy engine: eligibility → expected value → guardrails | Per-action rationale in ledger |
| 3 | Executes a bounded recovery workflow | Razorpay test-mode execution with idempotency | Live in demo video |
| 4 | Measured money recovered across a batch | Counterfactual replay, agent-on vs agent-off | ₹ incremental over N interventions |
| 5 | Compliant escalation | Amount thresholds, low-confidence escalation, mandate rules | Escalation count + reasons |
| 6 | Stopping rules | Max retries, cooldowns, circuit-break on SEVERE state | `docs/POLICY.md` + tests |
| 7 | Audit trail | Append-only Recovery Ledger, every action traceable | Exportable, shown in UI |

Every row in the "Evidence" column above is generated output once the
relevant phase lands — nothing in this table is a result, only a mapping
from requirement to where the evidence will live.

---

## Quickstart

```bash
cp .env.example .env   # fill in Razorpay test-mode keys + Groq key
make install
make test               # full suite, all phase gates through Phase 13
make holdout             # writes data/holdout/ (the held-out set, generated once)
make eval                # regenerates docs/RESULTS.md from the held-out set
make sweep                # regenerates docs/SENSITIVITY.md — 48-cell parameter grid
```

`make reproduce` chains `seed`, `eval`, and `sweep` and will regenerate
every number in `docs/RESULTS.md` and `docs/SENSITIVITY.md` from a clean
clone — `eval` and `sweep` regenerate the held-out set in-memory
themselves (same seed, deterministic), so they don't strictly depend on
`make holdout` having been run first; `make holdout` exists to put the
held-out parquet files on disk for separate inspection.

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

See `anvil-build-plan.md` §13 and `docs/PHASES.md` for the full layered
architecture (L0 event source → L10 decision-quality monitor) and the
per-phase build order.

## Docs

- `docs/PHASES.md` — the phase-by-phase build plan and gates
- `docs/EPISODE-SPEC.md` — committed before the generator, frozen after
- `docs/OUTCOME-MODEL.md` — every recovery-economics assumption, named and sourced
- `docs/NON-GOALS.md` — what was deliberately not built, and why
- `docs/POLICY.md` — policy engine gates, guardrails, stopping rules (Phase 6)
- `docs/RESULTS.md` — generated scorecard (Phase 8+)
- `docs/SENSITIVITY.md` — generated sensitivity sweep (Phase 13)
- `docs/JOURNAL.md` — what broke, what we did, as it happens
