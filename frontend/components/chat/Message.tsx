import { cn } from "@/lib/utils";
import { AssistantMessage } from "./AssistantMessage";
import type { StreamingStage } from "@/lib/streaming-stages";
import type { ChatMessage } from "@/lib/types";

interface MessageProps {
  message: ChatMessage;
  streamingStage?: StreamingStage | null;
  currentToolName?: string | null;
  isStreaming?: boolean;
  streamStartedAt?: number | null;
  /** ID сессии — для CardContext load-more (Plan 03-04) */
  sessionId?: string;
  /** F-06: повтор предыдущего вопроса (только для assistant-сообщений). */
  onRepeat?: () => void;
}

export function Message({ message, streamingStage, currentToolName, isStreaming, streamStartedAt, sessionId, onRepeat }: MessageProps) {
  // tool messages не рендерятся в Thread — только в Trace panel (Plan 2.5)
  if (message.role === "tool") return null;

  if (message.role === "assistant") {
    return (
      <AssistantMessage
        message={message}
        streamingStage={streamingStage}
        currentToolName={currentToolName}
        isStreaming={isStreaming}
        streamStartedAt={streamStartedAt}
        sessionId={sessionId}
        onRepeat={onRepeat}
      />
    );
  }

  // user message — bubble справа
  return (
    <div className={cn("flex w-full justify-end")}>
      <div
        className={cn(
          "max-w-3xl rounded-[12px] p-4 text-[15px] leading-[1.6]",
          "bg-[var(--bg-2)] text-[var(--fg-1)] border border-[var(--bd-1)]",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </div>
  );
}
