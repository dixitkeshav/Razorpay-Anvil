import { useEffect, useState } from "react";

import { api, paise } from "../api";
import Shell from "../components/Shell";
import { Card, EmptyState, ErrorState, Loading } from "../components/ui";

type MerchantRow = { merchant_id: string; attempts: number; successes: number; at_risk_gmv: number; incidents: number };

export default function Merchants() {
  const [rows, setRows] = useState<MerchantRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .incidents()
      .then((incidents) => Promise.all(incidents.map((inc) => api.incident(inc.incident_index))))
      .then((details) => {
        const byMerchant = new Map<string, MerchantRow>();
        for (const inc of details) {
          for (const m of inc.top_merchants) {
            const existing = byMerchant.get(m.merchant_id) ?? {
              merchant_id: m.merchant_id,
              attempts: 0,
              successes: 0,
              at_risk_gmv: 0,
              incidents: 0,
            };
            existing.attempts += m.attempts;
            existing.successes += m.successes;
            existing.at_risk_gmv += m.at_risk_gmv;
            existing.incidents += 1;
            byMerchant.set(m.merchant_id, existing);
          }
        }
        setRows([...byMerchant.values()].sort((a, b) => b.at_risk_gmv - a.at_risk_gmv));
      })
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <Shell title="Merchants" subtitle="Merchants ranked by revenue at risk across all detected incidents">
      {error && <ErrorState message={error} />}
      {!error && !rows && <Loading label="Loading merchants..." />}

      {rows && (
        <Card>
          {rows.length === 0 ? (
            <EmptyState title="No affected merchants" hint="Merchant impact appears here once incidents are detected." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-anvil-ink-muted">
                  <tr className="border-b border-anvil-border">
                    <th className="px-5 py-3 font-medium">Merchant</th>
                    <th className="px-5 py-3 font-medium">Incidents affecting</th>
                    <th className="px-5 py-3 font-medium">Attempts</th>
                    <th className="px-5 py-3 font-medium">Successes</th>
                    <th className="px-5 py-3 font-medium">At-risk GMV</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((m) => (
                    <tr key={m.merchant_id} className="border-b border-anvil-border last:border-0 hover:bg-anvil-surface">
                      <td className="px-5 py-2.5 font-mono text-xs text-anvil-ink">{m.merchant_id}</td>
                      <td className="px-5 py-2.5 text-anvil-ink-soft">{m.incidents}</td>
                      <td className="px-5 py-2.5 text-anvil-ink-soft">{m.attempts}</td>
                      <td className="px-5 py-2.5 text-anvil-ink-soft">{m.successes}</td>
                      <td className="px-5 py-2.5 text-anvil-ink-soft">{paise(m.at_risk_gmv)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </Shell>
  );
}
