# Policy Engine — gates, guardrails, stopping rules, escalation

L5, the trust boundary. Every money action (RETRY, REROUTE, HOLD,
ESCALATE_HUMAN) passes through `src/policy/engine.py::decide()` — no other
module executes one. See CLAUDE.md rule #6.

```
payment + incident context
   |
[1] ELIGIBILITY GATES  -- hard, deterministic, fail-closed
   |
[2] EXPECTED VALUE     -- only for actions that survived [1]
   |
[3] GUARDRAILS          -- override EV, never the reverse
   |
[4] DECISION + rationale -> Recovery Ledger
```

Implementation: `src/policy/gates.py`, `src/policy/expected_value.py`,
`src/policy/guardrails.py`, orchestrated by `src/policy/engine.py`.

---

## [1] Eligibility gates

Fail-closed: any check that cannot be positively confirmed makes the
action ineligible. Never the reverse.

**RETRY**
- `attempt_number < max_retries(method)` — see `MAX_RETRIES_BY_METHOD` in
  `src/policy/config.py` (upi/wallet: 2, card: 2, netbanking/emi: 1)
- not already captured (duplicate-payment guard)
- within the retry window (`RETRY_WINDOW_SECONDS`, 30 minutes)
- idempotency key unused

**REROUTE**
- method supports reroute (`upi`, `card`, `wallet` — not `netbanking`/`emi`,
  which are tied to a specific bank/mandate rather than a switchable PSP)
- not already captured
- an alternate PSP is healthy
- idempotency key unused

**HOLD** and **ESCALATE_HUMAN** are always eligible — the fail-safe
defaults when nothing else is.

## [2] Expected value

Computed only for eligible RETRY/REROUTE. See `docs/OUTCOME-MODEL.md` §4
for the formula and every parameter's basis:

```
EV(retry)   = p_retry_success   x amount - cost_retry
EV(reroute) = p_reroute_success x amount - cost_reroute
EV(hold)    = 0
```

The higher-EV eligible action becomes the *candidate* decision — subject
to guardrails below, which can still override it.

## [3] Guardrails

Deterministic, and they win over EV every time.

| Condition | Outcome |
|---|---|
| `amount > ₹50,000` | ESCALATE_HUMAN |
| `root_cause_confidence < 0.80` | ESCALATE_HUMAN |
| mandate/autopay debit | ESCALATE_HUMAN |
| no eligible automated action (RETRY and REROUTE both ineligible) | ESCALATE_HUMAN |
| `incident_state == SEVERE` and candidate action is RETRY | HOLD |
| merchant's hourly recovery budget spent | HOLD |
| cooldown active on this `payment_id` | HOLD |

The fourth ESCALATE_HUMAN condition ("no eligible automated action") is
not in `anvil-build-plan.md`'s original three-item guardrail bullet list
— it's a deliberate addition made while building this phase, so that
`docs/PHASES.md`'s Phase 6 gate ("escalation triggers on all four
documented conditions") has four real, distinct, testable triggers rather
than three. See `docs/JOURNAL.md`.

Escalation guardrails are checked before HOLD guardrails: if any
escalation condition fires, the decision is ESCALATE_HUMAN regardless of
whether a HOLD condition also fires.

## Stopping rules

- **Max retries** — the RETRY eligibility gate (`attempt_number <
  max_retries(method)`).
- **Cooldown** — the cooldown-active HOLD guardrail.
- **Circuit-break on SEVERE** — the SEVERE-state HOLD guardrail: no retry
  is issued against a dependency the incident state machine has already
  classified as severely degraded, regardless of how favorable the naive
  EV calculation looks. This is the guardrail directly answering the
  scenario named in `anvil-build-plan.md` §15 as the strongest possible
  journal entry — several hundred retries hammering an already-down bank
  — by making it structurally impossible for RETRY to survive guardrails
  while the incident is SEVERE.

## Idempotency

Both RETRY and REROUTE gates require `idempotency_key not in
idempotency_keys_used`. The set of used keys is passed into
`PolicyContext` explicitly rather than looked up by the policy engine
itself — Phase 7 wires this to the real Recovery Ledger. See
`tests/test_idempotency.py`.
