# Outcome Model — every assumption named and sourced

`docs/RESULTS.md` reports a rupee figure. That figure is only as honest as
the assumptions below. Each parameter here is marked **[public]** (grounded
in a citable public payments-industry figure) or **[assumed]** (our own
reasoned estimate, to be swept in `docs/SENSITIVITY.md` rather than trusted
as a point value).

This document has no numeric results in it — only parameters and their
basis. Results live in `docs/RESULTS.md` and `docs/SENSITIVITY.md`, both
generated.

---

## 1. Action set

| Action | Definition |
|---|---|
| RETRY | Re-attempt the same payment on the same method/PSP after a backoff |
| REROUTE | Re-attempt via an alternate PSP for the same method |
| HOLD | Do nothing, log the decision, wait for state to clear |
| ESCALATE_HUMAN | Surface to an operator queue, do not act automatically |

## 2. Success-probability parameters

| Parameter | Meaning | Default | Basis | Swept range (§ sensitivity) |
|---|---|---|---|---|
| `p_retry_success` | P(success \| retry, same PSP, context) during an active incident | 0.45 | **[assumed]** — incident-time retries succeed less often than steady-state retries because the underlying cause (bank/PSP degradation) is often still active | {0.35, 0.45, 0.55, 0.65} |
| `p_reroute_success` | P(success \| reroute to healthy alternate PSP, context) | 0.65 | **[assumed]** — bounded above steady-state baseline success rate, since the alternate PSP is confirmed healthy by the eligibility gate, but below it since routing overhead and merchant-side friction remain | {0.50, 0.60, 0.70, 0.80} |
| baseline steady-state SR by method | non-incident success rate | 88–96% by method | **[assumed]**, drawn from the generator's own baseline parameters (§ `EPISODE-SPEC.md` §1) — used only as a reference point for computing incremental lift, not as an external benchmark | n/a |

## 3. Cost parameters

| Parameter | Meaning | Default | Basis | Swept range |
|---|---|---|---|---|
| `cost_retry` | Marginal cost of a retry attempt (gateway/processing fee, no success) | ₹0 | **[assumed]** — most PSPs do not charge for a failed authorization attempt; treated as negligible | not swept |
| `cost_reroute` | Marginal cost of a reroute (alternate-PSP fee differential + any switching overhead) | ₹50 | **[assumed]** — placeholder for PSP fee differentials, which vary by contract and are not public | {₹20, ₹50, ₹100} |
| `cost_escalation` | Operator time cost per escalation | not monetized | Escalations are counted, not priced — pricing operator time is out of scope and would be a separate assumption stacked on this one |

## 4. Expected value

```
EV(retry)   = p_retry_success   × amount − cost_retry
EV(reroute) = p_reroute_success × amount − cost_reroute
EV(hold)    = 0
```

The policy engine (`src/policy/`) selects the surviving action (post
eligibility gates) with the highest EV, subject to guardrails overriding EV
per `docs/POLICY.md`.

## 5. Counterfactual baseline (agent-off)

Agent-off assumes the payment attempt is not retried or rerouted by Anvil —
it follows whatever the generator's native retry behavior is (an
independent, unassisted retry rate not driven by policy), or fails
outright if the generator does not model an independent retry. This
baseline is fixed by the generator (frozen at Phase 1) and is identical for
both the agent-on and agent-off replay, so the only variable between the
two replay runs is whether Anvil's policy engine acted.

## 6. Sensitivity sweep (Phase 13, `make sweep`)

Grid: `p_retry_success ∈ {0.35, 0.45, 0.55, 0.65}` ×
`p_reroute_success ∈ {0.50, 0.60, 0.70, 0.80}` ×
`cost_reroute ∈ {₹20, ₹50, ₹100}` — 48 cells.

Output: `docs/SENSITIVITY.md`, a heatmap of net incremental recovery per
cell, with the region where net recovery goes negative marked explicitly.
No cell value in that document is hand-computed; all 48 come from
`make sweep`.

## 7. What this model does not capture

- Customer abandonment dynamics (a customer who sees a failure may not
  wait for a retry regardless of what Anvil does) — not modeled.
- Cross-payment learning (Anvil's own actions changing PSP health) — not
  modeled; each episode's health trajectory is generator-determined and
  unaffected by policy actions, which is a real limitation of the replay
  methodology, noted in `README.md` under "What this evaluation cannot
  tell you."
