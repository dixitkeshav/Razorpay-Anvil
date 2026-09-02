export default function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-anvil-border bg-white/85 px-8 py-5 backdrop-blur">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-anvil-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-anvil-ink-soft">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden items-center gap-2 rounded-md border border-anvil-border bg-anvil-surface px-3 py-2 text-sm text-anvil-ink-muted md:flex">
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
            <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.6" />
            <path d="m17 17-4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          Search incidents, merchants, banks...
        </div>

        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-9 w-9 items-center justify-center rounded-md border border-anvil-border text-anvil-ink-soft hover:bg-anvil-surface"
        >
          <svg className="h-4.5 w-4.5" viewBox="0 0 20 20" fill="none">
            <path
              d="M5 8a5 5 0 0 1 10 0v3.2l1.4 2.3H3.6L5 11.2V8Z"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinejoin="round"
            />
            <path d="M8.2 15.8a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>

        <div className="flex items-center gap-2 rounded-md border border-anvil-border px-2.5 py-1.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-anvil-blue-soft text-xs font-semibold text-anvil-blue">
            AD
          </div>
          <div className="hidden text-left leading-tight sm:block">
            <p className="text-xs font-semibold text-anvil-ink">Anvil Demo</p>
            <p className="text-[11px] text-anvil-ink-muted">ACCT-001</p>
          </div>
        </div>
      </div>
    </header>
  );
}
