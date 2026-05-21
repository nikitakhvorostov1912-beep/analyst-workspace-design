"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { Button } from "@/components/ui/button";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import { MemoryHint } from "@/components/memory/MemoryHint";
import { fetchHealth, fetchConnections, fetchLLMConfig } from "@/lib/api";
import { migrateLegacyApiKey } from "@/lib/api-keys";
import { useSessionsStore } from "@/lib/sessions-store";
import { getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import { getOnboardingCompleted, setOnboardingCompleted } from "@/lib/onboarding-flag";
import { publishToast } from "@/lib/toast";
import type { HealthResponse } from "@/lib/types";

type BackendStatus = "loading" | "ok" | "unavailable";

function BackendIndicator() {
  const [status, setStatus] = useState<BackendStatus>("loading");
  const [info, setInfo] = useState<HealthResponse | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setInfo(data);
        setStatus("ok");
      })
      .catch(() => {
        setStatus("unavailable");
      });
  }, []);

  if (status === "loading") return null;

  return (
    <div className="fixed bottom-3 right-3 z-50">
      <span
        className={`text-xs px-2 py-1 rounded border ${
          status === "ok"
            ? "text-[var(--success)] border-[var(--success-40)] bg-[var(--success-12)]"
            : "text-[var(--error)] border-[var(--error-40)] bg-[var(--error-12)]"
        }`}
      >
        {status === "ok"
          ? `Backend: ok ${info?.version ?? ""}`
          : "Backend: недоступен"}
      </span>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [hasConfig, setHasConfig] = useState(false);
  const [activeChannelId, setLocalActiveChannelId] = useState<string | null>(null);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  // null = ещё не определили, true/false = решение принято
  const [showOnboarding, setShowOnboarding] = useState<boolean | null>(null);
  const store = useSessionsStore();

  useEffect(() => {
    let cancelled = false;

    // One-time migration: если в localStorage есть старый api_key — переносим в sessionStorage (T-05-13)
    migrateLegacyApiKey();

    (async () => {
      const flag = getOnboardingCompleted();

      try {
        // Загружаем актуальные данные из backend (source-of-truth, Plan 5.4 UX-04)
        const [conns, llm] = await Promise.all([
          fetchConnections(),
          fetchLLMConfig(),
        ]);
        if (cancelled) return;

        const hasBoth = conns.length > 0 && llm !== null;

        if (!flag) {
          if (hasBoth) {
            // Legacy users: уже всё настроено — ставим флаг автоматически
            setOnboardingCompleted(true);
            setShowOnboarding(false);
          } else {
            setShowOnboarding(true);
          }
        } else {
          setShowOnboarding(false);
        }

        // hasConfig читается из backend (source-of-truth)
        setHasConfig(hasBoth);

        // Auto-select: если ничего не активно, но подключения есть — выбираем первое.
        // Иначе аналитик видит «Выберите подключение» с красной точкой и не понимает что делать.
        if (!cancelled && conns.length > 0) {
          const savedActive = getActiveChannelId();
          const stillExists = savedActive && conns.some((c) => c.id === savedActive);
          if (!stillExists) {
            const firstId = conns[0]!.id;
            setActiveChannelId(firstId);
            setLocalActiveChannelId(firstId);
          }
        }
      } catch {
        // Backend недоступен — не блокируем пользователя onboarding'ом
        if (!cancelled) {
          setShowOnboarding(false);
          setHasConfig(false);
        }
      }

      if (!cancelled) {
        // Если auto-select выше уже выставил activeChannelId — повторно не перетираем.
        // setLocalActiveChannelId вызывается выше в auto-select ветке; здесь подхватываем
        // сохранённое значение только если оно валидно.
        const saved = getActiveChannelId();
        if (saved !== null) setLocalActiveChannelId((prev) => prev ?? saved);
        setReady(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    void store.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  function handleChannelChange(newId: string) {
    setActiveChannelId(newId);
    setLocalActiveChannelId(newId);
    void store.refresh();
  }

  // Перезагружает состояние после завершения onboarding (Plan 5.4: backend source-of-truth)
  function refreshAfterOnboarding() {
    void (async () => {
      try {
        const [conns, llm] = await Promise.all([fetchConnections(), fetchLLMConfig()]);
        setHasConfig(conns.length > 0 && llm !== null);
      } catch {
        setHasConfig(false);
      }
      setLocalActiveChannelId(getActiveChannelId());
      void store.refresh();
    })();
  }

  // Global Cmd+K / Ctrl+K hotkey для CommandPalette (должен быть до ранних return)
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((v) => !v);
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, []);

  // Skeleton пока не загрузились данные
  if (!ready) {
    return (
      <div className="h-screen flex items-center justify-center bg-[var(--bg)]">
        <div className="text-sm text-[var(--fg-muted)]">Загрузка...</div>
      </div>
    );
  }

  // Onboarding wizard (первый запуск)
  if (showOnboarding) {
    return (
      <>
        <OnboardingDialog
          open={true}
          onComplete={(chId) => {
            setShowOnboarding(false);
            if (chId) {
              setActiveChannelId(chId);
              setLocalActiveChannelId(chId);
            }
            refreshAfterOnboarding();
          }}
          onSkip={() => {
            setShowOnboarding(false);
            refreshAfterOnboarding();
          }}
        />
        <BackendIndicator />
      </>
    );
  }

  // Empty state — нет конфигурации
  if (!hasConfig) {
    return (
      <>
        <div className="h-screen flex flex-col items-center justify-center gap-6 bg-[var(--bg)]">
          <div className="text-center space-y-3">
            <h1 className="text-2xl font-semibold text-[var(--fg)]">
              Начните работу
            </h1>
            <p className="text-[var(--fg-muted)] max-w-sm text-sm leading-relaxed">
              Укажите адрес базы 1С и подключите модель — после этого можно задавать вопросы.
            </p>
          </div>
          <Button asChild>
            <Link href="/settings">Настроить</Link>
          </Button>
        </div>
        <BackendIndicator />
      </>
    );
  }

  async function handleCreateNew() {
    const ch = getActiveChannelId() ?? "default";
    try {
      const newSession = await store.createNew(ch);
      router.push(`/sessions/${newSession.id}`);
    } catch (err) {
      // Раньше catch был пустой — кнопка кликалась, ничего не происходило,
      // пользователь думал что приложение зависло. Теперь явно сообщаем
      // причину (типичная — backend не отвечает, см. BackendIndicator).
      const message = err instanceof Error ? err.message : "Не удалось создать чат";
      publishToast({
        type: "error",
        message: `Не удалось создать чат: ${message}. Проверь связь с backend (индикатор справа внизу).`,
      });
    }
  }

  async function handleDelete(sessionId: string) {
    await store.remove(sessionId);
  }

  // Основной layout — AppShell с welcome screen (нет активной сессии).
  // Важно: не рендерить здесь пустой <Thread /> рядом с welcome — оба имеют h-full,
  // main:overflow-y-auto скроллит вниз из-за Thread auto-scrollIntoView, welcome уходит выше viewport.
  const totalSessionCount =
    (store.grouped?.today.length ?? 0) +
    (store.grouped?.yesterday.length ?? 0) +
    (store.grouped?.this_week.length ?? 0) +
    (store.grouped?.earlier.length ?? 0);

  return (
    <>
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        channelId={activeChannelId ?? undefined}
      />
      <MemoryHint sessionCount={totalSessionCount} />
      <AppShell
        grouped={store.grouped}
        activeId={null}
        onCreateNew={handleCreateNew}
        onDeleteSession={handleDelete}
        headerProps={{
          activeChannelId,
          onChannelChange: handleChannelChange,
        }}
      >
        <div className="h-full flex flex-col items-center justify-center gap-6 text-center px-6 max-w-2xl mx-auto" data-testid="welcome-screen">
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold text-[var(--fg)]">
              Готов отвечать на вопросы по 1С
            </h2>
            <p className="text-[var(--fg-muted)] text-sm leading-relaxed">
              Напишите вопрос на русском — модель сама подберёт нужные инструменты 1С,
              выполнит запросы и покажет ответ с таблицей или карточкой объекта.
            </p>
          </div>

          <Button onClick={handleCreateNew} className="gap-2">
            + Новый чат
          </Button>

          <div className="w-full pt-4 border-t border-[var(--border)] text-center">
            <p className="text-xs text-[var(--fg-muted)] pt-2">
              <Link href="/about" className="text-blue-400 hover:underline">
                Подробнее о приложении
              </Link>
              {" · "}
              <Link href="/status" className="text-blue-400 hover:underline">
                Проверить диагностику
              </Link>
            </p>
          </div>
        </div>
      </AppShell>
      <BackendIndicator />
    </>
  );
}
