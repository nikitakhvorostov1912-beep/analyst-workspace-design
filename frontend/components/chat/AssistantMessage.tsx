"use client";

import { Markdown } from "./Markdown";
import { CardRenderer } from "@/components/cards/CardRenderer";
import { ToolTrace } from "./ToolTrace";
import type { ChatMessage } from "@/lib/types";

interface AssistantMessageProps {
  message: ChatMessage;
}

/** Композитный assistant message: TL;DR markdown + cards[] + ToolTrace (Plan 2.5). */
export function AssistantMessage({ message }: AssistantMessageProps) {
  return (
    <div className="flex w-full justify-start">
      <div className="max-w-3xl w-full">
        {/* Метка роли */}
        <div className="text-xs text-[var(--fg-muted)] mb-1 font-medium">
          Ассистент
        </div>

        {/* TL;DR — markdown с безопасным рендером */}
        {message.content && (
          <div className="text-sm leading-relaxed">
            <Markdown>{message.content}</Markdown>
          </div>
        )}

        {/* Inline карточки */}
        {message.cards && message.cards.length > 0 && (
          <div className="space-y-3 mt-3">
            {message.cards.map((card, i) => (
              <CardRenderer key={i} card={card} />
            ))}
          </div>
        )}

        {/* Trace panel — показывается только если есть tool_calls */}
        <ToolTrace
          toolCalls={message.tool_calls ?? []}
          totalDurationMs={message.duration_ms}
        />
      </div>
    </div>
  );
}
