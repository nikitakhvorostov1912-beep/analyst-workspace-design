"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import { CommandPalette } from "@/components/chat/CommandPalette";
import { ComposerHub } from "@/components/chat/ComposerHub";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/Skeleton";
import { OnboardingDialog } from "@/components/onboarding/OnboardingDialog";
import { OnboardingResumeBanner } from "@/components/onboarding/OnboardingResumeBanner";
import { MemoryHint } from "@/components/memory/MemoryHint";
import { fetchConnections, fetchLLMConfig, patchSessionTitle } from "@/lib/api";
import { useBackendHealth } from "@/lib/use-backend-health";
import { BackendDownBanner } from "@/components/shell/BackendDownBanner";

// 2026-05-25: таймаут на initial bootstrap-fetch чтобы Skeleton не висел
// вечно если backend подвис (memory leak / event loop blocked / asyncio
// fire-and-forget deadlock — см. M-K0 Wave 1, BE-1..BE-4).
//
// Раньше fetchConnections/fetchLLMConfig вызывались без timeout/signal —
// при подвисшем backend Promise.all не резолвился, ready=false навсегда,
// у пользователя чёрный экран с тремя серыми skeleton-полосками без
// возможности что-либо сделать. Закрыть приложение можно было только
// через Task Manager.
//
// Теперь после INIT_FETCH_TIMEOUT_MS падаем в catch → setReady(true).
// `useBackendHealth` (отдельный hook с пингом /health каждые ~5 c) подцепит
// факт что backend лежит и покажет BackendDownBanner с кнопкой Retry.
// Пользователь как минимум видит UI и может попробовать перезайти.
const INIT_FETCH_TIMEOUT_MS = 10_000;

class InitFetchTimeoutError extends Error {
  constructor() {
    super(`Backend не ответил за ${INIT_FETCH_TIMEOUT_MS / 1000} с`);
    this.name = "InitFetchTimeoutError";
  }
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new InitFetchTimeoutError()), ms),
    ),
  ]);
}
import { migrateLegacyApiKey } from "@/lib/api-keys";
import { useSessionsStore } from "@/lib/sessions-store";
import { getActiveChannelId, setActiveChannelId } from "@/lib/storage";
import { getOnboardingCompleted, setOnboardingCompleted } from "@/lib/onboarding-flag";
import { publishToast } from "@/lib/toast";
import { publishUndoToast } from "@/lib/undo-toast";
// Sprint 03 (handoff F · BackendDownBanner): старый BackendIndicator
// (мелкий chip в правом нижнем углу) заменён на top-banner. Логика probe/retry
// вынесена в `useBackendHealth` hook — переиспользуется во всех страницах.

export default function HomePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [hasConfig, setHasConfig] = useState(false);
  const [activeChannelId, setLocalActiveChannelId] = useState<string | null>(null);
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  // null = ещё не определили, true/false = решение принято
  const [showOnboarding, setShowOnboarding] = useState<boolean | null>(null);
  // Sprint 03 (handoff 06 · ComposerHub): данные активного подключения для
  // eyebrow («БАЗА 1С · {name} · {config_type}»). Загружается одновременно
  // с conns/llm — отдельного fetch не нужно.
  const [connections, setConnections] = useState<
    Array<{ id: string; name: string; config_type?: string | null }>
  >([]);
  // 2026-05-24 P0: фикс «Введите API ключ» на главной. Раньше hasEnvApiKey={false}
  // был жёстко вшит — даже когда backend имеет ключ в env, Input.tsx показывал
  // toast и блокировал отправку. См. .planning/qa-prod-release-2026-05-24/FINDINGS.md
  // FINDING-12. Подхватываем из llm.has_env_api_key (по аналогии с sessions/[id]).
  const [hasEnvApiKey, setHasEnvApiKey] = useState(false);
  const store = useSessionsStore();
  const backendHealth = useBackendHealth();

  useEffect(() => {
    let cancelled = false;

    // One-time migration: если в localStorage есть старый api_key — переносим в sessionStorage (T-05-13)
    migrateLegacyApiKey();

    (async () => {
      const flag = getOnboardingCompleted();

      try {
        // Загружаем актуальные данные из backend (source-of-truth, Plan 5.4 UX-04).
        // 2026-05-25: с таймаутом INIT_FETCH_TIMEOUT_MS — иначе подвисший
        // backend оставлял Skeleton навсегда (см. комментарий к константе).
        const [conns, llm] = await withTimeout(
          Promise.all([fetchConnections(), fetchLLMConfig()]),
          INIT_FETCH_TIMEOUT_MS,
        );
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
        setHasEnvApiKey(Boolean(llm?.has_env_api_key));
        // Сохраняем connections для ComposerHub eyebrow
        setConnections(
          conns.map((c) => ({
            id: c.id,
            name: c.name,
            config_type: c.config_type,
          })),
        );

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
      } catch (err) {
        // Backend недоступен (HTTP-ошибка ИЛИ таймаут) — не блокируем
        // пользователя onboarding'ом и не оставляем Skeleton навсегда.
        // BackendDownBanner внизу страницы сам подцепит факт что бэк лежит.
        if (!cancelled) {
          if (err instanceof InitFetchTimeoutError) {
            // Сигнализируем в console — для разработчика в DevTools
            // (production-сборка console.error всё равно собирает).
            console.error(
              "[HomePage] initial fetch timed out — backend hung. " +
                "Showing UI with empty state.",
            );
          }
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

  // Перезагружает состояние после завершения onboarding (Plan 5.4: backend source-of-truth).
  // 2026-05-25: тот же withTimeout что в initial useEffect — иначе после
  // onboarding'а можно было снова уйти в висящий fetch и потерять контроль над UI.
  function refreshAfterOnboarding() {
    void (async () => {
      try {
        const [conns, llm] = await withTimeout(
          Promise.all([fetchConnections(), fetchLLMConfig()]),
          INIT_FETCH_TIMEOUT_MS,
        );
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
    // Sprint 02 (handoff M01): Skeleton shimmer вместо текста «Загрузка...».
    return (
      <div className="h-screen flex flex-col items-center justify-center gap-3 bg-[var(--bg)] px-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-72" />
        <Skeleton className="h-4 w-64" />
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
          // Sprint 04 (handoff O-5): юзер выбрал quick-start на финальном шаге.
          // Создаём сессию и сохраняем pending-message — session page подхватит
          // и автоматически отправит (тот же flow что у ComposerHub).
          onCompleteWithQuestion={async (chId, question) => {
            setShowOnboarding(false);
            if (chId) {
              setActiveChannelId(chId);
              setLocalActiveChannelId(chId);
            }
            refreshAfterOnboarding();
            try {
              const ch = chId ?? getActiveChannelId() ?? "default";
              const newSession = await store.createNew(ch);
              if (typeof window !== "undefined") {
                try {
                  sessionStorage.setItem(
                    `pending-message-${newSession.id}`,
                    JSON.stringify({ message: question, attachments: null }),
                  );
                } catch {
                  // privacy mode — fallback на пустую сессию
                }
              }
              router.push(`/sessions/${newSession.id}`);
            } catch (err) {
              const reason =
                err instanceof Error ? err.message : "Не удалось создать чат";
              publishToast({
                type: "error",
                message: `Не удалось создать чат: ${reason}`,
              });
            }
          }}
        />
        <BackendDownBanner
          visible={backendHealth.status === "unavailable"}
          onRetry={backendHealth.retry}
        />
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
        <BackendDownBanner
          visible={backendHealth.status === "unavailable"}
          onRetry={backendHealth.retry}
        />
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
      // причину (типичная — backend не отвечает, см. BackendDownBanner вверху).
      const message = err instanceof Error ? err.message : "Не удалось создать чат";
      publishToast({
        type: "error",
        message: `Не удалось создать чат: ${message}. Проверьте связь с базой 1С.`,
      });
    }
  }

  function handleDelete(sessionId: string) {
    // Sprint 02 A · UndoToast: оптимистичное удаление с возможностью отмены.
    // Сначала убираем из UI, через 5с делаем реальный DELETE.
    const allItems = [
      ...(store.grouped?.today ?? []),
      ...(store.grouped?.yesterday ?? []),
      ...(store.grouped?.this_week ?? []),
      ...(store.grouped?.earlier ?? []),
    ];
    const item = allItems.find((s) => s.id === sessionId);
    if (!item) return;

    store.removeOptimistic(sessionId);
    publishUndoToast({
      id: `delete-${sessionId}`,
      title: "Чат удалён",
      subtitle: item.title ?? `#${sessionId.slice(0, 4).toUpperCase()}`,
      durationMs: 5000,
      onUndo: () => store.restoreOptimistic(sessionId),
      onCommit: () => {
        void store.commitRemove(sessionId);
      },
    });
  }

  // F-11: переименование чата — оптимистично локально + persist на бэк,
  // при ошибке откатываемся через refresh.
  function handleRename(sessionId: string, title: string): void {
    store.renameLocal(sessionId, title);
    void patchSessionTitle(sessionId, title).catch(() => {
      void store.refresh();
    });
  }

  // Основной layout — AppShell с welcome screen (нет активной сессии).
  // Важно: не рендерить здесь пустой <Thread /> рядом с welcome — оба имеют h-full,
  // main:overflow-y-auto скроллит вниз из-за Thread auto-scrollIntoView, welcome уходит выше viewport.
  const totalSessionCount =
    (store.grouped?.today.length ?? 0) +
    (store.grouped?.yesterday.length ?? 0) +
    (store.grouped?.this_week.length ?? 0) +
    (store.grouped?.earlier.length ?? 0);

  // Sprint 03 (handoff 06 · ComposerHub): данные для eyebrow.
  const activeConn = connections.find((c) => c.id === activeChannelId);
  const recentSessions = [
    ...(store.grouped?.today ?? []),
    ...(store.grouped?.yesterday ?? []),
    ...(store.grouped?.this_week ?? []),
    ...(store.grouped?.earlier ?? []),
  ];

  // Sprint 04 (handoff O-2): функция «перезапустить onboarding».
  // Сбрасываем флаг — useEffect пересчитает и откроет диалог с сохранённым
  // прогрессом из localStorage.
  function handleResumeOnboarding(): void {
    setShowOnboarding(true);
  }

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
        onRenameSession={handleRename}
        headerProps={{
          activeChannelId,
          onChannelChange: handleChannelChange,
        }}
      >
        {/* Sprint 04 (handoff O-2 + O-3): resume banner / config warning над
            ComposerHub. SSR-safe — компонент сам читает localStorage в useEffect. */}
        <div className="px-6 pt-4 max-w-2xl mx-auto w-full">
          <OnboardingResumeBanner
            onboardingCompleted={true}
            onResume={handleResumeOnboarding}
            hasFullConfig={hasConfig}
          />
        </div>
        <ComposerHub
          activeChannelId={activeChannelId}
          recentSessions={recentSessions}
          totalSessionCount={totalSessionCount}
          activeConnectionName={activeConn?.name}
          activeConnectionConfigType={activeConn?.config_type ?? null}
          hasEnvApiKey={hasEnvApiKey}
        />
      </AppShell>
      <BackendDownBanner
        visible={backendHealth.status === "unavailable"}
        onRetry={backendHealth.retry}
      />
    </>
  );
}
