import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api, IncidentSummary, paise, Scorecard } from "../api";

const ACTION_COLORS: Record<string, string> = {
  RETRY: "#3b82f6",
  REROUTE: "#8b5cf6",
  HOLD: "#f59e0b",
  ESCALATE_HUMAN: "#ef4444",
};

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-100">{value}</div>
    </div>
  );
}

export default function OpsOverview() {
  const [incidents, setIncidents] = useState<IncidentSummary[] | null>(null);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.incidents(), api.scorecard()])
      .then(([inc, sc]) => {
        setIncidents(inc);
        setScorecard(sc);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return <div className="p-8 text-red-400">Failed to load: {error}</div>;
  }
  if (!incidents || !scorecard) {
    return <div className="p-8 text-slate-400">Loading Anvil ops overview...</div>;
  }

  const actionData = Object.entries(scorecard.decisions_by_action).map(([action, count]) => ({
    action,
    count,
  }));

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <header className="mb-8">
        <h1 className="text-3xl font-bold">Anvil — Ops Overview</h1>
        <p className="mt-1 text-slate-400">
          Payment-degradation detection and revenue-recovery — Razorpay AI Buildathon Track 03
        </p>
      </header>

      <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Incidents detected" value={String(scorecard.incidents_detected)} />
        <StatCard label="Attempts replayed" value={String(scorecard.attempts_replayed)} />
        <StatCard label="Recovered" value={String(scorecard.recovered_count)} />
        <StatCard
          label="Net incremental recovery"
          value={paise(scorecard.net_incremental_recovery_paise)}
        />
      </section>

      <section className="mb-8 rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h2 className="mb-4 text-lg font-semibold">Decisions by action</h2>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={actionData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="action" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" allowDecimals={false} />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "1px solid #334155", color: "#e2e8f0" }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {actionData.map((d) => (
                <Cell key={d.action} fill={ACTION_COLORS[d.action] ?? "#64748b"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Incidents</h2>
        <div className="overflow-x-auto rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-800 text-slate-400">
              <tr>
                <th className="px-4 py-2">Slice</th>
                <th className="px-4 py-2">Affected attempts</th>
                <th className="px-4 py-2">At-risk GMV</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.incident_index} className="border-t border-slate-800 hover:bg-slate-900">
                  <td className="px-4 py-2 font-mono text-xs">
                    {Object.entries(inc.slice)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(", ")}
                  </td>
                  <td className="px-4 py-2">{inc.affected_attempts}</td>
                  <td className="px-4 py-2">{paise(inc.at_risk_gmv_paise)}</td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/incidents/${inc.incident_index}`}
                      className="text-blue-400 hover:underline"
                    >
                      View incident &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
              {incidents.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-center text-slate-500" colSpan={4}>
                    No incidents detected in this run.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
