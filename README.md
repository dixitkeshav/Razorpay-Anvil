# Anvil

**Razorpay AI Buildathon · Track 03 (AI Revenue Recovery)**

> Razorpay's Vulcan makes millions of routing decisions a day. Anvil watches
> the ground underneath them — detecting when payment performance degrades,
> attributing the failure to a specific slice of the network, executing a
> bounded recovery, and proving in rupees how much of that revenue came back.

Anvil is not a routing model, a fraud detector, or a subscription-recovery
agent.

## What it does

- **Detects** revenue at risk — a CUSUM detector on success rate and an
  EWMA detector on P95 latency, walked hierarchically across a
  method/PSP/issuer/region slice lattice.
- **Attributes** each detected incident to the specific slice responsible.
- **Decides** a bounded action (retry, reroute, hold, or escalate to a
  human) through a single policy engine — eligibility gates, then expected
  value, then guardrails that always win over the EV math.
- **Executes** it for real, against Razorpay's test-mode API, with
  idempotency so a replay never double-charges.
- **Measures** net rupees recovered via a counterfactual replay
  (agent-on vs. a do-nothing baseline) on a held-out set the detector was
  never tuned against.
- **Records** every action, with its rationale, in an append-only Recovery
  Ledger — browsable in the dashboard and queryable over MCP.
- **Answers questions** about what it found — an "Ask Anvil" chat panel
  that explains detected incidents in plain language, strictly grounded in
  the same ledger/incident data, with no path back into the decision
  engine.

All generated evaluation numbers (recall, recovery, sensitivity) come only
from running the code below — never hand-typed.

## Quickstart

```bash
make install
make reproduce
```

Reproduces the full held-out evaluation from a clean clone, no credentials
required.

```bash
cp .env.example .env   # optional — Razorpay test-mode keys + Groq key
make install
make test
```

Runs the full test suite (two tests need real Razorpay test-mode
credentials and skip cleanly without them).

## Dashboard

```bash
docker compose up --build
```

Dashboard at `http://localhost:5173`, API at `http://localhost:8000`.
Click into any incident for the attribution trace, affected merchants, and
Recovery Ledger, or use the "Ask Anvil" chat panel.

The same incident data is available over MCP for Claude Desktop, Claude
Code, or any other MCP client:

```bash
.venv/bin/python -m src.mcp.server
```
