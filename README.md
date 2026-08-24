# Anvil

**Razorpay AI Buildathon · Track 03 (AI Revenue Recovery)**

> Razorpay's Vulcan makes millions of routing decisions a day. Anvil watches
> the ground underneath them — detecting when payment performance degrades,
> attributing the failure to a specific slice of the network, executing a
> bounded recovery, and proving in rupees how much of that revenue came back.

Anvil is not a routing model, a fraud detector, or a subscription-recovery
agent. See `docs/NON-GOALS.md` for the full list of what this deliberately
is not, and why.

Build status: **Phase 0 — scaffold.** See `docs/PHASES.md` for the full
15-phase plan and gates.

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
make test-phase-0      # verifies Razorpay test-mode auth works
```

Once later phases land:

```bash
make reproduce          # seed + eval + sweep, deterministic
```

will regenerate every number in `docs/RESULTS.md` and `docs/SENSITIVITY.md`
from a clean clone.

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
