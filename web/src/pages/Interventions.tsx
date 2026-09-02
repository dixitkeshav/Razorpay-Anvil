import { useEffect, useState } from "react";

import { api, LedgerEntry, paise, Scorecard } from "../api";
import Drawer from "../components/Drawer";
import Shell from "../components/Shell";
import { Badge, Card, CardHeader, EmptyState, ErrorState, Loading, MetricCard } from "../components/ui";

const ACTION_TONE: Record<string, "blue" | "success" | "warning" | "danger"> = {
  RETRY: "blue",
  REROUTE: "success",
  HOLD: "warning",
  ESCALATE_HUMAN: "danger",
};

const STATUS_TONE: Record<string, "success" | "danger" | "neutral"> = {
  success: "success",
  failed: "danger",
  not_executed: "neutral",
};

const ACTION_EXPLANATION: Record<string, string> = {
  RETRY: "Resubmits the same payment on the same rail — chosen when the policy engine's expected value favours a retry over a reroute or hold, and the retry-window and per-method retry-limit gates both pass.",
  REROUTE: "Sends the payment down an alternate rail/PSP — chosen when reroute's expected value beats retry, and the method is in the reroute-eligible set.",
  HOLD: "No automated action taken — a guardrail (merchant hourly budget spent, cooldown active, or SEVERE-state retry block) overrode the expected-value ranking.",
  ESCALATE_HUMAN: "Automated action was blocked entirely — amount above the escalation threshold, low root-cause confidence, a mandate/autopay debit, or no eligible action survived the gates.",
};

type DrawerContent = { title: string; body: React.ReactNode } | null;

export default function Interventions() {
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerContent>(null);

  useEffect(() => {
    Promise.all([api.incidents(), api.scorecard()])
      .then(([incidents, sc]) => {
        setScorecard(sc);
        if (incidents.length === 0) return null;
        return api.ledger(incidents[0].incident_index, 500);
      })
      .then((led) => setEntries(led ? [...led.entries].reverse() : []))
      .catch((e) => setError(String(e)));
  }, []);

  function explain(action: string) {
    const forAction = (entries ?? []).filter((e) => e.action === action);
    const success = forAction.filter((e) => e.execution_status === "success").length;
    const failed = forAction.filter((e) => e.execution_status === "failed").length;
    const totalAmount = forAction.reduce((sum, e) => sum + e.amount_paise, 0);

    setDrawer({
      title: `${action.replace("_", " ")} — ${forAction.length} decisions`,
      body: (
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-anvil-ink-soft">{ACTION_EXPLANATION[action]}</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-anvil-border p-3">
              <p className="text-xs text-anvil-ink-muted">Succeeded</p>
              <p className="mt-1 text-lg font-semibold text-anvil-success">{success}</p>
            </div>
            <div className="rounded-lg border border-anvil-border p-3">
              <p className="text-xs text-anvil-ink-muted">Failed</p>
              <p className="mt-1 text-lg font-semibold text-anvil-danger">{failed}</p>
            </div>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Amount moved</p>
            <p className="mt-1 text-xl font-semibold text-anvil-ink">{paise(totalAmount)}</p>
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Payments</p>
            <ul className="max-h-64 space-y-1.5 overflow-y-auto">
              {forAction.slice(0, 20).map((e) => (
                <li
                  key={e.sequence}
                  className="flex items-center justify-between rounded-md bg-anvil-surface px-3 py-2 text-xs"
                >
                  <span className="font-mono text-anvil-ink-soft">{e.payment_id}</span>
                  <span className={e.execution_status === "success" ? "text-anvil-success" : "text-anvil-danger"}>
                    {e.execution_status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ),
    });
  }

  return (
    <Shell title="Interventions" subtitle="Every automated recovery action the policy engine decided and executed">
      {error && <ErrorState message={error} />}
      {!error && (!entries || !scorecard) && <Loading label="Loading interventions..." />}

      {entries && scorecard && (
        <>
          <section className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            {(["RETRY", "REROUTE", "HOLD", "ESCALATE_HUMAN"] as const).map((action) => (
              <MetricCard
                key={action}
                label={action.replace("_", " ")}
                value={String(scorecard.decisions_by_action[action] ?? 0)}
                onClick={() => explain(action)}
              />
            ))}
          </section>
          <p className="-mt-4 mb-6 text-xs text-anvil-ink-muted">Click a card for the breakdown</p>

          <Card>
            <CardHeader title="Executed interventions" />
            {entries.length === 0 ? (
              <EmptyState title="No interventions executed" hint="Actions will appear here once the policy engine runs." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-anvil-ink-muted">
                    <tr className="border-b border-anvil-border">
                      <th className="px-5 py-3 font-medium">Payment</th>
                      <th className="px-5 py-3 font-medium">Type</th>
                      <th className="px-5 py-3 font-medium">Outcome</th>
                      <th className="px-5 py-3 font-medium">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.map((e) => (
                      <tr key={e.sequence} className="border-b border-anvil-border last:border-0 hover:bg-anvil-surface">
                        <td className="px-5 py-2.5 font-mono text-xs text-anvil-ink">{e.payment_id}</td>
                        <td className="px-5 py-2.5">
                          <Badge tone={ACTION_TONE[e.action] ?? "blue"}>{e.action}</Badge>
                        </td>
                        <td className="px-5 py-2.5">
                          <Badge tone={STATUS_TONE[e.execution_status] ?? "neutral"}>{e.execution_status}</Badge>
                        </td>
                        <td className="px-5 py-2.5 text-anvil-ink-soft">{paise(e.amount_paise)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      <Drawer
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title ?? ""}
        eyebrow="Intervention type"
      >
        {drawer?.body}
      </Drawer>
    </Shell>
  );
}
