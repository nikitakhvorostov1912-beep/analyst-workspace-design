"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getLLMConfig, getMCPConnections } from "@/lib/storage";
import type { LLMConfig, MCPConnection } from "@/lib/types";

export default function SettingsPage() {
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null);
  const [mcpConnections, setMcpConnections] = useState<MCPConnection[]>([]);

  useEffect(() => {
    setLlmConfig(getLLMConfig());
    setMcpConnections(getMCPConnections());
  }, []);

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

      {/* Секция LLM */}
      <section className="mb-6">
        <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
          <h2 className="text-sm font-semibold text-[var(--fg)] mb-4">LLM</h2>

          {llmConfig ? (
            <div className="space-y-3">
              <SettingRow label="Endpoint" value={llmConfig.endpoint} />
              <SettingRow label="Модель" value={llmConfig.model} />
              <SettingRow label="Температура" value={String(llmConfig.temperature)} />
              <SettingRow label="API ключ" value="••••••••" />
            </div>
          ) : (
            <p className="text-sm text-[var(--fg-muted)]">
              LLM не настроен
            </p>
          )}

          <div className="mt-4 pt-4 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--fg-muted)] italic">
              Редактирование появится в следующей итерации (Phase 2)
            </p>
          </div>
        </div>
      </section>

      {/* Секция MCP подключения */}
      <section>
        <div className="border border-[var(--border)] rounded-lg p-5 bg-[var(--bg-elevated)]">
          <h2 className="text-sm font-semibold text-[var(--fg)] mb-4">
            MCP подключения
          </h2>

          {mcpConnections.length > 0 ? (
            <div className="space-y-4">
              {mcpConnections.map((conn) => (
                <div
                  key={conn.id}
                  className="p-3 border border-[var(--border)] rounded-md space-y-2"
                >
                  <SettingRow label="Название" value={conn.name} />
                  <SettingRow label="Endpoint" value={conn.endpoint} />
                  {conn.channel && (
                    <SettingRow label="Канал" value={conn.channel} />
                  )}
                  <SettingRow
                    label="Анонимизация"
                    value={conn.anon_enabled ? "Включена" : "Выключена"}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--fg-muted)]">
              Нет настроенных подключений
            </p>
          )}

          <div className="mt-4 pt-4 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--fg-muted)] italic">
              Редактирование появится в следующей итерации (Phase 2)
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-[var(--fg-muted)] flex-none">{label}</span>
      <span className="text-sm text-[var(--fg)] font-mono truncate">{value}</span>
    </div>
  );
}
