import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, AttributionData, IncidentDetailData, paise } from "../api";
import Shell from "../components/Shell";
import { Badge, Card, CardHeader, ErrorState, Loading } from "../components/ui";
import { pct, sliceEntries, sliceLabel } from "../lib/format";
import { SEVERITY_TONE, severityOf, successRateDrop } from "../lib/severity";

export default function IncidentDetail() {
  const { incidentIndex } = useParams();
  const index = Number(incidentIndex ?? 0);

  const [incident, setIncident] = useState<IncidentDetailData | null>(null);
  const [attribution, setAttribution] = useState<AttributionData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIncident(null);
    setAttribution(null);
    Promise.all([api.incident(index), api.attribution(index)])
      .then(([inc, attr]) => {
        setIncident(inc);
        setAttribution(attr);
      })
      .catch((e) => setError(String(e)));
  }, [index]);

  return (
    <Shell title={`Incident #${index}`} subtitle="Detection, attribution and estimated impact for this slice">
      {error && <ErrorState message={`incident ${index}: ${error}`} />}
      {!error && (!incident || !attribution) && <Loading label={`Loading incident ${index}...`} />}

      {incident && attribution && (
        <>
          <Link to="/incidents" className="mb-4 inline-block text-sm font-medium text-anvil-blue hover:underline">
            &larr; back to incidents
          </Link>

          <Card className="mb-6">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-anvil-border px-6 py-5">
              <div className="flex items-center gap-3">
                <Badge tone={SEVERITY_TONE[severityOf(incident)]}>{severityOf(incident)}</Badge>
                <h2 className="text-lg font-semibold text-anvil-ink">{sliceLabel(incident.slice)}</h2>
              </div>
              <span className="text-xs text-anvil-ink-muted">{sliceEntries(incident.slice)}</span>
            </div>

            <div className="grid grid-cols-2 gap-6 px-6 py-5 md:grid-cols-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Baseline SR</p>
                <p className="mt-1 text-xl font-semibold text-anvil-ink">{pct(incident.baseline_success_rate)}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">SR drop</p>
                <p className="mt-1 text-xl font-semibold text-anvil-danger">
                  -{pct(successRateDrop(incident).drop)}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Window</p>
                <p className="mt-1 text-xl font-semibold text-anvil-ink">
                  {incident.window[0]}&ndash;{incident.window[1]}
                  <span className="ml-1 text-sm font-normal text-anvil-ink-muted">min</span>
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">At-risk GMV</p>
                <p className="mt-1 text-xl font-semibold text-anvil-ink">{paise(incident.at_risk_gmv_paise)}</p>
              </div>
            </div>
          </Card>

          <section className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Attribution — minimal explanatory cut" />
              <div className="px-6 py-4">
                <p className="mb-4 rounded-md bg-anvil-surface px-3 py-2 font-mono text-xs text-anvil-ink">
                  {sliceEntries(attribution.minimal_cut)}
                </p>
                <table className="w-full text-left text-sm">
                  <thead className="text-anvil-ink-muted">
                    <tr className="border-b border-anvil-border">
                      <th className="py-2 pr-4 font-medium">Dimension</th>
                      <th className="py-2 pr-4 font-medium">Value</th>
                      <th className="py-2 pr-4 font-medium">p-value</th>
                      <th className="py-2 pr-4 font-medium">Fraction explained</th>
                      <th className="py-2 pr-4 font-medium">Attempts</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attribution.trace.map((step, i) => (
                      <tr key={i} className="border-b border-anvil-border last:border-0">
                        <td className="py-2 pr-4 text-anvil-ink">{step.dimension}</td>
                        <td className="py-2 pr-4 text-anvil-ink-soft">{step.value}</td>
                        <td className="py-2 pr-4 font-mono text-xs text-anvil-ink-soft">
                          {step.p_value?.toExponential(2) ?? "-"}
                        </td>
                        <td className="py-2 pr-4 text-anvil-ink-soft">{pct(step.fraction_explained, 1)}</td>
                        <td className="py-2 pr-4 text-anvil-ink-soft">{step.attempts}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card>
              <CardHeader title="Attribution coverage" />
              <div className="flex flex-col gap-4 px-6 py-5">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Coverage</p>
                  <p className="mt-1 text-2xl font-semibold text-anvil-ink">{pct(attribution.coverage, 0)}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Original deficit</p>
                  <p className="mt-1 text-sm font-medium text-anvil-ink">{attribution.original_deficit.toFixed(3)}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-anvil-ink-muted">Target deficit</p>
                  <p className="mt-1 text-sm font-medium text-anvil-ink">{attribution.target_deficit.toFixed(3)}</p>
                </div>
              </div>
            </Card>
          </section>

          <Card>
            <CardHeader
              title="Top affected merchants"
              action={
                <Link to="/merchants" className="text-sm font-medium text-anvil-blue hover:underline">
                  All merchants &rarr;
                </Link>
              }
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-anvil-ink-muted">
                  <tr className="border-b border-anvil-border">
                    <th className="px-6 py-3 font-medium">Merchant</th>
                    <th className="px-6 py-3 font-medium">Attempts</th>
                    <th className="px-6 py-3 font-medium">Successes</th>
                    <th className="px-6 py-3 font-medium">At-risk GMV</th>
                  </tr>
                </thead>
                <tbody>
                  {incident.top_merchants.map((m) => (
                    <tr key={m.merchant_id} className="border-b border-anvil-border last:border-0">
                      <td className="px-6 py-2.5 font-mono text-xs text-anvil-ink">{m.merchant_id}</td>
                      <td className="px-6 py-2.5 text-anvil-ink-soft">{m.attempts}</td>
                      <td className="px-6 py-2.5 text-anvil-ink-soft">{m.successes}</td>
                      <td className="px-6 py-2.5 text-anvil-ink-soft">{paise(m.at_risk_gmv)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </Shell>
  );
}
