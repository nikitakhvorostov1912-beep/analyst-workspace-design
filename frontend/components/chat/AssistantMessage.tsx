"use client";

import { Markdown } from "./Markdown";
import { CardRenderer } from "@/components/cards/CardRenderer";
import type { ChatMessage } from "@/lib/types";

interface AssistantMessageProps {
  message: ChatMessage;
}

/** Композитный assistant message: TL;DR markdown + cards[] + footer placeholder (Trace — Plan 2.5). */
export function AssistantMessage({ message }: AssistantMessageProps) {
  const toolCallCount = message.tool_calls?.length ?? 0;
  const durationMs = message.duration_ms;

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

        {/* Footer — trace placeholder (Plan 2.5 добавит интерактивный ToolTrace) */}
        {toolCallCount > 0 && (
          <div
            className="mt-2 text-xs text-[var(--fg-muted)]"
            data-testid="trace-placeholder"
          >
            {toolCallCount} {toolCallCount === 1 ? "tool" : "tools"}
            {durationMs != null && `, ${durationMs} мс`}
          </div>
        )}
      </div>
    </div>
  );
}
