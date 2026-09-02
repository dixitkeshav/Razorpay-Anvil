import Shell from "../components/Shell";
import { Card, CardHeader } from "../components/ui";

/**
 * Static mirror of src/policy/config.py — the policy engine's own
 * constants. Not sourced from the API (there's no /policies endpoint);
 * kept in sync by hand since these are code-level config, not eval output.
 */
const GUARDRAILS = [
  { label: "Amount escalation threshold", value: "Rs. 50,000", note: "Above this, ESCALATE_HUMAN — no automated retry/reroute." },
  { label: "Root-cause confidence threshold", value: "0.80", note: "Below this, ESCALATE_HUMAN regardless of expected value." },
  { label: "Merchant hourly recovery budget", value: "Rs. 2,00,000 / hour", note: "Per-merchant cap; further actions HOLD once spent." },
  { label: "Retry window", value: "30 minutes", note: "An attempt older than this is no longer eligible for retry." },
];

const RETRY_LIMITS = [
  { method: "UPI", max: 2 },
  { method: "Card", max: 2 },
  { method: "Netbanking", max: 1 },
  { method: "Wallet", max: 2 },
  { method: "EMI", max: 1 },
];

const OUTCOME_MODEL = [
  { label: "P(retry success)", value: "0.45" },
  { label: "P(reroute success)", value: "0.65" },
  { label: "Retry cost", value: "Rs. 0" },
  { label: "Reroute cost", value: "Rs. 50" },
];

export default function Policies() {
  return (
    <Shell title="Policies & Guardrails" subtitle="Decision boundaries enforced by the policy engine (src/policy)">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Guardrails" />
          <div className="divide-y divide-anvil-border">
            {GUARDRAILS.map((g) => (
              <div key={g.label} className="flex items-start justify-between gap-4 px-6 py-4">
                <div>
                  <p className="text-sm font-medium text-anvil-ink">{g.label}</p>
                  <p className="mt-0.5 text-xs text-anvil-ink-muted">{g.note}</p>
                </div>
                <span className="whitespace-nowrap text-sm font-semibold text-anvil-ink">{g.value}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Retry limits by method" />
          <div className="divide-y divide-anvil-border">
            {RETRY_LIMITS.map((r) => (
              <div key={r.method} className="flex items-center justify-between px-6 py-3.5">
                <span className="text-sm font-medium text-anvil-ink">{r.method}</span>
                <span className="text-sm text-anvil-ink-soft">{r.max} max retries</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Outcome model (expected-value inputs)" />
          <div className="grid grid-cols-2 gap-6 px-6 py-5 md:grid-cols-4">
            {OUTCOME_MODEL.map((o) => (
              <div key={o.label}>
                <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">{o.label}</p>
                <p className="mt-1 text-lg font-semibold text-anvil-ink">{o.value}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Shell>
  );
}
