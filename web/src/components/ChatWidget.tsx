import { useState } from "react";

import ChatThread from "./ChatThread";
import { useChat } from "../lib/useChat";

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const { messages, loading, listRef, send } = useChat();

  return (
    <>
      <div
        className={`fixed bottom-6 right-6 z-30 flex h-[32rem] w-[23rem] flex-col overflow-hidden rounded-xl border border-anvil-border bg-white shadow-2xl transition-all duration-200 ${
          open ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-3 opacity-0"
        }`}
      >
        <div className="flex items-center justify-between border-b border-anvil-border bg-anvil-blue-soft px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-anvil-blue text-xs font-bold text-white">
              A
            </span>
            <div>
              <p className="text-sm font-semibold text-anvil-ink">Ask Anvil</p>
              <p className="text-[11px] text-anvil-ink-soft">Grounded in detected incidents</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close chat"
            className="flex h-7 w-7 items-center justify-center rounded-md text-anvil-ink-soft hover:bg-white/60"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
              <path d="m5 5 10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <ChatThread messages={messages} loading={loading} listRef={listRef} onSend={send} compact />
        </div>
      </div>

      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open Ask Anvil"
          className="fixed bottom-6 right-6 z-30 flex h-13 w-13 items-center justify-center rounded-full bg-anvil-blue text-white shadow-lg shadow-anvil-blue/30 transition-transform hover:scale-105"
          style={{ height: "3.25rem", width: "3.25rem" }}
        >
          <svg className="h-5.5 w-5.5" viewBox="0 0 20 20" fill="none">
            <path d="M3 4.5h14v9H8.5L5 16.5V13.5H3v-9Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
            <path d="M7 8h6M7 10.5h4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </>
  );
}
