# Non-Goals — what we cut, and why

Razorpay's rubric names "AI judgment — the right tool in the right place,
and where you chose not to use one." This document is the direct answer.

| Not used | Why not |
|---|---|
| Kafka | Zero infra needed at ~100k events; a message queue is ceremony without a second consumer |
| Redis | No shared mutable cache required; DuckDB-over-Parquet already serves rollups in milliseconds |
| Postgres | Parquet + DuckDB gives single-file storage, zero-ops, and fast analytical rollups without running a database server |
| Kubernetes | One FastAPI service and one static frontend; a Docker Compose file is the honest amount of orchestration |
| Bandit / RL policy | The policy engine's job is bounded, auditable, deterministic decisions with hard guardrails — an RL policy trades that auditability for marginal EV gains this project does not need, and cannot produce a gate-by-gate rationale for a ledger entry |
| RAG | Nothing in this system requires retrieval over a document corpus; the LLM layer (L9) only normalises error text and narrates an already-computed incident, both of which fit in a single prompt with no retrieval step |
| Custom route-scoring model | Building a competing router duplicates Vulcan and is explicitly out of scope per the positioning in `anvil-build-plan.md` — Anvil tests routing decisions, it does not make them. The `RoutingOracle` protocol exists precisely so no such model needs to be built here |
| `ruptures` / changepoint libraries | CUSUM is ~40 lines that can be defended line-by-line in a panel; defending a library's internals you didn't write is a worse position for a hackathon submission |

## Things that are deliberately out of scope, not just unused tools

- **Subscription recovery, dispute response, cart recovery** — Razorpay's
  own Agent Studio shipped all three in March; building any of them here
  competes with a product Razorpay already sells, not with a gap in it.
- **A fraud detector.** Anvil detects performance degradation, not
  fraudulent behavior. These are different signal classes and conflating
  them would blur the product's positioning.
- **Live Vulcan integration.** There is no public Vulcan API. `VulcanOracle`
  in `src/quality/` is a documented stub implementing the `RoutingOracle`
  protocol, and nothing more — see `anvil-build-plan.md` §6.
