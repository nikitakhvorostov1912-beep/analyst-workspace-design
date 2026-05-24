"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const PROGRESS_STORAGE_KEY = "analyst.onboarding-progress";
const DISMISSED_STORAGE_KEY = "analyst.onboarding-resume-dismissed";

interface PersistedProgress {
  step: 1 | 2 | 3 | 4;
  createdConnectionId: string | null;
  llmTestPassed: boolean;
  learnOn: boolean;
}

function readProgress(): PersistedProgress | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PROGRESS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedProgress;
    if (parsed.step < 1 || parsed.step > 4) return null;
    return parsed;
  } catch {
    return null;
  }
}

function readDismissed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(DISMISSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

interface OnboardingResumeBannerProps {
  /**
   * Если true — onboarding уже завершён (флаг ставит сам OnboardingDialog),
   * но в localStorage остался прогресс. В этом случае показываем баннер
   * «Вы остановились на шаге N — продолжите».
   */
  onboardingCompleted: boolean;
  /** Открыть OnboardingDialog заново. Управляется HomePage. */
  onResume: () => void;
  /**
   * Sprint 04 (handoff O-3): дополнительный «soft» режим — onboarding
   * был пропущен (skip), и сейчас приложение работает с неполным конфигом
   * (нет подключения или LLM). Banner-warning об этом.
   */
  hasFullConfig?: boolean;
}

/**
 * Sprint 04 (handoff O-2 + O-3): баннер на welcome screen.
 *
 * Два состояния:
 * - Resume (O-2): onboarding-completed=true + progress в localStorage →
 *   «Вы остановились на шаге N — продолжите чтобы получить максимум».
 * - Warning (O-3): hasFullConfig=false → «Часть настроек пропущена, приложение
 *   может работать ограниченно».
 *
 * Закрывается крестиком — флаг dismissed сохраняется, баннер больше не
 * появится в этой и следующих сессиях (пока юзер не сбросит progress).
 */
export function OnboardingResumeBanner({
  onboardingCompleted,
  onResume,
  hasFullConfig = true,
}: OnboardingResumeBannerProps) {
  const [progress, setProgress] = useState<PersistedProgress | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // SSR-safe: читаем localStorage только после mount, иначе hydration mismatch.
  useEffect(() => {
    setProgress(readProgress());
    setDismissed(readDismissed());
  }, []);

  function handleDismiss() {
    setDismissed(true);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(DISMISSED_STORAGE_KEY, "true");
      } catch {
        // ignore
      }
    }
  }

  if (dismissed) return null;

  // Resume-кейс (O-2): высший приоритет, инфо-стиль с accent.
  if (onboardingCompleted && progress) {
    return (
      <div
        role="status"
        data-testid="onboarding-resume-banner"
        className="rounded-lg border border-[var(--accent-32)] bg-[var(--accent-08)] p-4 flex items-center gap-3 animate-fade-up"
      >
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-[var(--fg-1)]">
            Завершите настройку
          </div>
          <div className="text-xs text-[var(--fg-3)] mt-0.5">
            Вы остановились на шаге {progress.step} из 4. Продолжите, чтобы
            получить максимум от приложения.
          </div>
        </div>
        <Button size="sm" onClick={onResume}>
          Продолжить →
        </Button>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Скрыть"
          className="text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors p-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  // Warning-кейс (O-3): нет подключения или LLM — warning-стиль.
  if (onboardingCompleted && !hasFullConfig) {
    return (
      <div
        role="alert"
        data-testid="onboarding-config-warning"
        className="rounded-md border border-dashed border-[var(--warning-40)] bg-[var(--warning-12)] p-3 text-sm flex items-center gap-2 animate-fade-up"
      >
        <AlertTriangle className="h-4 w-4 text-[var(--warning)] flex-none" />
        <span className="text-[var(--fg-1)] flex-1">
          Часть настроек пропущена — приложение может работать ограниченно.
        </span>
        <Link
          href="/settings"
          className="text-[10px] tracking-[0.16em] uppercase text-[var(--accent)] hover:underline flex-none px-1"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          Открыть настройки →
        </Link>
        <button
          type="button"
          onClick={handleDismiss}
          aria-label="Скрыть"
          className="text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors p-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return null;
}
