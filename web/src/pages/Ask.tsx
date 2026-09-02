import ChatThread from "../components/ChatThread";
import Shell from "../components/Shell";
import { Card } from "../components/ui";
import { useChat } from "../lib/useChat";

export default function Ask() {
  const { messages, loading, listRef, send } = useChat();

  return (
    <Shell
      title="Ask Anvil"
      subtitle="Ask why payments are failing, which PSP is affected, or anything about detected incidents"
    >
      <Card className="h-[calc(100vh-160px)] overflow-hidden">
        <ChatThread messages={messages} loading={loading} listRef={listRef} onSend={send} />
      </Card>
    </Shell>
  );
}
