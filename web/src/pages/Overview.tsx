import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api, IncidentSummary, LedgerEntry, paise, Scorecard } from "../api";
import Drawer from "../components/Drawer";
import { IconAlert, IconCheck, IconReplay, IconRupee } from "../components/MetricIcons";
import Shell from "../components/Shell";
import { Badge, Card, CardHeader, ErrorState, Loading, MetricCard } from "../components/ui";
import { sliceLabel } from "../lib/format";
import { SEVERITY_TONE, severityOf } from "../lib/severity";

const ACTION_COLORS: Record<string, string> = {
  RETRY: "#0D5CFF",
  REROUTE: "#8B5CF6",
  HOLD: "#F59E0B",
  ESCALATE_HUMAN: "#EF4444",
};

const ACTION_EXPLANATION: Record<string, string> = {
  RETRY: "Resubmits the same payment on the same rail — chosen when the policy engine's expected value favours a retry over a reroute or hold, and the retry-window and per-method retry-limit gates both pass.",
  REROUTE: "Sends the payment down an alternate rail/PSP — chosen when reroute's expected value beats retry, and the method is in the reroute-eligible set.",
  HOLD: "No automated action taken — a guardrail (merchant hourly budget spent, cooldown active, or SEVERE-state retry block) overrode the expected-value ranking.",
  ESCALATE_HUMAN: "Automated action was blocked entirely — amount above the escalation threshold, low root-cause confidence, a mandate/autopay debit, or no eligible action survived the gates.",
};

type DrawerContent = { title: string; eyebrow: string; body: React.ReactNode } | null;

export default function Overview() {
  const [incidents, setIncidents] = useState<IncidentSummary[] | null>(null);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerContent>(null);

  useEffect(() => {
    Promise.all([api.incidents(), api.scorecard()])
      .then(([inc, sc]) => {
        setIncidents(inc);
        setScorecard(sc);
        return inc.length > 0 ? api.ledger(inc[0].incident_index, 500) : null;
      })
      .then((led) => setLedger(led ? led.entries : []))
      .catch((e) => setError(String(e)));
  }, []);

  function explainAction(action: string) {
    const entries = (ledger ?? []).filter((e) => e.action === action);
    const success = entries.filter((e) => e.execution_status === "success").length;
    const failed = entries.filter((e) => e.execution_status === "failed").length;
    const notExecuted = entries.length - success - failed;
    const totalAmount = entries.reduce((sum, e) => sum + e.amount_paise, 0);
    const samples = entries.slice(0, 4);

    setDrawer({
      eyebrow: "Decisions by action",
      title: `${action.replace("_", " ")} — ${entries.length} decisions`,
      body: (
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-anvil-ink-soft">{ACTION_EXPLANATION[action]}</p>

          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-anvil-border p-3">
              <p className="text-xs text-anvil-ink-muted">Success</p>
              <p className="mt-1 text-lg font-semibold text-anvil-success">{success}</p>
            </div>
            <div className="rounded-lg border border-anvil-border p-3">
              <p className="text-xs text-anvil-ink-muted">Failed</p>
              <p className="mt-1 text-lg font-semibold text-anvil-danger">{failed}</p>
            </div>
            <div className="rounded-lg border border-anvil-border p-3">
              <p className="text-xs text-anvil-ink-muted">Not executed</p>
              <p className="mt-1 text-lg font-semibold text-anvil-ink">{notExecuted}</p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">
              Amount moved through {action.replace("_", " ")}
            </p>
            <p className="mt-1 text-xl font-semibold text-anvil-ink">{paise(totalAmount)}</p>
          </div>

          {samples.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">
                Sample rationale
              </p>
              <ul className="space-y-2">
                {samples.map((e) => (
                  <li key={e.sequence} className="rounded-lg bg-anvil-surface p-3 text-xs text-anvil-ink-soft">
                    <p className="mb-1 font-mono text-[11px] text-anvil-ink-muted">{e.payment_id}</p>
                    {e.rationale[e.rationale.length - 1] ?? "no rationale recorded"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ),
    });
  }

  function explainGmv(label: string) {
    if (!scorecard) return;
    const isOn = label === "Agent ON";
    setDrawer({
      eyebrow: "Recovered vs replayed GMV",
      title: label,
      body: isOn ? (
        <div className="space-y-5">
          <p className="text-sm leading-relaxed text-anvil-ink-soft">
            GMV recovered when the policy engine is allowed to retry, reroute, or hold failed
            attempts during replay — this is the real output of{" "}
            <code className="rounded bg-anvil-surface px-1 py-0.5 text-xs">src/evaluation/replay.py</code>.
          </p>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-anvil-border p-3">
              <span className="text-sm text-anvil-ink-soft">GMV recovered</span>
              <span className="text-sm font-semibold text-anvil-ink">
                {paise(scorecard.gmv_recovered_agent_on_paise)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-anvil-border p-3">
              <span className="text-sm text-anvil-ink-soft">Execution cost</span>
              <span className="text-sm font-semibold text-anvil-ink">
                {paise(scorecard.execution_cost_paise)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-anvil-blue/30 bg-anvil-blue-soft p-3">
              <span className="text-sm font-medium text-anvil-blue">Net incremental recovery</span>
              <span className="text-sm font-semibold text-anvil-blue">
                {paise(scorecard.net_incremental_recovery_paise)}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm leading-relaxed text-anvil-ink-soft">
            The do-nothing counterfactual — what the same replay recovers with the policy engine
            switched off. It's zero by construction: with no retry, reroute, or hold, a failed
            attempt simply stays failed, so no GMV is recovered.
          </p>
          <p className="text-sm leading-relaxed text-anvil-ink-soft">
            Everything in <span className="font-medium text-anvil-ink">Net incremental recovery</span> is
            the delta this baseline makes visible — Anvil's entire case rests on that gap being
            real and reproducible via <code className="rounded bg-anvil-surface px-1 py-0.5 text-xs">make eval</code>.
          </p>
        </div>
      ),
    });
  }

  return (
    <Shell title="Overview" subtitle="Revenue at risk and recovery impact — from the last committed eval run">
      {error && <ErrorState message={error} />}
      {!error && (!incidents || !scorecard) && <Loading label="Loading overview..." />}

      {incidents && scorecard && (
        <>
          <section className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Incidents detected" value={String(scorecard.incidents_detected)} icon={<IconAlert />} />
            <MetricCard label="Attempts replayed" value={String(scorecard.attempts_replayed)} icon={<IconReplay />} />
            <MetricCard label="Recovered payments" value={String(scorecard.recovered_count)} icon={<IconCheck />} />
            <MetricCard
              label="Net incremental recovery"
              value={paise(scorecard.net_incremental_recovery_paise)}
              icon={<IconRupee />}
            />
          </section>

          <section className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Recovered vs replayed GMV (agent on/off)" />
              <div className="p-5">
                <p className="mb-1 text-xs text-anvil-ink-muted">Click a bar for the breakdown</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={[
                      { label: "Agent ON", value: scorecard.gmv_recovered_agent_on_paise / 100 },
                      { label: "Agent OFF (baseline)", value: scorecard.gmv_recovered_agent_off_paise / 100 },
                    ]}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
                    <XAxis dataKey="label" stroke="#98A2B3" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis stroke="#98A2B3" tickLine={false} axisLine={false} fontSize={12} />
                    <Tooltip
                      formatter={(v: number) => [`Rs. ${v.toLocaleString("en-IN")}`, "Recovered GMV"]}
                      contentStyle={{ borderRadius: 8, borderColor: "#E5E7EB", fontSize: 12 }}
                    />
                    <Bar
                      dataKey="value"
                      radius={[6, 6, 0, 0]}
                      fill="#0D5CFF"
                      cursor="pointer"
                      onClick={(d: { label: string }) => explainGmv(d.label)}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <CardHeader title="Decisions by action" />
              <div className="p-5">
                <p className="mb-1 text-xs text-anvil-ink-muted">Click a bar for the breakdown</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={Object.entries(scorecard.decisions_by_action).map(([action, count]) => ({ action, count }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
                    <XAxis dataKey="action" stroke="#98A2B3" tickLine={false} axisLine={false} fontSize={12} />
                    <YAxis stroke="#98A2B3" tickLine={false} axisLine={false} allowDecimals={false} fontSize={12} />
                    <Tooltip contentStyle={{ borderRadius: 8, borderColor: "#E5E7EB", fontSize: 12 }} />
                    <Bar
                      dataKey="count"
                      radius={[6, 6, 0, 0]}
                      cursor="pointer"
                      onClick={(d: { action: string }) => explainAction(d.action)}
                    >
                      {Object.keys(scorecard.decisions_by_action).map((action) => (
                        <Cell key={action} fill={ACTION_COLORS[action] ?? "#98A2B3"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </section>

          <section>
            <Card>
              <CardHeader
                title="Incidents"
                action={
                  <Link to="/incidents" className="text-sm font-medium text-anvil-blue hover:underline">
                    View all &rarr;
                  </Link>
                }
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-anvil-ink-muted">
                    <tr className="border-b border-anvil-border">
                      <th className="px-5 py-3 font-medium">Slice</th>
                      <th className="px-5 py-3 font-medium">Severity</th>
                      <th className="px-5 py-3 font-medium">Affected attempts</th>
                      <th className="px-5 py-3 font-medium">At-risk GMV</th>
                      <th className="px-5 py-3" />
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.slice(0, 8).map((inc) => (
                      <tr key={inc.incident_index} className="border-b border-anvil-border last:border-0 hover:bg-anvil-surface">
                        <td className="px-5 py-3 font-medium text-anvil-ink">{sliceLabel(inc.slice)}</td>
                        <td className="px-5 py-3">
                          <Badge tone={SEVERITY_TONE[severityOf(inc)]}>{severityOf(inc)}</Badge>
                        </td>
                        <td className="px-5 py-3 text-anvil-ink-soft">{inc.affected_attempts}</td>
                        <td className="px-5 py-3 text-anvil-ink-soft">{paise(inc.at_risk_gmv_paise)}</td>
                        <td className="px-5 py-3 text-right">
                          <Link
                            to={`/incidents/${inc.incident_index}`}
                            className="text-sm font-medium text-anvil-blue hover:underline"
                          >
                            View &rarr;
                          </Link>
                        </td>
                      </tr>
                    ))}
                    {incidents.length === 0 && (
                      <tr>
                        <td className="px-5 py-10 text-center text-anvil-ink-muted" colSpan={5}>
                          No incidents detected in this run.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </section>
        </>
      )}

      <Drawer
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title ?? ""}
        eyebrow={drawer?.eyebrow}
      >
        {drawer?.body}
      </Drawer>
    </Shell>
  );
}
