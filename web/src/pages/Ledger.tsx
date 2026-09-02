import { useEffect, useState } from "react";

import { api, LedgerEntry, paise } from "../api";
import Shell from "../components/Shell";
import { Badge, Card, EmptyState, ErrorState, Loading } from "../components/ui";

const STATUS_TONE: Record<string, "success" | "danger" | "neutral"> = {
  success: "success",
  failed: "danger",
  not_executed: "neutral",
};

export default function Ledger() {
  const [entries, setEntries] = useState<LedgerEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .incidents()
      .then((incidents) => {
        if (incidents.length === 0) {
          setEntries([]);
          return null;
        }
        return api.ledger(incidents[0].incident_index, 500);
      })
      .then((led) => {
        if (led) {
          setEntries([...led.entries].reverse());
          setTotal(led.total);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <Shell title="Recovery Ledger" subtitle="Append-only audit trail of every executed recovery action">
      {error && <ErrorState message={error} />}
      {!error && !entries && <Loading label="Loading ledger..." />}

      {entries && (
        <Card>
          {entries.length === 0 ? (
            <EmptyState title="No ledger entries yet" hint="Recovery actions will appear here once executed." />
          ) : (
            <div className="max-h-[calc(100vh-13rem)] overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white text-anvil-ink-muted">
                  <tr className="border-b border-anvil-border">
                    <th className="px-5 py-3 font-medium">#</th>
                    <th className="px-5 py-3 font-medium">Payment</th>
                    <th className="px-5 py-3 font-medium">Action</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Amount</th>
                    <th className="px-5 py-3 font-medium">Rationale</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.sequence} className="border-b border-anvil-border last:border-0 hover:bg-anvil-surface">
                      <td className="px-5 py-2.5 text-anvil-ink-muted">{e.sequence}</td>
                      <td className="px-5 py-2.5 font-mono text-xs text-anvil-ink">{e.payment_id}</td>
                      <td className="px-5 py-2.5 font-medium text-anvil-ink">{e.action}</td>
                      <td className="px-5 py-2.5">
                        <Badge tone={STATUS_TONE[e.execution_status] ?? "neutral"}>{e.execution_status}</Badge>
                      </td>
                      <td className="px-5 py-2.5 text-anvil-ink-soft">{paise(e.amount_paise)}</td>
                      <td className="max-w-xs truncate px-5 py-2.5 text-xs text-anvil-ink-muted" title={e.rationale.join(" | ")}>
                        {e.rationale[e.rationale.length - 1] ?? ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="border-t border-anvil-border px-5 py-3 text-xs text-anvil-ink-muted">
            {total} entries total
          </div>
        </Card>
      )}
    </Shell>
  );
}
