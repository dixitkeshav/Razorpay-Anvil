import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-anvil-border bg-white shadow-card transition-shadow ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-anvil-border px-5 py-4">
      <h2 className="text-sm font-semibold text-anvil-ink">{title}</h2>
      {action}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  delta,
  positive,
  icon,
  onClick,
}: {
  label: string;
  value: string;
  delta?: string;
  positive?: boolean;
  icon?: ReactNode;
  onClick?: () => void;
}) {
  const interactive = Boolean(onClick);
  return (
    <Card
      className={`p-5 ${interactive ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md" : ""}`}
    >
      <button
        type="button"
        onClick={onClick}
        disabled={!interactive}
        className="w-full text-left disabled:cursor-default"
      >
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-anvil-ink-soft">{label}</p>
          {icon && (
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-anvil-blue-soft text-anvil-blue">
              {icon}
            </span>
          )}
        </div>
        <div className="mt-2 flex items-end justify-between gap-2">
          <h3 className="text-2xl font-semibold tracking-tight text-anvil-ink">{value}</h3>
          {delta && (
            <span
              className={`text-sm font-medium ${positive ? "text-anvil-success" : "text-anvil-danger"}`}
            >
              {delta}
            </span>
          )}
        </div>
      </button>
    </Card>
  );
}

const BADGE_STYLES: Record<string, string> = {
  neutral: "bg-anvil-surface text-anvil-ink-soft border-anvil-border",
  blue: "bg-anvil-blue-soft text-anvil-blue border-blue-100",
  success: "bg-anvil-success-soft text-anvil-success border-green-100",
  warning: "bg-anvil-warning-soft text-anvil-warning border-amber-100",
  danger: "bg-anvil-danger-soft text-anvil-danger border-red-100",
};

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "blue" | "success" | "warning" | "danger";
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-6 py-16 text-center">
      <p className="text-sm font-medium text-anvil-ink">{title}</p>
      {hint && <p className="text-sm text-anvil-ink-muted">{hint}</p>}
    </div>
  );
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="flex h-full min-h-[40vh] items-center justify-center text-sm text-anvil-ink-muted">
      {label}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="m-6 rounded-lg border border-red-200 bg-anvil-danger-soft p-4 text-sm text-anvil-danger">
      Failed to load: {message}
    </div>
  );
}
