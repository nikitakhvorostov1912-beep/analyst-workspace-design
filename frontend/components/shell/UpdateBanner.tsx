"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

/**
 * P1.4 (2026-05-23): UpdateBanner — non-blocking уведомление о новой версии.
 *
 * Слушает события auto-update из main.js (через preload.js bridge):
 *   - `updater:available` — началось скачивание новой версии
 *   - `updater:downloaded` — installer готов, можно перезапустить
 *
 * В dev-режиме (browser без Electron) — компонент скрыт (window.electronAPI
 * отсутствует). В Electron — баннер появляется в Header.
 *
 * UX:
 *   - 1-я стадия: «Скачивается v1.3.1...» — спинер, без действий
 *   - 2-я стадия: «Готово к установке» + кнопка «Перезапустить»
 *   - 3-я стадия: при клике на «Перезапустить» — quitAndInstall()
 */

interface UpdateInfo {
  version?: string;
  releaseDate?: string;
}

type ElectronAPI = {
  onUpdateAvailable: (cb: (info: UpdateInfo) => void) => () => void;
  onUpdateDownloaded: (cb: (info: UpdateInfo) => void) => () => void;
  installUpdate: () => Promise<{ ok: boolean; error?: string }>;
};

declare global {
  interface Window {
    electronAPI?: ElectronAPI & {
      openPath?: (path: string) => Promise<string>;
    };
  }
}

type UpdateState =
  | { kind: "idle" }
  | { kind: "downloading"; version: string }
  | { kind: "ready"; version: string };

export function UpdateBanner() {
  const [state, setState] = useState<UpdateState>({ kind: "idle" });
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    const api = window.electronAPI;
    if (!api || !api.onUpdateAvailable || !api.onUpdateDownloaded) {
      // Не Electron / нет updater'а — скрываем
      return;
    }

    const cleanupAvailable = api.onUpdateAvailable((info) => {
      setState({ kind: "downloading", version: info?.version ?? "" });
    });
    const cleanupDownloaded = api.onUpdateDownloaded((info) => {
      setState({ kind: "ready", version: info?.version ?? "" });
    });

    return () => {
      cleanupAvailable?.();
      cleanupDownloaded?.();
    };
  }, []);

  async function handleInstall() {
    const api = window.electronAPI;
    if (!api?.installUpdate || installing) return;
    setInstalling(true);
    try {
      const result = await api.installUpdate();
      if (!result.ok) {
        console.warn("[updater] install failed:", result.error);
        setInstalling(false);
      }
      // Если ok — приложение уже закрывается, setState не нужен
    } catch (err) {
      console.warn("[updater] install threw:", err);
      setInstalling(false);
    }
  }

  if (state.kind === "idle") return null;

  if (state.kind === "downloading") {
    return (
      <div
        data-testid="update-banner-downloading"
        className="inline-flex items-center gap-2 px-2 py-1 rounded-sm text-[10px] uppercase tracking-wide bg-[var(--bg-2)] text-[var(--fg-3)] border border-[var(--bd-1)]"
        title="Скачивается обновление в фоне. Можно продолжать работу."
      >
        <span className="inline-block h-2 w-2 rounded-full bg-[var(--accent)] animate-pulse" />
        Скачивается v{state.version}…
      </div>
    );
  }

  // state.kind === "ready"
  return (
    <div
      data-testid="update-banner-ready"
      className="inline-flex items-center gap-2 px-2 py-1 rounded-sm text-[10px] uppercase tracking-wide bg-[var(--accent-12)] text-[var(--accent)] border border-[var(--accent-40)]"
    >
      <span>Готова v{state.version}</span>
      <Button
        size="sm"
        variant="ghost"
        onClick={handleInstall}
        disabled={installing}
        className="h-5 px-1.5 text-[10px] uppercase tracking-wide text-[var(--accent)] hover:opacity-80"
        data-testid="update-banner-install"
      >
        {installing ? "Перезапуск…" : "Перезапустить"}
      </Button>
    </div>
  );
}
