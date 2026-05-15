"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { fetchConnections, fetchLLMConfig } from "@/lib/api";
import { MCPConnectionList } from "@/components/settings/MCPConnectionList";
import { LLMConfigForm } from "@/components/settings/LLMConfigForm";
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
        setError("Backend недоступен. Запустите docker compose up");
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
      </div>

      {loading && (
        <div className="flex items-center justify-center py-16">
          <p className="text-sm text-[var(--fg-muted)]">Загрузка...</p>
        </div>
      )}

      {!loading && error && (
        <div className="border border-red-800 rounded-lg p-5 bg-[var(--bg-elevated)]">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Секция MCP подключений */}
          <section className="mb-6">
            <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
              <h2 className="text-sm font-semibold text-[var(--fg)] mb-4">
                Подключения 1С
              </h2>
              <MCPConnectionList
                initialConnections={connections}
                onChanged={reloadConnections}
              />
            </div>
          </section>

          {/* Секция LLM */}
          <section>
            <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
              <h2 className="text-sm font-semibold text-[var(--fg)] mb-4">
                LLM
              </h2>
              <LLMConfigForm initial={llmConfig} onSaved={reloadLLM} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
