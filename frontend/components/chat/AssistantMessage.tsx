"use client";

import { Markdown } from "./Markdown";
import { AnswerProvenance } from "./AnswerProvenance";
import { Alert } from "@/components/ui/Alert";
import { CopyButton } from "@/components/ui/CopyButton";
import { BrandMark } from "@/components/shell/BrandMark";
import { CardRenderer } from "@/components/cards/CardRenderer";
import { ToolTrace } from "./ToolTrace";
import { StreamingStages } from "./StreamingStages";
import { buildStreamingStages } from "@/lib/streaming-stages";
import { getMCPConnections, getActiveChannelId } from "@/lib/storage";
import { parseBackendDate } from "@/lib/utils";
import { formatDuration } from "@/lib/format-duration";
import type { StreamingStage } from "@/lib/streaming-stages";
import type { ChatMessage, CardContext } from "@/lib/types";

function formatTime(iso: string | undefined): string {
  if (!iso) return "";
  try {
    return parseBackendDate(iso).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

interface AssistantMessageProps {
  message: ChatMessage;
  /** Стадия стриминга — показывает StreamingStages под контентом */
  streamingStage?: StreamingStage | null;
  currentToolName?: string | null;
  /** ID сессии — для CardContext load-more */
  sessionId?: string;
}

/**
 * Композитный assistant message:
 *   TL;DR markdown + cards[] + ToolTrace (Plan 2.5) + StreamingStages (Phase 11.4)
 *
 * Phase 11.4: StreamingIndicator → StreamingStages с pipeline-визуализацией.
 * Adapter в `lib/streaming-stages.ts` маппит SSE state на массив Stage.
 */
export function AssistantMessage({
  message,
  streamingStage,
  currentToolName,
  sessionId,
}: AssistantMessageProps) {
  // Cache fallback after ChannelSelector sync: getMCPConnections() читает localStorage-кеш,
  // который заполняется через syncMCPConnections() в ChannelSelector после успешного fetchConnections().
  // Для production source-of-truth используется fetchConnections() в page.tsx (Plan 5.4 UX-04).
  // Этот read используется только для read-only UX (curl-copy endpoint) — T-05-15 accept.
  const activeChannelId = getActiveChannelId();
  const connections = getMCPConnections();
  const mcpEndpoint = connections.find((c) => c.id === activeChannelId)?.endpoint;

  // Формируем CardContext для load-more
  const cardContext: CardContext | undefined = sessionId && message.id
    ? { sessionId, messageId: message.id, mcpEndpoint }
    : undefined;

  // Phase 11.4: преобразуем SSE state → линейный pipeline для StreamingStages
  const pipeline = buildStreamingStages({
    streamingStage: streamingStage ?? null,
    currentToolName: currentToolName ?? null,
    toolCalls: message.tool_calls ?? [],
  });

  const time = formatTime(message.created_at);
  const isStreaming = Boolean(streamingStage);

  return (
    <div className="group flex w-full justify-start gap-3">
      {/* Аватар-глиф (F-06) */}
      <BrandMark size={28} className="flex-none mt-0.5" />

      <div className="max-w-3xl w-full min-w-0">
        {/* Имя · время · длительность */}
        <div
          className="flex items-center gap-2 mb-1 text-[11px] text-[var(--fg-3)]"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          <span className="font-medium text-[var(--fg-2)]">Аналитик</span>
          {time && (
            <>
              <span className="text-[var(--fg-4)]">·</span>
              <span className="tabular-nums">{time}</span>
            </>
          )}
          {message.duration_ms != null && message.duration_ms > 0 && (
            <>
              <span className="text-[var(--fg-4)]">·</span>
              <span className="tabular-nums">{formatDuration(message.duration_ms)}</span>
            </>
          )}
        </div>

        {/* Inline error — единый Alert (F-04), без emoji, lucide-иконка */}
        {message.error && (
          <div className="mb-2">
            <Alert tone="error" title={message.error.message} />
          </div>
        )}

        {/* Тело ответа — 15px / line-height 1.6 (redesign 2.0 §1.7) */}
        {message.content && (
          <div className="text-[15px] leading-[1.6]">
            <Markdown>{message.content}</Markdown>
          </div>
        )}

        {/* Грунт ответа — провенанс под текстом (F-02). Только по завершении стрима. */}
        {!isStreaming && (
          <div className="mt-2">
            <AnswerProvenance toolCalls={message.tool_calls ?? []} />
          </div>
        )}

        {/* Streaming pipeline — pipeline-визуализация с иконками + переходы */}
        {pipeline && (
          <div className="mt-2">
            <StreamingStages
              stages={pipeline.stages}
              activeIndex={pipeline.activeIndex}
            />
          </div>
        )}

        {/* Inline карточки */}
        {message.cards && message.cards.length > 0 && (
          <div className="space-y-3 mt-3">
            {message.cards.map((card, i) => (
              <CardRenderer key={i} card={card} context={cardContext} />
            ))}
          </div>
        )}

        {/* Hover-действия (F-06): появляются при наведении/фокусе на сообщение */}
        {!isStreaming && message.content && (
          <div className="mt-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity duration-150">
            <CopyButton value={message.content} label="Копировать ответ" />
          </div>
        )}

        {/* Trace panel — показывается только если есть tool_calls */}
        <ToolTrace
          toolCalls={message.tool_calls ?? []}
          totalDurationMs={message.duration_ms}
          mcpEndpoint={mcpEndpoint}
        />
      </div>
    </div>
  );
}
