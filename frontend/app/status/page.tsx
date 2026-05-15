"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, CheckCircle2, XCircle, AlertCircle, HelpCircle } from "lucide-react";
import {
  fetchHealth,
  fetchConnections,
  fetchLLMConfig,
  pingConnection,
  testLLMConfig,
} from "@/lib/api";
import { getLLMApiKey } from "@/lib/api-keys";
import { Button } from "@/components/ui/button";

type CheckStatus = "loading" | "ok" | "warn" | "error";

type Check = {
  id: string;
  title: string;
  status: CheckStatus;
  message: string;
  hint?: string;
};

export default function StatusPage() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [running, setRunning] = useState(false);

  async function runChecks() {
    setRunning(true);

    const results: Check[] = [];

    // 1. Backend health
    try {
      const h = await fetchHealth();
      results.push({
        id: "backend",
        title: "Backend (FastAPI)",
        status: "ok",
        message: `OK · версия ${h.version} · БД ${h.db}`,
      });
    } catch {
      results.push({
        id: "backend",
        title: "Backend (FastAPI)",
        status: "error",
        message: "Не отвечает",
        hint: "Запустите `docker compose up backend` или `python -m uvicorn app.main:app --port 8010`",
      });
      setChecks([...results, ...placeholderRest()]);
      setRunning(false);
      return;
    }

    // 2. MCP connections
    let connections: Awaited<ReturnType<typeof fetchConnections>> = [];
    try {
      connections = await fetchConnections();
    } catch {
      results.push({
        id: "connections",
        title: "MCP подключения",
        status: "error",
        message: "Не удалось получить список",
      });
    }

    if (connections.length === 0) {
      results.push({
        id: "connections",
        title: "MCP подключения",
        status: "warn",
        message: "Подключений нет",
        hint: "Добавьте подключение к вашей базе 1С через Настройки → MCP",
      });
    } else {
      // Пингуем каждое подключение
      for (const conn of connections) {
        try {
          const ping = await pingConnection(conn.id);
          const toolCount = (ping as { tool_count?: number }).tool_count;
          results.push({
            id: `mcp-${conn.id}`,
            title: `MCP «${conn.name}»`,
            status: "ok",
            message: `OK · ${toolCount ?? "?"} инструментов · ${conn.endpoint}`,
          });
        } catch (e) {
          results.push({
            id: `mcp-${conn.id}`,
            title: `MCP «${conn.name}»`,
            status: "error",
            message: e instanceof Error ? e.message : "Не отвечает",
            hint: `Проверьте что MCP Toolkit запущен на ${conn.endpoint}`,
          });
        }
      }
    }

    // 3. LLM config
    let llmConfig: Awaited<ReturnType<typeof fetchLLMConfig>> = null;
    try {
      llmConfig = await fetchLLMConfig();
    } catch {
      /* swallow */
    }

    if (!llmConfig) {
      results.push({
        id: "llm-config",
        title: "LLM провайдер",
        status: "warn",
        message: "Не настроен",
        hint: "Добавьте endpoint и ключ через Настройки → LLM",
      });
    } else {
      const apiKey = getLLMApiKey();
      if (!apiKey) {
        results.push({
          id: "llm-config",
          title: "LLM провайдер",
          status: "warn",
          message: `Endpoint настроен (${llmConfig.endpoint}), но ключ не введён`,
          hint: "Ключ хранится в sessionStorage и теряется после закрытия вкладки — введите его снова в Настройках",
        });
      } else {
        try {
          const t = await testLLMConfig(
            {
              endpoint: llmConfig.endpoint,
              model: llmConfig.model,
              temperature: llmConfig.temperature,
            },
            apiKey,
          );
          if (t.ok) {
            results.push({
              id: "llm-config",
              title: "LLM провайдер",
              status: "ok",
              message: `OK · ${llmConfig.endpoint} · модель ${llmConfig.model}`,
            });
          } else {
            results.push({
              id: "llm-config",
              title: "LLM провайдер",
              status: "error",
              message: t.error_code === "invalid_key" ? "Неверный API ключ" : (t.error_code ?? "Ошибка"),
              hint: "Проверьте endpoint и ключ в Настройках → LLM",
            });
          }
        } catch (e) {
          results.push({
            id: "llm-config",
            title: "LLM провайдер",
            status: "error",
            message: e instanceof Error ? e.message : "Не отвечает",
          });
        }
      }
    }

    setChecks(results);
    setRunning(false);
  }

  useEffect(() => {
    void runChecks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const allOk = checks.length > 0 && checks.every((c) => c.status === "ok");
  const anyError = checks.some((c) => c.status === "error");

  return (
    <div className="min-h-screen bg-[var(--bg)] px-6 py-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link
          href="/"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors flex items-center gap-1 text-sm"
        >
          <ArrowLeft size={16} />
          На главную
        </Link>
        <h1 className="text-lg font-semibold text-[var(--fg)]">Диагностика</h1>
        <div className="ml-auto">
          <Button
            onClick={() => void runChecks()}
            variant="secondary"
            disabled={running}
            className="gap-2"
          >
            <RefreshCw size={14} className={running ? "animate-spin" : ""} />
            {running ? "Проверяем..." : "Обновить"}
          </Button>
        </div>
      </div>

      {/* Общий статус */}
      {checks.length > 0 && (
        <div
          className={`mb-6 p-4 rounded-lg border ${
            allOk
              ? "border-green-800 bg-green-950/30"
              : anyError
                ? "border-red-800 bg-red-950/30"
                : "border-yellow-800 bg-yellow-950/30"
          }`}
        >
          <p className="text-sm">
            {allOk && (
              <span className="text-green-400">
                ✓ Всё работает. Можно задавать вопросы на главной странице.
              </span>
            )}
            {anyError && (
              <span className="text-red-400">
                ✗ Найдены проблемы. Смотрите детали ниже и подсказки по исправлению.
              </span>
            )}
            {!allOk && !anyError && (
              <span className="text-yellow-400">
                ⚠ Есть незавершённые настройки. Раскройте детали ниже.
              </span>
            )}
          </p>
        </div>
      )}

      {/* Список проверок */}
      <div className="space-y-2">
        {checks.length === 0 && (
          <div className="text-center text-[var(--fg-muted)] py-8 text-sm">
            Запускаем проверки...
          </div>
        )}
        {checks.map((check) => (
          <CheckRow key={check.id} check={check} />
        ))}
      </div>

      {/* Подсказка снизу */}
      <div className="mt-8 pt-6 border-t border-[var(--border)] text-xs text-[var(--fg-muted)] space-y-1">
        <p>
          <strong>Backend</strong> — FastAPI-сервер, который маршрутизирует запросы между UI, LLM и
          MCP Toolkit.
        </p>
        <p>
          <strong>MCP</strong> — обработка 1С (EPF), которая даёт API доступ к базе. Должна быть
          запущена в вашей 1С.
        </p>
        <p>
          <strong>LLM</strong> — модель которая интерпретирует ваши вопросы и решает какие
          инструменты 1С вызвать.
        </p>
      </div>
    </div>
  );
}

function CheckRow({ check }: { check: Check }) {
  const Icon =
    check.status === "ok"
      ? CheckCircle2
      : check.status === "error"
        ? XCircle
        : check.status === "warn"
          ? AlertCircle
          : HelpCircle;
  const iconColor =
    check.status === "ok"
      ? "text-green-500"
      : check.status === "error"
        ? "text-red-500"
        : check.status === "warn"
          ? "text-yellow-500"
          : "text-[var(--fg-muted)]";

  return (
    <div className="border border-[var(--border)] rounded-md p-4 bg-[var(--bg-elevated)]">
      <div className="flex items-start gap-3">
        <Icon className={`${iconColor} flex-none mt-0.5`} size={18} />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-[var(--fg)]">{check.title}</div>
          <div className="text-xs text-[var(--fg-muted)] mt-1 font-mono break-words">
            {check.message}
          </div>
          {check.hint && (
            <div className="text-xs text-blue-400 mt-2">→ {check.hint}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function placeholderRest(): Check[] {
  return [
    {
      id: "connections-skip",
      title: "MCP подключения",
      status: "warn" as const,
      message: "Проверка пропущена (backend не отвечает)",
    },
    {
      id: "llm-skip",
      title: "LLM провайдер",
      status: "warn" as const,
      message: "Проверка пропущена (backend не отвечает)",
    },
  ];
}
