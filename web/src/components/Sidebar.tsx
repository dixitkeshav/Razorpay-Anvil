import { NavLink } from "react-router-dom";

import AnvilLogo from "./AnvilLogo";

const NAV_ITEMS = [
  { to: "/", label: "Overview", exact: true },
  { to: "/incidents", label: "Incidents" },
  { to: "/interventions", label: "Interventions" },
  { to: "/ledger", label: "Ledger" },
  { to: "/merchants", label: "Merchants" },
  { to: "/policies", label: "Policies" },
  { to: "/ask", label: "Ask Anvil" },
];

function NavIcon({ label }: { label: string }) {
  const common = "h-4.5 w-4.5";
  switch (label) {
    case "Overview":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M3 10.5 10 4l7 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M5 9.5V16h10V9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "Incidents":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M10 3 2 17h16L10 3Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M10 8.5v3.2M10 14.2h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    case "Interventions":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M10 2v4M10 14v4M4 10H2M18 10h-2M5.6 5.6 4.2 4.2M15.8 15.8l-1.4-1.4M5.6 14.4l-1.4 1.4M15.8 4.2l-1.4 1.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      );
    case "Ledger":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <rect x="3.5" y="2.5" width="13" height="15" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
          <path d="M6.5 6.5h7M6.5 10h7M6.5 13.5h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    case "Merchants":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M3 8.5 4 3.5h12l1 5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M3.5 8.5v7h13v-7" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M8 15.5V11h4v4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        </svg>
      );
    case "Policies":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M10 2.5 16.5 5v4.5c0 4.2-2.8 7-6.5 8-3.7-1-6.5-3.8-6.5-8V5L10 2.5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M7.3 10.1 9.2 12l3.5-3.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "Ask Anvil":
      return (
        <svg className={common} viewBox="0 0 20 20" fill="none">
          <path d="M3 4.5h14v9H8.5L5 16.5V13.5H3v-9Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          <path d="M7 8h6M7 10.5h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      );
    default:
      return null;
  }
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-anvil-border bg-white">
      <div className="flex items-center gap-2.5 px-6 py-6">
        <AnvilLogo />
        <div className="leading-tight">
          <span className="block text-lg font-bold tracking-tight text-anvil-ink">Anvil</span>
          <span className="block text-[11px] font-medium text-anvil-ink-muted">Revenue Recovery</span>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-anvil-blue-soft text-anvil-blue"
                  : "text-anvil-ink-soft hover:bg-anvil-surface hover:text-anvil-ink"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-anvil-blue transition-opacity ${
                    isActive ? "opacity-100" : "opacity-0"
                  }`}
                />
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-md transition-colors ${
                    isActive ? "bg-white text-anvil-blue" : "text-anvil-ink-muted group-hover:text-anvil-ink"
                  }`}
                >
                  <NavIcon label={item.label} />
                </span>
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-1 border-t border-anvil-border px-3 py-4">
        <a
          href="https://razorpay.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-anvil-ink-soft hover:bg-anvil-surface hover:text-anvil-ink"
        >
          Docs
        </a>
        <a
          href="https://razorpay.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-anvil-ink-soft hover:bg-anvil-surface hover:text-anvil-ink"
        >
          Support
        </a>
      </div>
    </aside>
  );
}
