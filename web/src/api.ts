export type IncidentSummary = {
  incident_index: number;
  slice: Record<string, string>;
  window: [number, number];
  baseline_success_rate: number;
  affected_attempts: number;
  affected_successes: number;
  at_risk_gmv_paise: number;
};

export type IncidentDetailData = IncidentSummary & {
  top_merchants: { merchant_id: string; attempts: number; successes: number; at_risk_gmv: number }[];
};

export type AttributionStep = {
  dimension: string;
  value: string;
  p_value: number | null;
  fraction_explained: number;
  attempts: number;
};

export type AttributionData = {
  minimal_cut: Record<string, string>;
  coverage: number;
  original_deficit: number;
  target_deficit: number;
  trace: AttributionStep[];
};

export type LedgerEntry = {
  sequence: number;
  payment_id: string;
  action: string;
  execution_status: string;
  amount_paise: number;
  rationale: string[];
};

export type Scorecard = {
  incidents_detected: number;
  attempts_replayed: number;
  decisions_by_action: Record<string, number>;
  gmv_recovered_agent_on_paise: number;
  gmv_recovered_agent_off_paise: number;
  execution_cost_paise: number;
  net_incremental_recovery_paise: number;
  recovered_count: number;
};

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  scorecard: () => getJson<Scorecard>("/scorecard"),
  incidents: () => getJson<IncidentSummary[]>("/incidents"),
  incident: (index: number) => getJson<IncidentDetailData>(`/incidents/${index}`),
  attribution: (index: number) => getJson<AttributionData>(`/incidents/${index}/attribution`),
  ledger: (index: number, limit = 100) =>
    getJson<{ total: number; entries: LedgerEntry[] }>(
      `/incidents/${index}/ledger?limit=${limit}`,
    ),
};

export function paise(p: number): string {
  return `Rs. ${(p / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
