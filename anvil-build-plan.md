# Anvil — Build Plan
**Razorpay AI Buildathon · Track 03 (AI Revenue Recovery)**
Applications close 5 September 2026

> *Vulcan decides. Anvil is where those decisions get tested.*

Rename freely, but keep the rhyme with Vulcan — it signals to the panel that you read their launch from 18 August and built for the world it created.

---

## 1. Positioning

**One sentence, to open the video:**

> Razorpay's Vulcan makes millions of routing decisions a day. Anvil watches the ground underneath them — detecting when payment performance degrades, attributing the failure to a specific slice of the network, executing a bounded recovery, and proving in rupees how much of that revenue came back.

**Elevator version for the form's "what it solves":**

> When a bank's UPI handle degrades at 21:04, merchants find out from customer complaints forty minutes later. Anvil detects it in under three minutes, names the failing slice, recovers what it can within hard limits, and produces an auditable record of every rupee it moved and every action it declined to take.

**What Anvil is not:** it does not score routes, predict fraud, or compete with Vulcan. It is the incident, recovery and accountability layer *above* a model-driven payments network — the thing a company that just bet its stack on a 3,000-signal black box does not yet have.

---

## 2. The Track 03 bar — the mandatory floor

Track 03 says: *"Build an agent that detects revenue at risk, determines the right intervention, and executes a bounded recovery workflow… Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail."*

Seven requirements. Every one gets its own visible artifact and its own README row.

| # | Bar requirement | Anvil deliverable | Evidence |
|---|---|---|---|
| 1 | Detects revenue at risk | CUSUM detector on success rate + EWMA on P95 latency | `docs/RESULTS.md` — recall, time-to-detect |
| 2 | Determines the right intervention | Policy engine: eligibility → expected value → guardrails | Per-action rationale in ledger |
| 3 | Executes a bounded recovery workflow | Razorpay test-mode execution with idempotency | Live in demo video |
| 4 | **Measured money recovered across a batch** | Counterfactual replay, agent-on vs agent-off | ₹ incremental over N interventions |
| 5 | **Compliant escalation** | Amount thresholds, low-confidence escalation, mandate rules | Escalation count + reasons |
| 6 | **Stopping rules** | Max retries, cooldowns, circuit-break on SEVERE state | `docs/POLICY.md` + tests |
| 7 | **Audit trail** | Append-only Recovery Ledger, every action traceable | Exportable, shown in UI |

**Put a section in the README titled exactly `## How this meets the Track 03 bar` containing this table.** A reviewer scanning fifty repos finds it in ten seconds.

---

## 3. Floor before USP — the ordering rule

The build splits cleanly:

**FLOOR (Phases 0–8)** — a complete, defensible Track 03 submission on its own. If everything after Phase 8 fell over, you could still submit and score well.

**USP (Phases 9–12)** — the layer that makes you memorable: LLM explanation with injection defense, decision-quality monitoring, MCP server, dashboard.

The USP is more interesting than the floor and will pull your attention. Resist it. **Do not begin Phase 9 until `make eval` emits a complete scorecard with a real rupee figure in it.** A submission with a brilliant calibration monitor and no measured recovery fails Track 03 on its stated terms.

---

## 4. What Anvil is: a service with two faces

```
                    ┌──────────────────────────────────────┐
                    │      ANVIL CORE SERVICE (FastAPI)    │
                    │                                      │
                    │  ingest → detect → attribute →       │
                    │  impact → decide → execute → ledger  │
                    └───────┬──────────────────────┬───────┘
                            │                      │
              ┌─────────────▼──────┐    ┌──────────▼─────────────┐
              │  React Dashboard   │    │  Anvil MCP Server      │
              │  humans watch      │    │  agents query          │
              │  incidents & money │    │  get_incident,         │
              │                    │    │  explain_attribution,  │
              │                    │    │  query_ledger          │
              └────────────────────┘    └────────────────────────┘
                                                   │
                                        ┌──────────▼─────────────┐
                                        │ Razorpay MCP Server    │
                                        │ (official) — execution │
                                        └────────────────────────┘
```

Two faces on one core is the whole point:
- The **dashboard** makes it demoable to a panel.
- The **MCP server** makes it integrable — an Agent Studio–style agent could consume Anvil tomorrow, over the same protocol Razorpay already publishes their own server on.

Logic lives in the service. The dashboard is a thin client. If you spend more than a fifth of your time on the frontend, stop.

---

## 5. Layered architecture

```
L0  EVENT SOURCE
    synthetic generator (Razorpay-shaped)  │  razorpay test-mode adapter
    → Parquet
─────────────────────────────────────────────────────────────
L1  AGGREGATION — DuckDB
    1-min buckets × slice lattice
    attempts, successes, SR, P50/P95/P99, timeout_rate, retry_rate
─────────────────────────────────────────────────────────────
L2  DETECTION — no LLM
    CUSUM on SR · EWMA on P95 latency
    hierarchical sequential testing, Benjamini–Hochberg per level
─────────────────────────────────────────────────────────────
L3  ATTRIBUTION — no LLM
    contribution decomposition over the lattice
    minimal explanatory cut covering ≥X% of the aggregate delta
─────────────────────────────────────────────────────────────
L4  IMPACT — no LLM
    affected attempts · at-risk GMV · per-merchant breakdown
─────────────────────────────────────────────────────────────
L5  POLICY ENGINE — no LLM · THE TRUST BOUNDARY
    eligibility gates → EV ranking → guardrails → decision
─────────────────────────────────────────────────────────────
L6  EXECUTION
    Razorpay test-mode (subset) │ outcome simulator (batch)
    idempotency keys · duplicate-payment guard
─────────────────────────────────────────────────────────────
L7  RECOVERY LEDGER — append-only, immutable
─────────────────────────────────────────────────────────────
L8  EVALUATION
    counterfactual replay · sensitivity sweep · scorecard · failure taxonomy
─────────────────────────────────────────────────────────────
L9  EXPLANATION — LLM, read-only, terminal
    error normalisation · incident narrative · investigation Q&A
    CANNOT write to L5. Enforced by import test.
─────────────────────────────────────────────────────────────
L10 DECISION-QUALITY MONITOR — the USP
    realised SR vs routing-oracle implied confidence, per slice
```

**The architectural claim to land in the video:** the LLM sits at L9, downstream of every money decision. It describes; it cannot cause. There is a test that proves the policy module has no import path to the LLM module. A passing test beats a paragraph.

---

## 6. The signature feature: decision-quality monitoring (L10)

This is what separates Anvil from every other Track 03 submission, and it exists only because Vulcan launched last week.

Your routing oracle emits a confidence score per route. Anvil tracks **realised outcome against implied confidence, per slice, over time**:

```
HDFC × UPI × PSP-A
  routes scored at mean confidence 0.91
  realised success rate 0.62 over 340 attempts
  calibration gap −0.29, sustained 14 min
  → MODEL-DRIFT INCIDENT
     the oracle's priors are stale for this slice;
     it will keep routing here confidently until retrained
```

This is a different class of incident from a bank outage. A bank outage is visible in raw success rate. Calibration drift is visible *only* if you compare the model's own confidence against reality — and nobody is doing that.

**The `RoutingOracle` interface.** You cannot call Vulcan; there is no public API. Do not pretend otherwise. Instead:

```python
class RoutingOracle(Protocol):
    def score_routes(self, ctx: PaymentContext) -> list[RouteScore]: ...

class SimulatedOracle(RoutingOracle):   # ships with the repo
class VulcanOracle(RoutingOracle):      # stub + docstring only
```

Then in the README: *"Anvil is model-agnostic by design. Swapping the simulated oracle for a production routing model is one adapter class; nothing above L1 changes."* That is an honest senior-engineer answer and an invitation to a conversation, rather than an unverifiable claim.

---

## 7. Event schema — Razorpay-shaped, non-negotiable

```python
class PaymentAttempt(BaseModel):
    # Razorpay payment-object aligned
    id: str                       # "pay_XXXXXXXXXXXX"
    order_id: str                 # "order_XXXXXXXXXXXX"
    entity: Literal["payment"] = "payment"
    amount: int                   # paise
    currency: str = "INR"
    status: Literal["created","authorized","captured","failed","refunded"]
    method: Literal["upi","card","netbanking","wallet","emi"]
    bank: str | None
    wallet: str | None
    vpa: str | None
    card_id: str | None
    international: bool = False
    captured: bool
    description: str | None       # ← UNTRUSTED. injection vector.
    error_code: str | None
    error_description: str | None
    error_source: str | None      # customer | business | bank | gateway
    error_step: str | None
    error_reason: str | None
    created_at: int

    # ops extensions — namespaced so the boundary is obvious
    x_psp: str
    x_issuer: str
    x_bin: str | None
    x_attempt_number: int
    x_latency_ms: int
    x_region: str
    x_merchant_id: str
    x_merchant_category: str
    x_route_confidence: float     # what the oracle believed
    x_episode_id: str | None      # GROUND TRUTH — never read downstream
```

`error_source` and `error_step` mirror Razorpay's real error object. Use their actual error code vocabulary (`BAD_REQUEST_ERROR`, `GATEWAY_ERROR`, and the payment failure reasons) — a reviewer who works there will recognise them instantly.

### Slice lattice

Dimensions: `method × psp × issuer × region × merchant_category`

Never test the cross-product. Test hierarchically, drilling into a child only when the parent fires:

```
L0  overall
 └ L1  method
    └ L2  method × psp
       └ L3  method × psp × issuer
          └ L4  + region  /  + merchant_id
```

Benjamini–Hochberg applied *within each level*, with that level's test count as the denominator. Total tests stay in the tens. Bonferroni across the full lattice would destroy your power and you would detect nothing — this is a real failure mode worth writing about in the journal.

---

## 8. Policy engine (L5)

```
payment + incident context
   ↓
[1] ELIGIBILITY GATES — hard, deterministic, fail-closed
    · attempt_number < max_retries(method)
    · not already captured        ← duplicate-payment guard
    · within retry window
    · idempotency key unused
    · alternate PSP healthy       ← for REROUTE
    · method supports the action
   ↓
[2] EXPECTED VALUE per surviving action
    EV(a) = P(success | a, context) × amount − cost(a)
   ↓
[3] GUARDRAILS — override EV, deterministic  [BAR ITEMS 5 & 6]
    · amount > ₹50,000                    → ESCALATE_HUMAN
    · root-cause confidence < 0.80        → ESCALATE_HUMAN
    · incident state == SEVERE and RETRY  → HOLD   (don't hammer a downed bank)
    · per-merchant hourly budget spent    → HOLD
    · cooldown active on payment_id       → HOLD
    · mandate/autopay debit limits        → ESCALATE_HUMAN
   ↓
[4] DECISION + rationale → Recovery Ledger  [BAR ITEM 7]
```

Every gate result is logged and rendered in the UI. That is your bounded-and-gated evidence, and it is three of the seven bar items in one component.

### Incident state machine

```
NORMAL → WATCH → DEGRADED → SEVERE → RECOVERING → NORMAL
```

State gates which actions are permitted. SEVERE disables RETRY entirely. Cheap to build, and it converts "we detected an anomaly" into "we have operational intelligence."

---

## 9. Evaluation methodology — the part that earns trust

### 9.1 The circularity protocol

You author the degradations and then detect them. Untreated, this invalidates every number.

1. Write `docs/EPISODE-SPEC.md` **first**. Commit it. The git timestamp is your evidence.
2. Build the generator to that spec. Commit. **Never touch it again once the detector exists.**
3. Build the detector against emitted events only — never generator internals.
4. Add a lint test: no module under `src/detection/`, `src/attribution/` or `src/policy/` may reference `x_episode_id`.
5. Generate a **held-out set at Phase 13** with fresh seeds and redrawn parameters. Headline metrics come from the held-out set only.
6. Stratify by difficulty and report recall per tier:

| Tier | Definition |
|---|---|
| Easy | SR drop > 20pp, high-volume slice |
| Medium | SR drop 8–20pp, medium volume |
| Hard | SR drop 3–8pp, low-volume slice, or confounded by a concurrent volume spike |

7. Include **decoys** — volume spikes, diurnal troughs, merchant onboarding ramps that look like degradation but aren't. False alarms on decoys are the most informative number in the project.
8. README section: **"What this evaluation cannot tell you."** Naming your own ceiling is what makes everything else believable.

### 9.2 Episode types to inject

| Episode | Shape | What it tests |
|---|---|---|
| A — Bank degradation | HDFC × UPI, SR 94→68% over 40 min | basic detection |
| B — PSP timeout | PSP-A, all banks, P95 800ms→4.8s, SR barely moves | latency leading indicator |
| C — Card BIN issue | BIN 523xxx, SR 92→41% | deep-lattice attribution |
| D — Regional | Rajasthan × UPI × PSP-B, SR 93→72% | low-volume slice sensitivity |
| E — Merchant-specific | M492 × cards, SR 91→54% | merchant-dimension drill-down |
| F — Calibration drift | SR stable but oracle confidence 0.91 vs realised 0.62 | **L10 only — invisible to every other detector** |
| G — Two concurrent causes | A and C overlapping | attribution honesty; expect failures |

Episode F is the one that justifies the USP. Episode G is the one you will fail on and should write about.

### 9.3 The outcome model, and why it needs a sensitivity sweep

"₹6.7L incremental" is a function of your assumed `P(success | retry, context)`. If that assumption is arbitrary, the number is theatre.

- Name every parameter in `docs/OUTCOME-MODEL.md`, with its basis. Mark clearly which are grounded in public payment-industry figures and which are your own reasoned estimates.
- Sweep the grid: retry success ∈ {0.35, 0.45, 0.55, 0.65} × reroute success ∈ {0.50, 0.60, 0.70, 0.80} × reroute cost ∈ {₹20, ₹50, ₹100}.
- Emit a heatmap of net incremental recovery. **Mark the region where Anvil loses money.**

Headline claim becomes: *"Net incremental recovery is positive in 41 of 48 parameter settings; it turns negative when reroute success falls below 0.55 with cost above ₹80."*

Almost nobody at any level does this. It is the single highest-leverage afternoon in the build.

---

## 10. Tech stack

| Layer | Choice | Why, and why not the obvious alternative |
|---|---|---|
| Language | Python 3.11 | ecosystem for the statistics; speed irrelevant at 100k events |
| Event store | **Parquet + DuckDB** | single file, zero infra, ms rollups. Postgres = ceremony. Kafka = a lie about scale |
| Dataframes | Polars | fast, lazy API keeps aggregation readable |
| Detection | numpy/scipy, **hand-rolled CUSUM** | ~40 lines you can defend line-by-line in a panel. `ruptures` means defending code you didn't write |
| Multiple testing | `statsmodels.stats.multitest` (BH) | standard, boring, correct |
| Backend | FastAPI + Pydantic v2 | schema validation doubles as the LLM output guard |
| Frontend | React 18 + Vite + Tailwind + Recharts | Streamlit signals "notebook"; a real dashboard signals "product" |
| LLM | Claude Haiku 4.5 via Anthropic API | cheap, fast, sufficient for normalisation + narration |
| LLM caching | `fixtures/llm_cache.json`, committed | **repo runs offline and reproducibly; demo survives an API outage** |
| Agent framing | Claude Agent SDK | the same SDK Agent Studio is built on — you're on their stack |
| Payments | official `razorpay` Python SDK, test mode | orders, payments, refunds, payment links |
| Agent surface | **Razorpay MCP Server** (official) for execution; **your own MCP server** for incident queries | demonstrates both directions of integration |
| Tests | pytest + ruff | including the architectural tests below |
| Packaging | Docker Compose (api, web) + Makefile | `make reproduce` regenerates every number in the README |

**Explicitly not used, and say so in `docs/NON-GOALS.md`:** Kafka, Redis, Postgres, Kubernetes, a bandit/RL policy, RAG, a custom route-scoring model. Each with a one-line reason. Razorpay's rubric names *"AI judgment — the right tool in the right place, and where you chose not to use one."* This document is a direct answer to that criterion.

### Makefile

```
make seed        # generate the frozen episode set
make holdout     # generate held-out set — run ONCE, at Phase 13
make run         # docker compose up
make eval        # full replay + scorecard → docs/RESULTS.md
make sweep       # sensitivity grid → docs/SENSITIVITY.md
make reproduce   # seed + eval + sweep, deterministic
make test
make test-phase-N
```

---

## 11. Phased build with test gates

Each phase ends in a machine-checkable gate. This is what lets an agent run unattended between your check-ins: the gate is the definition of done, so the agent can iterate without you.

### FLOOR

| Phase | Goal | Gate — `make test-phase-N` passes when |
|---|---|---|
| **0** | Scaffold: repo, Docker, Makefile, `CLAUDE.md`, `EPISODE-SPEC.md`, `OUTCOME-MODEL.md`, Razorpay test-mode keys | A test creates a real test-mode order via the Razorpay SDK and asserts a valid `order_id`. **Do this on day one — auth friction is the classic day-eater.** |
| **1** | Event generator: base traffic, diurnal curve, 7 episode types, decoys, difficulty tiers | `make seed` emits ≥100k events; every injected episode is recoverable from ground truth; schema validates |
| **2** | DuckDB ingestion + slice-lattice rollups | Query returns SR/P95/timeout-rate for any slice × minute; matches a hand-computed fixture |
| **3** | CUSUM on SR + EWMA on P95 + hierarchical BH | Detects all easy-tier episodes; fires at ≤2 false alarms/day on a clean stretch; **passes the no-ground-truth lint test** |
| **4** | Attribution: contribution decomposition, minimal explanatory cut | Names the correct slice on episodes A, C, D, E; reports over-broad rather than wrong on G |
| **5** | Impact estimator + incident state machine | Affected-attempt count within 5% of truth; state transitions follow the documented FSM |
| **6** | Policy engine: gates, EV, guardrails, stopping rules, escalation | Every gate has a passing unit test; no action can bypass `[3]`; escalation triggers on all four documented conditions |
| **7** | Execution (Razorpay test-mode + simulator) + Recovery Ledger | Ledger is append-only; replaying the same idempotency key does not double-charge; ≥1 real test-mode recovery completes |
| **8** | Counterfactual replay + scorecard | `make eval` emits `docs/RESULTS.md` with a real ₹ figure, agent-on vs agent-off, from the same seed |

> **⛔ FLOOR COMPLETE. A valid Track 03 submission exists at this point.** Verify `make eval` output before proceeding. If the schedule collapses, you stop here and still submit.

### USP

| Phase | Goal | Gate |
|---|---|---|
| **9** | LLM layer: error normalisation, incident narrative, response cache, injection defense | `test_llm_cannot_reach_policy.py` passes; injection fixture produces inert narrative + unchanged ledger; **full suite passes with network disabled** |
| **10** | Decision-quality monitor (L10) | Detects episode F, which every L2 detector misses; calibration gap reported per slice |
| **11** | Anvil MCP server: `get_incident`, `explain_attribution`, `query_recovery_ledger` | Claude Desktop or Claude Code connects and successfully calls all three tools |
| **12** | Dashboard: Ops overview + Incident detail with failure analysis embedded | Loads from a clean `docker compose up`; renders a full incident end to end |

> **⛔ FEATURE FREEZE after Phase 12.** Nothing new gets added after this line.

### CLOSE

| Phase | Goal | Gate |
|---|---|---|
| **13** | Held-out generation, full eval, sensitivity sweep, failure taxonomy | `make holdout && make eval && make sweep` from a clean clone; every README number is generated output |
| **14** | README, ARCHITECTURE, NON-GOALS, POLICY, journal cleanup | A stranger clones and reproduces your numbers with two commands |
| **15** | Record and edit the 5-minute video; submit the form | Submitted, with a day of buffer |

---

## 12. Running this with Claude Code

Claude Code is the right tool. Headless mode (`claude -p`) runs non-interactively with scoped tools and turn caps, and the sandbox jails bash behind a filesystem and network allowlist.

Be realistic about autonomy: auto mode escalates to the human after repeated denials, and in headless mode — with no UI to ask — it terminates instead. Plan on **6–8 check-ins at phase boundaries**, not zero. Between them you can genuinely walk away.

**Per-phase invocation pattern:**

```bash
claude -p "Implement Phase 4 per docs/PHASES.md.
           Acceptance: make test-phase-4 passes.
           Do not modify src/generator/ or any file under docs/.
           Stop and report if the gate cannot be met." \
  --allowedTools "Read,Edit,Write,Bash(make:*),Bash(pytest:*),Bash(git:*)" \
  --max-turns 60 \
  --output-format json
```

Commit at every phase boundary so you can roll back a phase that went sideways.

**The rule that matters most:** never let the agent write your evaluation numbers. If Claude Code produces both the detector and the results table, you get plausible, fabricated, indefensible metrics — and you will be asked, in a panel, how you got them. Every figure in the README must be emitted by `make eval`. This goes in `CLAUDE.md` as a hard constraint.

---

## 13. Repo structure

```
anvil/
├── README.md                    ← scorecard, bar mapping, limitations, quickstart
├── CLAUDE.md                    ← agent operating rules
├── Makefile
├── docker-compose.yml
├── docs/
│   ├── EPISODE-SPEC.md          ← committed Phase 0, before any detector
│   ├── OUTCOME-MODEL.md         ← every assumption named and sourced
│   ├── PHASES.md                ← the table from §11, with acceptance criteria
│   ├── ARCHITECTURE.md
│   ├── POLICY.md                ← gates, guardrails, stopping rules, escalation
│   ├── NON-GOALS.md             ← what you cut and why
│   ├── RESULTS.md               ← GENERATED
│   ├── SENSITIVITY.md           ← GENERATED
│   └── JOURNAL.md               ← daily; see §15
├── src/
│   ├── generator/               # L0
│   ├── ingest/                  # L1
│   ├── detection/               # L2   ⟵ may not import llm/
│   ├── attribution/             # L3   ⟵ may not import llm/
│   ├── impact/                  # L4
│   ├── policy/                  # L5   ⟵ may not import llm/
│   ├── execution/               # L6   razorpay_adapter.py, simulator.py
│   ├── ledger/                  # L7
│   ├── evaluation/              # L8
│   ├── llm/                     # L9   ⟵ imports nothing above it
│   ├── quality/                 # L10  decision-quality monitor
│   ├── mcp/                     # Anvil MCP server
│   └── api/
├── web/
├── fixtures/llm_cache.json
└── tests/
    ├── test_detector_ignores_ground_truth.py
    ├── test_llm_cannot_reach_policy.py
    ├── test_policy_gates.py
    ├── test_stopping_rules.py
    ├── test_escalation_thresholds.py
    ├── test_injection_defense.py
    ├── test_idempotency.py
    └── test_ledger_append_only.py
```

---

## 14. Video outline — five minutes

| Time | Content |
|---|---|
| 0:00–0:25 | The problem, concretely. A bank's UPI handle degrades at 21:04; merchants learn about it from complaints forty minutes later. |
| 0:25–0:45 | The positioning line. Vulcan decides; Anvil tests those decisions. |
| 0:45–2:15 | **Live incident walkthrough.** Screen recording, no slides. SR drops → detector fires at +2min → attribution names the slice → impact by merchant → policy engine picks actions with gate results visible → ledger fills → recovery measured. |
| 2:15–2:50 | Architecture, one diagram. The LLM is at L9, downstream, read-only — and here's the test that enforces it. Name what you chose *not* to build and why. |
| 2:50–3:15 | Episode F: the calibration-drift incident that no success-rate detector can see. This is the moment they remember. |
| 3:15–3:30 | Injection attempt blocked, ledger unchanged. |
| 3:30–4:20 | **The scorecard — including the misses.** Sensitivity heatmap. Point at the region where Anvil loses money. |
| 4:20–5:00 | What broke and how you got out. |

---

## 15. The form question that decides this

> *"What broke, and how you got out"* — and the page says **"The last one is the one we read first."**

Start `docs/JOURNAL.md` at Phase 0. Two lines a day: what broke, what you did. You will end up with real entries instead of a manufactured anecdote, and the difference is obvious to anyone who has debugged anything.

The strongest answer is not a heroic recovery — it's a specific bug traced to a specific wrong assumption. Likely candidates from this build:

- Bonferroni across the full lattice killed detection power to near zero; the fix was realising you were correcting across the wrong test family, and moving to per-level BH.
- The detector reported suspiciously perfect recall because `x_episode_id` leaked through a join — caught by the lint test you'd written for exactly this reason.
- The SEVERE-state guardrail didn't fire, and several hundred retries hammered a bank that was already down. Visible in your own failure taxonomy.

That last one is real, it will be in your scorecard, and it is the best answer of the three.

---

## 16. Risks

| Risk | Mitigation |
|---|---|
| USP work starts before the floor is done | Phase 8 gate is a hard stop. `make eval` must emit a ₹ figure first. |
| Razorpay test-mode auth friction | Phase 0 gate is a real test-mode `order.create`. Day one. |
| Detector tuned against known ground truth | Held-out set at Phase 13 with fresh seeds; lint test blocks ground-truth reads. |
| Agent fabricates evaluation numbers | `CLAUDE.md` hard rule; all figures are generated output, committed. |
| Numbers you cannot regenerate | `make reproduce` from a clean clone at Phase 14. If it doesn't run, the number doesn't ship. |
| LLM API down during the demo | Response cache committed; full suite passes with network disabled. |
| Video recorded at 2am the night before | Record a rough cut at Phase 12 even if incomplete. You will need two takes. |
| Building something Razorpay already sells | Do not build subscription recovery, dispute response, or cart recovery — Agent Studio shipped all three in March. |
