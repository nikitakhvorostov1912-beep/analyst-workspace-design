"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { Thread } from "@/components/chat/Thread";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { Button } from "@/components/ui/button";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import { fetchHealth, fetchConnections, fetchLLMConfig } from "@/lib/api";
import { migrateLegacyApiKey } from "@/lib/api-keys";
import { useSessionsStore } from "@/lib/sessions-store";
import { getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import { getOnboardingCompleted, setOnboardingCompleted } from "@/lib/onboarding-flag";
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
            ? "text-green-400 border-green-800 bg-green-950"
            : "text-red-400 border-red-800 bg-red-950"
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
      } catch {
        // Backend недоступен — не блокируем пользователя onboarding'ом
        if (!cancelled) {
          setShowOnboarding(false);
          setHasConfig(false);
        }
      }

      if (!cancelled) {
        setLocalActiveChannelId(getActiveChannelId());
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
              Подключите вашу базу 1С через MCP и укажите LLM-провайдер
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
    } catch {
      // Если создание не удалось — остаёмся на главной
    }
  }

  async function handleDelete(sessionId: string) {
    await store.remove(sessionId);
  }

  // Основной layout — AppShell с пустым Thread (нет активной сессии)
  return (
    <>
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        channelId={activeChannelId ?? undefined}
      />
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
        <div className="h-full flex flex-col items-center justify-center gap-6 text-center px-6 max-w-2xl mx-auto">
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

          <div className="w-full pt-4 border-t border-[var(--border)] space-y-2 text-left">
            <p className="text-xs text-[var(--fg-muted)] uppercase tracking-wide">
              Попробуйте спросить
            </p>
            <div className="space-y-1.5">
              {[
                "Расскажи про базу — какие подсистемы, основные документы",
                "Покажи последние 50 документов реализации",
                "Что в журнале регистрации за сегодня — есть ошибки?",
                "Сколько контрагентов в базе и сколько активных",
                "Где используется справочник Номенклатура — какие документы",
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={handleCreateNew}
                  className="block w-full text-left text-sm text-[var(--fg-muted)] hover:text-[var(--fg)] hover:bg-[var(--bg-elevated)] rounded px-3 py-2 transition-colors border border-transparent hover:border-[var(--border)]"
                >
                  → {q}
                </button>
              ))}
            </div>
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
        <Thread messages={[]} />
      </AppShell>
      <BackendIndicator />
    </>
  );
}
