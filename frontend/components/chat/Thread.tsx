"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "./Message";
import type { StreamingStage } from "./StreamingIndicator";
import type { ChatMessage } from "@/lib/types";

interface ThreadProps {
  messages: ChatMessage[];
  /** Стадия стриминга — прокидывается в последний AssistantMessage */
  streamingStage?: StreamingStage | null;
  currentToolName?: string | null;
  /** ID сессии — для CardContext load-more (Plan 03-04) */
  sessionId?: string;
}

export function Thread({ messages, streamingStage, currentToolName, sessionId }: ThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll вниз при появлении новых сообщений (стриминг и загрузка истории)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // tool-сообщения не рендерятся в Thread — только в Trace panel (Plan 2.5)
  const visibleMessages = messages.filter((m) => m.role !== "tool");
  const lastAssistantIdx = visibleMessages.reduce(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1,
  );

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
        {visibleMessages.map((msg, i) => (
          <Message
            key={msg.id}
            message={msg}
            streamingStage={i === lastAssistantIdx ? streamingStage : null}
            currentToolName={i === lastAssistantIdx ? currentToolName : null}
            sessionId={sessionId}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
