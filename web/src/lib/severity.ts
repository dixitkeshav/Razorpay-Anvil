import type { IncidentSummary } from "../api";

export type SeverityLevel = "SEVERE" | "DEGRADED" | "WATCH";

/**
 * Client-side display tier only — derived from the real success-rate drop
 * returned by the API. Not the policy engine's IncidentState (that enum is
 * internal to src/policy and isn't exposed over the API).
 */
export function severityOf(inc: Pick<IncidentSummary, "baseline_success_rate" | "affected_attempts" | "affected_successes">): SeverityLevel {
  const currentRate = inc.affected_attempts > 0 ? inc.affected_successes / inc.affected_attempts : 0;
  const drop = inc.baseline_success_rate - currentRate;
  if (drop >= 0.15) return "SEVERE";
  if (drop >= 0.08) return "DEGRADED";
  return "WATCH";
}

export function successRateDrop(inc: Pick<IncidentSummary, "baseline_success_rate" | "affected_attempts" | "affected_successes">): {
  currentRate: number;
  drop: number;
} {
  const currentRate = inc.affected_attempts > 0 ? inc.affected_successes / inc.affected_attempts : 0;
  return { currentRate, drop: inc.baseline_success_rate - currentRate };
}

export const SEVERITY_TONE: Record<SeverityLevel, "danger" | "warning" | "blue"> = {
  SEVERE: "danger",
  DEGRADED: "warning",
  WATCH: "blue",
};
