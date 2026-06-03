"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Message } from "./Message";
import { EXAMPLE_PROMPTS } from "@/lib/welcome-templates";
import type { StreamingStage } from "@/lib/streaming-stages";
import type { ChatMessage } from "@/lib/types";

interface ThreadProps {
  messages: ChatMessage[];
  /** Стадия стриминга — прокидывается в последний AssistantMessage */
  streamingStage?: StreamingStage | null;
  currentToolName?: string | null;
  /** ID сессии — для CardContext load-more (Plan 03-04) */
  sessionId?: string;
  /** F-06: повтор вопроса — передаётся текст предыдущего user-сообщения. */
  onRepeat?: (content: string) => void;
}

/**
 * Подсказки на пустой сессии. Аналитик-новичок открывает «+ Новый чат» →
 * видит пустую область → не понимает что писать. До этого фикса экран был
 * полностью пустым (только composer внизу), что выглядело как «приложение
 * зависло». Список не интерактивный — это намеренно, чтобы не воровать
 * фокус с composer'а. Аналитик читает, понимает идею, пишет своё.
 */
// F-12: единый источник примеров (lib/welcome-templates · EXAMPLE_PROMPTS),
// общий с пустым экраном на главной.
const EXAMPLE_QUESTIONS = EXAMPLE_PROMPTS;

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center px-6 py-12" data-testid="thread-empty">
      <div className="max-w-xl w-full text-center space-y-6">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-[var(--fg-1)]">
            С чего начнём?
          </h2>
          <p className="text-sm text-[var(--fg-3)] leading-relaxed">
            Спросите базу обычными словами — модель подберёт нужные инструменты 1С,
            выполнит запросы и покажет ответ.
          </p>
        </div>

        <div className="space-y-2">
          <p
            className="text-[10px] tracking-[0.1em] uppercase text-[var(--fg-4)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Примеры
          </p>
          <ul className="space-y-1.5">
            {EXAMPLE_QUESTIONS.map((q) => (
              <li
                key={q}
                className="text-sm text-[var(--fg-2)]"
                style={{ fontFamily: "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace" }}
              >
                «{q}»
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function Thread({ messages, streamingStage, currentToolName, sessionId, onRepeat }: ThreadProps) {
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

  if (visibleMessages.length === 0) {
    return (
      <ScrollArea className="h-full">
        <EmptyState />
      </ScrollArea>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4 max-w-4xl mx-auto">
        {visibleMessages.map((msg, i) => {
          // F-06: для assistant-сообщения находим предыдущий вопрос пользователя.
          const prevUser =
            msg.role === "assistant" && onRepeat
              ? [...visibleMessages.slice(0, i)]
                  .reverse()
                  .find((m) => m.role === "user")?.content
              : undefined;
          return (
            <Message
              key={msg.id}
              message={msg}
              streamingStage={i === lastAssistantIdx ? streamingStage : null}
              currentToolName={i === lastAssistantIdx ? currentToolName : null}
              sessionId={sessionId}
              onRepeat={prevUser ? () => onRepeat?.(prevUser) : undefined}
            />
          );
        })}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
