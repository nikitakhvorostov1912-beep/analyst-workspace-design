"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionsStore } from "@/lib/sessions-store";
import { getActiveChannelId } from "@/lib/storage";
import { publishToast } from "@/lib/toast";
import { ChatInput } from "@/components/chat/Input";
import Link from "next/link";
import {
  WELCOME_TEMPLATES,
  TEMPLATE_GROUPS,
  buildRepeatTemplate,
  type WelcomeTemplate,
} from "@/lib/welcome-templates";
import { cn } from "@/lib/utils";
import type { ChatAttachment, SessionListItem } from "@/lib/types";

interface ComposerHubProps {
  /** Активный канал (база 1С). Пробрасывается в ChatInput для metadata @-suggest. */
  activeChannelId: string | null;
  /** Список последних сессий — берётся первое user-сообщение для «↺ Повторить». */
  recentSessions: SessionListItem[];
  /** Общее число сессий — для линка «смотреть все». */
  totalSessionCount: number;
  /** Имя активного подключения — для eyebrow «БАЗА 1С · {name}». */
  activeConnectionName?: string;
  /** Тип конфигурации активного подключения — для eyebrow chip. */
  activeConnectionConfigType?: string | null;
  /** Backend has env API key — пробрасывается в ChatInput. */
  hasEnvApiKey?: boolean;
}

/** Чип-шаблон быстрого вопроса. Клик → prefill композера (не отправляет). */
function TemplateChip({
  tpl,
  onClick,
}: {
  tpl: WelcomeTemplate;
  onClick: (tpl: WelcomeTemplate) => void;
}) {
  const Icon = tpl.icon;
  return (
    <button
      type="button"
      onClick={() => onClick(tpl)}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full",
        "border border-[var(--bd-2)] bg-[var(--bg-1)] text-[12.5px] text-[var(--fg-2)]",
        "hover:border-[var(--bd-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)] transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)]",
      )}
      style={{
        fontFamily:
          "var(--font-plex-mono), 'IBM Plex Mono', ui-monospace, monospace",
      }}
    >
      {Icon && <Icon className="h-3 w-3 text-[var(--fg-3)]" />}
      {tpl.title}
    </button>
  );
}

/**
 * Sprint 03 (handoff 06 · Welcome → ComposerHub): welcome screen,
 * замещающий пустой текст + кнопку «+ Новый чат».
 *
 * Layout:
 *   - eyebrow: БАЗА 1С · ● {name} · {config_type}
 *   - h2 «О чём спросим базу?»
 *   - subtitle
 *   - composer (ChatInput с авто-фокусом)
 *   - templates chips strip
 *   - separator «Последние чаты · N — смотреть все →»
 *
 * Submit flow:
 *   1. `store.createNew(channelId)` → новая сессия
 *   2. Сохраняем pending-message в sessionStorage по ключу `pending-message-{id}`
 *   3. `router.push('/sessions/{id}')`
 *   4. На session page: проверяем sessionStorage и автоматически вызываем send()
 */
export function ComposerHub({
  activeChannelId,
  recentSessions,
  totalSessionCount,
  activeConnectionName,
  activeConnectionConfigType,
  hasEnvApiKey,
}: ComposerHubProps) {
  const router = useRouter();
  const store = useSessionsStore();
  const [prefillText, setPrefillText] = useState<string | null>(null);

  // Последнее user-сообщение из самой свежей сессии (для «↺ Повторить»).
  // Берём название первой сессии — это title, который backend генерит из first user msg.
  const lastUserMessage =
    recentSessions[0]?.title && recentSessions[0].title !== "Новый чат"
      ? recentSessions[0].title
      : null;

  const repeatTemplate = buildRepeatTemplate(lastUserMessage);

  // Когда юзер выбрал шаблон — пробрасываем text в ChatInput через ключ.
  // ChatInput читает initialValue prop при mount; мы пересоздаём его сменой key.
  const [composerKey, setComposerKey] = useState(0);

  function handleTemplateClick(tpl: WelcomeTemplate): void {
    setPrefillText(tpl.text);
    setComposerKey((k) => k + 1);
  }

  async function handleFirstQuestion(
    message: string,
    attachments?: ChatAttachment[],
  ): Promise<void> {
    const ch = activeChannelId ?? getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      // Сохраняем pending-message — на странице сессии он будет автоматически
      // отправлен через useChatStream.send() при первом mount.
      if (typeof window !== "undefined") {
        try {
          sessionStorage.setItem(
            `pending-message-${newSession.id}`,
            JSON.stringify({ message, attachments: attachments ?? null }),
          );
        } catch {
          // sessionStorage может быть отключён (приватный режим, electron) —
          // просто навигируем без auto-send, юзер сам нажмёт Enter.
        }
      }
      router.push(`/sessions/${newSession.id}`);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "Не удалось создать чат";
      publishToast({
        type: "error",
        message: `Не удалось создать чат: ${reason}. Проверьте связь с базой 1С.`,
      });
    }
  }

  function focusSidebar(): void {
    // Фокус на первый item в sidebar — он лежит в <aside>...<a> в AppShell.
    // Простой способ: используем data-attribute (см. SessionList.tsx → Link href).
    if (typeof document === "undefined") return;
    const firstLink = document.querySelector<HTMLAnchorElement>(
      "aside a[href^='/sessions/']",
    );
    firstLink?.focus();
  }

  // Sprint 03: при смене prefillText заполняем композер через ref/initialValue.
  // Так как ChatInput управляет своим value через useState, мы перерисовываем
  // компонент со свежим ключом + используем DOM-API для проставления значения
  // в textarea (тот самый, что есть в Input.tsx).
  useEffect(() => {
    if (prefillText === null) return;
    const textarea = document.querySelector<HTMLTextAreaElement>(
      "[data-testid='composer-hub'] textarea",
    );
    if (textarea) {
      textarea.focus();
      // Используем native setter, чтобы React зарегистрировал change event
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )?.set;
      nativeInputValueSetter?.call(textarea, prefillText);
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      // Ставим курсор в конец
      textarea.setSelectionRange(prefillText.length, prefillText.length);
    }
  }, [prefillText, composerKey]);

  return (
    <div
      data-testid="composer-hub"
      className="h-full flex flex-col items-center justify-center gap-8 px-6 max-w-2xl mx-auto py-8"
    >
      {/* Eyebrow + Title */}
      <div className="text-center w-full">
        <div
          className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] mb-3 flex items-center justify-center gap-2 flex-wrap"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          База 1С
          {activeConnectionName && (
            <>
              <span
                className="w-1.5 h-1.5 rounded-full bg-[var(--success)] status-online"
                aria-hidden="true"
              />
              <span className="text-[var(--fg-2)]">{activeConnectionName}</span>
            </>
          )}
          {activeConnectionConfigType && (
            <>
              <span className="text-[var(--fg-4)]">·</span>
              <span>{activeConnectionConfigType}</span>
            </>
          )}
        </div>
        <h2
          className="font-semibold text-[28px] tracking-[0] mb-2 text-[var(--fg-1)]"
          style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
        >
          О чём спросить базу?
        </h2>
        <p className="text-sm text-[var(--fg-3)] max-w-md mx-auto leading-relaxed">
          Спросите обычными словами — запросы и оформление модель возьмёт на себя.
        </p>
      </div>

      {/* Composer — brand-tick рисует сам ChatInput (F-09: дубль убран) */}
      <div className="w-full relative">
        <ChatInput
          key={composerKey}
          onSubmit={handleFirstQuestion}
          channelId={activeChannelId ?? undefined}
          hasEnvApiKey={hasEnvApiKey}
        />
      </div>

      {/* Templates chips — сгруппированы по 3 источникам знаний (P1).
          Так пользователь с первого экрана видит, что спрашивать можно не
          только про свою базу, но и про устройство типовой и методики ИТС. */}
      <div className="w-full space-y-4">
        {/* «↺ Повторить последний» — отдельной строкой над группами */}
        {repeatTemplate && (
          <div className="flex justify-center">
            <TemplateChip tpl={repeatTemplate} onClick={handleTemplateClick} />
          </div>
        )}

        {TEMPLATE_GROUPS.map((grp) => {
          const items = WELCOME_TEMPLATES.filter((t) => t.group === grp.id);
          if (items.length === 0) return null;
          return (
            <div key={grp.id}>
              <div
                className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-4)] mb-2 text-center"
                style={{
                  fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
                }}
              >
                {grp.label}
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                {items.map((tpl) => (
                  <TemplateChip
                    key={tpl.id}
                    tpl={tpl}
                    onClick={handleTemplateClick}
                  />
                ))}
              </div>
            </div>
          );
        })}

        <div className="text-center pt-1">
          <Link
            href="/guide"
            className="text-[11px] tracking-[0.14em] uppercase text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)] rounded-sm px-1"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Как это работает →
          </Link>
        </div>
      </div>

      {/* Recent chats strip — только если есть сессии */}
      {totalSessionCount > 0 && (
        <div className="w-full border-t border-[var(--bd-1)] pt-4 flex items-center justify-between">
          <span
            className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Последние чаты · {totalSessionCount}
          </span>
          <button
            type="button"
            onClick={focusSidebar}
            className="text-[10px] tracking-[0.14em] uppercase text-[var(--accent)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)] rounded-sm px-1"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Смотреть все →
          </button>
        </div>
      )}
    </div>
  );
}
