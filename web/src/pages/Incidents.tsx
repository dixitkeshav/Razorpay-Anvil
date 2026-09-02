import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, IncidentSummary, paise } from "../api";
import Shell from "../components/Shell";
import { Badge, Card, ErrorState, Loading } from "../components/ui";
import { pct, sliceLabel } from "../lib/format";
import { SEVERITY_TONE, severityOf, successRateDrop } from "../lib/severity";

export default function Incidents() {
  const [incidents, setIncidents] = useState<IncidentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.incidents().then(setIncidents).catch((e) => setError(String(e)));
  }, []);

  return (
    <Shell title="Incidents" subtitle="All incidents surfaced by the CUSUM detector for this run">
      {error && <ErrorState message={error} />}
      {!error && !incidents && <Loading label="Loading incidents..." />}

      {incidents && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-anvil-ink-muted">
                <tr className="border-b border-anvil-border">
                  <th className="px-5 py-3 font-medium">Slice</th>
                  <th className="px-5 py-3 font-medium">Severity</th>
                  <th className="px-5 py-3 font-medium">Baseline SR</th>
                  <th className="px-5 py-3 font-medium">SR drop</th>
                  <th className="px-5 py-3 font-medium">Affected attempts</th>
                  <th className="px-5 py-3 font-medium">At-risk GMV</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => {
                  const { drop } = successRateDrop(inc);
                  return (
                    <tr key={inc.incident_index} className="border-b border-anvil-border last:border-0 hover:bg-anvil-surface">
                      <td className="px-5 py-3 font-medium text-anvil-ink">{sliceLabel(inc.slice)}</td>
                      <td className="px-5 py-3">
                        <Badge tone={SEVERITY_TONE[severityOf(inc)]}>{severityOf(inc)}</Badge>
                      </td>
                      <td className="px-5 py-3 text-anvil-ink-soft">{pct(inc.baseline_success_rate)}</td>
                      <td className="px-5 py-3 text-anvil-danger">-{pct(drop)}</td>
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
                  );
                })}
                {incidents.length === 0 && (
                  <tr>
                    <td className="px-5 py-10 text-center text-anvil-ink-muted" colSpan={7}>
                      No incidents detected in this run.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </Shell>
  );
}
