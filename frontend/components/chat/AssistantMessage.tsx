"use client";

import { Markdown } from "./Markdown";
import { CardRenderer } from "@/components/cards/CardRenderer";
import { ToolTrace } from "./ToolTrace";
import { StreamingIndicator } from "./StreamingIndicator";
import type { StreamingStage } from "./StreamingIndicator";
import type { ChatMessage } from "@/lib/types";

interface AssistantMessageProps {
  message: ChatMessage;
  /** Стадия стриминга — показывает StreamingIndicator под контентом */
  streamingStage?: StreamingStage | null;
  currentToolName?: string | null;
}

/** Композитный assistant message: TL;DR markdown + cards[] + ToolTrace (Plan 2.5) + StreamingIndicator (Plan 3.1). */
export function AssistantMessage({ message, streamingStage, currentToolName }: AssistantMessageProps) {
  return (
    <div className="flex w-full justify-start">
      <div className="max-w-3xl w-full">
        {/* Метка роли */}
        <div className="text-xs text-[var(--fg-muted)] mb-1 font-medium">
          Ассистент
        </div>

        {/* Inline error — красный border, иконка ⚠, без stack trace */}
        {message.error && (
          <div className="border border-red-700 bg-red-950/30 rounded-md px-3 py-2 text-sm text-red-300 mb-2">
            ⚠ {message.error.message}
          </div>
        )}

        {/* TL;DR — markdown с безопасным рендером */}
        {message.content && (
          <div className="text-sm leading-relaxed">
            <Markdown>{message.content}</Markdown>
          </div>
        )}

        {/* Streaming stage индикатор */}
        {streamingStage && (
          <div className="mt-1">
            <StreamingIndicator stage={streamingStage} toolName={currentToolName ?? undefined} />
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
