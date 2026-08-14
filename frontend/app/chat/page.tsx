import { ChatPanel } from "@/components/ChatPanel";

export default function ChatPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Retrieval-augmented answers. The model only sees passages pulled from
          your documents, and every claim carries a citation you can check.
        </p>
      </div>

      <ChatPanel />
    </div>
  );
}
