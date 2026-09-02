import { useRef, useState } from "react";

import { api } from "../api";

export type ChatMessage = {
  role: "user" | "anvil";
  text: string;
  incidentIndices?: number[];
  isError?: boolean;
};

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  async function send(question: string) {
    const q = question.trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setLoading(true);

    try {
      const result = await api.ask(q);
      setMessages((prev) => [
        ...prev,
        { role: "anvil", text: result.answer, incidentIndices: result.incident_indices },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "anvil", text: `Couldn't reach Anvil: ${String(e)}`, isError: true },
      ]);
    } finally {
      setLoading(false);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  }

  return { messages, loading, listRef, send };
}
