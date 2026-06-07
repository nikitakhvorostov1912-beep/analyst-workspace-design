"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown } from "lucide-react";
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
  isStreaming?: boolean;
  streamStartedAt?: number | null;
  /** ID сессии — для CardContext load-more (Plan 03-04) */
  sessionId?: string;
  /** F-06: повтор вопроса — передаётся текст предыдущего user-сообщения. */
  onRepeat?: (content: string) => void;
  /** Карточка ИТС → «Разобрать статью»: отправка нового сообщения. */
  onAsk?: (text: string) => void;
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

export function Thread({ messages, streamingStage, currentToolName, isStreaming, streamStartedAt, sessionId, onRepeat, onAsk }: ThreadProps) {
  // tool-сообщения не рендерятся в Thread — только в Trace panel (Plan 2.5)
  const visibleMessages = messages.filter((m) => m.role !== "tool");
  const hasMessages = visibleMessages.length > 0;
  const lastAssistantIdx = visibleMessages.reduce(
    (acc, m, i) => (m.role === "assistant" ? i : acc),
    -1,
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLElement | null>(null);
  // «Прилипание» к низу. stickRef меняется ТОЛЬКО реальным скроллом
  // пользователя → не зависит от тайминга разметки. Пока пользователь у низа —
  // лента следует за стримом; отлистал вверх читать — не дёргаем + кнопка «↓».
  // Решает жалобу «скролл блокируется/дёргает вниз пока идёт ответ».
  const stickRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  // Находим scroll-viewport (radix ScrollArea) и слушаем позицию.
  // Завязано на hasMessages: при прямой загрузке сессии Thread сначала
  // рендерит EmptyState (messages грузятся async) — bottomRef ещё нет.
  // Эффект перезапускается, когда лента появилась, и привязывается тогда.
  useEffect(() => {
    if (!hasMessages) return;
    const vp = bottomRef.current?.closest(
      "[data-radix-scroll-area-viewport]",
    ) as HTMLElement | null;
    viewportRef.current = vp;
    if (!vp) return;
    function onScroll() {
      if (!vp) return;
      const near = vp.scrollHeight - vp.scrollTop - vp.clientHeight < 120;
      stickRef.current = near;
      setShowJump(!near);
    }
    vp.addEventListener("scroll", onScroll, { passive: true });
    return () => vp.removeEventListener("scroll", onScroll);
  }, [hasMessages]);

  // Смена сессии — снова прилипаем к низу (показать последнее).
  useEffect(() => {
    stickRef.current = true;
    setShowJump(false);
  }, [sessionId]);

  // Авто-скролл при новом контенте — только если прилипание включено.
  // Прямой scrollTop (а не scrollIntoView) надёжнее при растущем контенте;
  // rAF добивает после доразметки таблиц/карточек (иначе промах «до layout»).
  useEffect(() => {
    const vp = viewportRef.current;
    if (!vp || !stickRef.current) return;
    vp.scrollTop = vp.scrollHeight;
    const raf = requestAnimationFrame(() => {
      const v = viewportRef.current;
      if (v && stickRef.current) v.scrollTop = v.scrollHeight;
    });
    return () => cancelAnimationFrame(raf);
  }, [messages]);

  function scrollToBottom() {
    stickRef.current = true;
    setShowJump(false);
    const vp = viewportRef.current;
    if (vp) vp.scrollTop = vp.scrollHeight;
  }

  if (!hasMessages) {
    return (
      <ScrollArea className="h-full">
        <EmptyState />
      </ScrollArea>
    );
  }

  return (
    <div className="relative h-full">
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
                isStreaming={i === lastAssistantIdx ? isStreaming : false}
                streamStartedAt={i === lastAssistantIdx ? streamStartedAt : null}
                sessionId={sessionId}
                onRepeat={prevUser ? () => onRepeat?.(prevUser) : undefined}
                onAsk={onAsk}
              />
            );
          })}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Кнопка «вниз» — появляется когда пользователь отлистал вверх. */}
      {showJump && (
        <button
          type="button"
          onClick={scrollToBottom}
          data-testid="scroll-to-bottom"
          aria-label="Прокрутить вниз"
          className="absolute bottom-4 left-1/2 -translate-x-1/2 inline-flex items-center gap-1.5 h-8 px-3 rounded-full bg-[var(--bg-2)] border border-[var(--bd-2)] text-[12px] text-[var(--fg-1)] shadow-sm hover:bg-[var(--bg-hover)] hover:border-[var(--bd-3)] transition-colors"
        >
          <ArrowDown className="h-3.5 w-3.5" />
          {isStreaming ? "Ответ внизу" : "Вниз"}
        </button>
      )}
    </div>
  );
}
