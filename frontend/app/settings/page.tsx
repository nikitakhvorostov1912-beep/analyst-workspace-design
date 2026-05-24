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
    <div className="min-h-screen bg-[var(--bg)] p-6 max-w-3xl mx-auto">
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
        <div className="space-y-6">
          {/* Sprint 01 (HIGH-3) + Sprint 02 (Settings unification, 2026-05-24):
              единая система paddings/radius — все главные секции в одном визуальном
              слое (p-5 rounded-lg border-bd-2 bg-bg-1). Memory/Insights/Skills
              перенесены в отдельную секцию «Дополнительно» как grid 3-cols. */}

          {/* Секция подключений 1С */}
          <section>
            <div className="rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] p-5">
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
          <section>
            <div className="rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] p-5">
              <h2 className="text-sm font-semibold text-[var(--fg)] mb-1">
                Модель ИИ
              </h2>
              <p className="text-xs text-[var(--fg-muted)] mb-4">
                Языковая модель, которая читает ваши вопросы и обращается к базе 1С.
              </p>
              <LLMConfigForm initial={llmConfig} onSaved={reloadLLM} />
            </div>
          </section>

          {/* Локальные данные — privacy reset */}
          <section>
            <div className="rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] p-5">
              <LocalDataSection />
            </div>
          </section>

          {/* Дополнительно — Memory / Insights / Skills, единый визуальный слой */}
          <section>
            <h2
              className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] mb-3"
              style={{
                fontFamily: "var(--font-jb-mono), ui-monospace, monospace",
              }}
            >
              Дополнительно
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <Link
                href="/settings/memory"
                className="flex items-start gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group min-h-[96px]"
              >
                <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                  <Brain className="h-4 w-4 text-[var(--accent)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-semibold text-[var(--fg-1)] flex items-center gap-1">
                    Постоянная память
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="text-[12px] text-[var(--fg-3)] mt-1 leading-snug">
                    Заметки между сессиями — что ассистент помнит про базу и про вас
                  </div>
                </div>
              </Link>

              <Link
                href="/insights"
                className="flex items-start gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group min-h-[96px]"
              >
                <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                  <BarChart3 className="h-4 w-4 text-[var(--accent)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-semibold text-[var(--fg-1)] flex items-center gap-1">
                    Аналитика
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="text-[12px] text-[var(--fg-3)] mt-1 leading-snug">
                    Сессии, инструменты, ошибки — за период
                  </div>
                </div>
              </Link>

              <Link
                href="/settings/skills"
                className="flex items-start gap-3 p-4 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)] hover:bg-[var(--bg-2)] hover:border-[var(--bd-3)] transition-colors group min-h-[96px]"
              >
                <div className="h-9 w-9 rounded-md bg-[var(--accent-12)] flex items-center justify-center flex-shrink-0">
                  <Sparkles className="h-4 w-4 text-[var(--accent)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-semibold text-[var(--fg-1)] flex items-center gap-1">
                    Подсказки агента
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <div className="text-[12px] text-[var(--fg-3)] mt-1 leading-snug">
                    Шаблоны решений + автоочистка устаревших
                  </div>
                </div>
              </Link>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
