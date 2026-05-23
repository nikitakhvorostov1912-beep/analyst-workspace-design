"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BarChart3, Brain, ChevronRight, Sparkles } from "lucide-react";
import { fetchConnections, fetchLLMConfig } from "@/lib/api";
import { MCPConnectionList } from "@/components/settings/MCPConnectionList";
import { LLMConfigForm } from "@/components/settings/LLMConfigForm";
import { LocalDataSection } from "@/components/settings/LocalDataSection";
import { Skeleton } from "@/components/ui/Skeleton";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import type { LLMConfigResponse, MCPConnection } from "@/lib/types";

export default function SettingsPage() {
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [llmConfig, setLlmConfig] = useState<LLMConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [conns, llm] = await Promise.all([
          fetchConnections(),
          fetchLLMConfig(),
        ]);
        if (cancelled) return;
        setConnections(conns);
        setLlmConfig(llm);
      } catch {
        if (cancelled) return;
        // REM-2 (2026-05-24): убрали docker hint — приложение в Electron, не Docker.
        setError(
          "Серверная часть не отвечает. Проверьте, что приложение запущено корректно, и попробуйте перезагрузить страницу.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function reloadConnections() {
    try {
      const conns = await fetchConnections();
      setConnections(conns);
    } catch {
      // keep current
    }
  }

  async function reloadLLM() {
    try {
      const llm = await fetchLLMConfig();
      setLlmConfig(llm);
    } catch {
      // keep current
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] p-6 max-w-2xl mx-auto">
      {/* Навигация */}
      <div className="flex items-center gap-3 mb-8">
        <Link
          href="/"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors flex items-center gap-1 text-sm"
        >
          <ArrowLeft size={16} />
          Назад
        </Link>
        <h1 className="text-lg font-semibold text-[var(--fg)]">Настройки</h1>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>

      {loading && (
        // Sprint 02 M01: Skeleton вместо текста «Загрузка...»
        <div className="space-y-3 py-4">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-5 w-32 mt-6" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!loading && error && (
        <div className="border border-red-800 rounded-lg p-5 bg-[var(--bg-elevated)]">
          <p className="text-sm text-[var(--error)]">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Секция подключений 1С */}
          <section className="mb-6">
            <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
              <h2 className="text-sm font-semibold text-[var(--fg)] mb-1">
                Базы 1С
              </h2>
              <p className="text-xs text-[var(--fg-muted)] mb-4">
                Адреса баз, к которым вы хотите задавать вопросы.
              </p>
              <MCPConnectionList
                initialConnections={connections}
                onChanged={reloadConnections}
              />
            </div>
          </section>

          {/* Секция модели ИИ (LLM) */}
          <section className="mb-6">
            <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
              <h2 className="text-sm font-semibold text-[var(--fg)] mb-1">
                Модель ИИ
              </h2>
              <p className="text-xs text-[var(--fg-muted)] mb-4">
                Языковая модель, которая читает ваши вопросы и обращается к базе 1С.
              </p>
              <LLMConfigForm initial={llmConfig} onSaved={reloadLLM} />
            </div>
          </section>

          {/* Sprint 1 (Hermes): Постоянная память */}
          <section>
            <Link
              href="/settings/memory"
              className="flex items-center gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group"
            >
              <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                <Brain className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-[var(--fg-1)]">
                  Постоянная память
                </div>
                <div className="text-[12.5px] text-[var(--fg-3)]">
                  Заметки между сессиями — что ассистент помнит про базу и про вас
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
            </Link>
          </section>

          {/* Sprint 4 (Hermes): Insights dashboard */}
          <section>
            <Link
              href="/insights"
              className="flex items-center gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group"
            >
              <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                <BarChart3 className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-[var(--fg-1)]">
                  Аналитика
                </div>
                <div className="text-[12.5px] text-[var(--fg-3)]">
                  Сессии, инструменты, ошибки — за период
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
            </Link>
          </section>

          {/* Sprint 3 (Hermes): Skills + Curator */}
          <section>
            <Link
              href="/settings/skills"
              className="flex items-center gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group"
            >
              <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                <Sparkles className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[14px] font-semibold text-[var(--fg-1)]">
                  Подсказки агента
                </div>
                <div className="text-[12.5px] text-[var(--fg-3)]">
                  Накопленные шаблоны решений + автоматическая чистка устаревших
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
            </Link>
          </section>

          {/* Phase 9.1: Локальные данные — privacy reset */}
          <section>
            <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
              <LocalDataSection />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
