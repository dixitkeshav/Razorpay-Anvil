import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, AttributionData, IncidentDetailData, LedgerEntry, paise } from "../api";

const STATUS_COLOR: Record<string, string> = {
  success: "text-emerald-400",
  failed: "text-red-400",
  not_executed: "text-slate-500",
};

export default function IncidentDetail() {
  const { incidentIndex } = useParams();
  const index = Number(incidentIndex ?? 0);

  const [incident, setIncident] = useState<IncidentDetailData | null>(null);
  const [attribution, setAttribution] = useState<AttributionData | null>(null);
  const [ledger, setLedger] = useState<{ total: number; entries: LedgerEntry[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.incident(index), api.attribution(index), api.ledger(index, 50)])
      .then(([inc, attr, led]) => {
        setIncident(inc);
        setAttribution(attr);
        setLedger(led);
      })
      .catch((e) => setError(String(e)));
  }, [index]);

  if (error) {
    return <div className="p-8 text-red-400">Failed to load incident {index}: {error}</div>;
  }
  if (!incident || !attribution || !ledger) {
    return <div className="p-8 text-slate-400">Loading incident {index}...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <Link to="/" className="text-sm text-blue-400 hover:underline">
        &larr; back to ops overview
      </Link>

      <header className="mb-8 mt-4">
        <h1 className="text-2xl font-bold">
          Incident #{incident.incident_index} —{" "}
          {Object.entries(incident.slice)
            .map(([k, v]) => `${k}=${v}`)
            .join(", ")}
        </h1>
        <p className="mt-1 text-slate-400">
          Window: minute {incident.window[0]} to {incident.window[1]} &middot; baseline success
          rate {(incident.baseline_success_rate * 100).toFixed(1)}%
        </p>
      </header>

      <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Affected attempts</div>
          <div className="mt-1 text-2xl font-semibold">{incident.affected_attempts}</div>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">At-risk GMV</div>
          <div className="mt-1 text-2xl font-semibold">{paise(incident.at_risk_gmv_paise)}</div>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Attribution coverage</div>
          <div className="mt-1 text-2xl font-semibold">{(attribution.coverage * 100).toFixed(0)}%</div>
        </div>
      </section>

      <section className="mb-8 rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h2 className="mb-3 text-lg font-semibold">Attribution — minimal explanatory cut</h2>
        <p className="mb-3 font-mono text-sm text-slate-300">
          {Object.entries(attribution.minimal_cut)
            .map(([k, v]) => `${k}=${v}`)
            .join(" AND ")}
        </p>
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="py-1 pr-4">Dimension added</th>
              <th className="py-1 pr-4">Value</th>
              <th className="py-1 pr-4">p-value</th>
              <th className="py-1 pr-4">Fraction explained</th>
              <th className="py-1 pr-4">Attempts</th>
            </tr>
          </thead>
          <tbody>
            {attribution.trace.map((step, i) => (
              <tr key={i} className="border-t border-slate-800">
                <td className="py-1 pr-4">{step.dimension}</td>
                <td className="py-1 pr-4">{step.value}</td>
                <td className="py-1 pr-4 font-mono">{step.p_value?.toExponential(2) ?? "-"}</td>
                <td className="py-1 pr-4">{(step.fraction_explained * 100).toFixed(1)}%</td>
                <td className="py-1 pr-4">{step.attempts}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mb-8 rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h2 className="mb-3 text-lg font-semibold">Top affected merchants</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="py-1 pr-4">Merchant</th>
              <th className="py-1 pr-4">Attempts</th>
              <th className="py-1 pr-4">Successes</th>
              <th className="py-1 pr-4">At-risk GMV</th>
            </tr>
          </thead>
          <tbody>
            {incident.top_merchants.map((m) => (
              <tr key={m.merchant_id} className="border-t border-slate-800">
                <td className="py-1 pr-4">{m.merchant_id}</td>
                <td className="py-1 pr-4">{m.attempts}</td>
                <td className="py-1 pr-4">{m.successes}</td>
                <td className="py-1 pr-4">{paise(m.at_risk_gmv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
        <h2 className="mb-3 text-lg font-semibold">
          Recovery Ledger ({ledger.total} entries for this incident)
        </h2>
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-900 text-slate-400">
              <tr>
                <th className="py-1 pr-4">#</th>
                <th className="py-1 pr-4">Payment</th>
                <th className="py-1 pr-4">Action</th>
                <th className="py-1 pr-4">Status</th>
                <th className="py-1 pr-4">Amount</th>
              </tr>
            </thead>
            <tbody>
              {ledger.entries.map((e) => (
                <tr key={e.sequence} className="border-t border-slate-800" title={e.rationale.join(" | ")}>
                  <td className="py-1 pr-4">{e.sequence}</td>
                  <td className="py-1 pr-4 font-mono text-xs">{e.payment_id}</td>
                  <td className="py-1 pr-4">{e.action}</td>
                  <td className={`py-1 pr-4 ${STATUS_COLOR[e.execution_status] ?? ""}`}>
                    {e.execution_status}
                  </td>
                  <td className="py-1 pr-4">{paise(e.amount_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
