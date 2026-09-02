import { useState } from "react";
import { Link } from "react-router-dom";

import type { ChatMessage } from "../lib/useChat";

const SUGGESTIONS = [
  "Why are payments failing right now?",
  "Which PSP is down?",
  "What's affected — one method or several?",
];

export default function ChatThread({
  messages,
  loading,
  listRef,
  onSend,
  compact = false,
}: {
  messages: ChatMessage[];
  loading: boolean;
  listRef: React.RefObject<HTMLDivElement>;
  onSend: (q: string) => void;
  compact?: boolean;
}) {
  const [input, setInput] = useState("");

  return (
    <div className="flex h-full flex-col">
      <div ref={listRef} className={`flex-1 space-y-3 overflow-y-auto ${compact ? "p-4" : "p-5"}`}>
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <p className="text-sm text-anvil-ink-muted">
              Answers are grounded only in incidents Anvil has already detected — try one:
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSend(s)}
                  className="rounded-full border border-anvil-border px-3 py-1.5 text-xs font-medium text-anvil-ink-soft hover:border-anvil-blue hover:text-anvil-blue"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "bg-anvil-blue text-white"
                  : m.isError
                    ? "border border-red-200 bg-anvil-danger-soft text-anvil-danger"
                    : "border border-anvil-border bg-anvil-surface text-anvil-ink"
              }`}
            >
              <p className="whitespace-pre-wrap">{m.text}</p>
              {m.incidentIndices && m.incidentIndices.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2 border-t border-anvil-border/70 pt-2">
                  {m.incidentIndices.map((idx) => (
                    <Link
                      key={idx}
                      to={`/incidents/${idx}`}
                      className="text-xs font-medium text-anvil-blue hover:underline"
                    >
                      Incident #{idx} &rarr;
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-lg border border-anvil-border bg-anvil-surface px-3.5 py-2.5 text-sm text-anvil-ink-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-anvil-ink-muted" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-anvil-ink-muted [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-anvil-ink-muted [animation-delay:300ms]" />
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSend(input);
          setInput("");
        }}
        className="flex items-center gap-2 border-t border-anvil-border p-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask why payments are failing..."
          className="flex-1 rounded-md border border-anvil-border px-3 py-2 text-sm outline-none focus:border-anvil-blue"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-md bg-anvil-blue px-3.5 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
