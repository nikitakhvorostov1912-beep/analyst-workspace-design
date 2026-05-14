import { cn } from "@/lib/utils";
import { AssistantMessage } from "./AssistantMessage";
import type { ChatMessage } from "@/lib/types";

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  // tool messages не рендерятся в Thread — только в Trace panel (Plan 2.5)
  if (message.role === "tool") return null;

  if (message.role === "assistant") {
    return <AssistantMessage message={message} />;
  }

  // user message — bubble справа
  return (
    <div className={cn("flex w-full justify-end")}>
      <div
        className={cn(
          "max-w-3xl rounded-lg p-4 text-sm leading-relaxed",
          "bg-[var(--bg-elevated)] text-[var(--fg)] border border-[var(--border)]",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </div>
  );
}
