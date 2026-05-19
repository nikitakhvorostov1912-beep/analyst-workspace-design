"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCw, CheckCircle2, XCircle, AlertCircle, HelpCircle } from "lucide-react";
import {
  fetchAuxDiagnostics,
  fetchHealth,
  fetchConnections,
  fetchLLMConfig,
  pingConnection,
  testLLMConfig,
} from "@/lib/api";
import { getLLMApiKey } from "@/lib/api-keys";
import { KindBadge } from "@/components/shell/KindBadge";
import { Button } from "@/components/ui/button";
import type { MCPKind } from "@/lib/types";

type CheckStatus = "loading" | "ok" | "warn" | "error";

type Check = {
  id: string;
  title: string;
  status: CheckStatus;
  message: string;
  hint?: string;
  /** Опциональные UI-расширения для конкретных строк диагностики. */
  kind?: MCPKind;
  tools?: string[];
};

export default function StatusPage() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [running, setRunning] = useState(false);

  async function runChecks() {
    setRunning(true);

    const results: Check[] = [];

    // 1. Сервер приложения
    try {
      const h = await fetchHealth();
      results.push({
        id: "backend",
        title: "Сервер приложения",
        status: "ok",
        message: `OK · версия ${h.version} · БД ${h.db}`,
      });
    } catch {
      results.push({
        id: "backend",
        title: "Сервер приложения",
        status: "error",
        message: "Не отвечает",
        hint: "Перезапустите приложение «1С Аналитик» — фоновый сервер не отвечает.",
      });
      setChecks([...results, ...placeholderRest()]);
      setRunning(false);
      return;
    }

    // 2. Базы 1С — основные MCP подключения
    let connections: Awaited<ReturnType<typeof fetchConnections>> = [];
    try {
      connections = await fetchConnections();
    } catch {
      results.push({
        id: "connections",
        title: "Базы 1С",
        status: "error",
        message: "Не удалось получить список",
      });
    }

    if (connections.length === 0) {
      results.push({
        id: "connections",
        title: "База 1С",
        status: "warn",
        message: "Подключений нет",
        hint: "Откройте Настройки и добавьте адрес вашей базы 1С.",
      });
    } else {
      for (const conn of connections) {
        try {
          const ping = await pingConnection(conn.id);
          const tools = ping.tool_names ?? [];
          const kindLabel = conn.kind === "proxy" ? "Прокси" : "Локально";
          const channelInfo =
            conn.kind === "proxy" && conn.channel
              ? ` · канал ${conn.channel}`
              : "";
          results.push({
            id: `mcp-${conn.id}`,
            title: `База «${conn.name}»`,
            status: "ok",
            message: `OK · ${kindLabel}${channelInfo} · ${ping.tool_count} инструментов · ${conn.endpoint}`,
            kind: conn.kind,
            tools,
          });
        } catch (e) {
          const hint =
            conn.kind === "proxy"
              ? `Проверьте, что обработка MCP_Toolkit запущена на сервере и канал «${conn.channel ?? "?"}» включён.`
              : `В 1С на этом компьютере откройте обработку MCP_Toolkit и нажмите «Запустить». Адрес: ${conn.endpoint}`;
          results.push({
            id: `mcp-${conn.id}`,
            title: `База «${conn.name}»`,
            status: "error",
            message: e instanceof Error ? e.message : "Не отвечает",
            hint,
            kind: conn.kind,
          });
        }
      }
    }

    // 3. Aux MCP — справочник BSL и др.
    try {
      const aux = await fetchAuxDiagnostics();
      for (const item of aux.aux) {
        if (item.status === "ok") {
          results.push({
            id: `aux-${item.name}`,
            title: titleForAux(item.name),
            status: "ok",
            message: `OK · ${item.tool_count} инструментов`,
          });
        } else if (item.status === "not_configured") {
          results.push({
            id: `aux-${item.name}`,
            title: titleForAux(item.name),
            status: "warn",
            message: "Не подключён (опционально)",
            hint: item.error_hint ?? undefined,
          });
        } else {
          results.push({
            id: `aux-${item.name}`,
            title: titleForAux(item.name),
            status: "error",
            message: "Не запускается",
            hint: item.error_hint ?? undefined,
          });
        }
      }
    } catch {
      // Старый backend без /diagnostics/aux — секцию просто не показываем
    }

    // 4. LLM config
    let llmConfig: Awaited<ReturnType<typeof fetchLLMConfig>> = null;
    try {
      llmConfig = await fetchLLMConfig();
    } catch {
      /* swallow */
    }

    if (!llmConfig) {
      results.push({
        id: "llm-config",
        title: "Модель ИИ",
        status: "warn",
        message: "Не настроена",
        hint: "Откройте Настройки и введите API ключ.",
      });
    } else {
      const apiKey = getLLMApiKey();
      if (!apiKey) {
        results.push({
          id: "llm-config",
          title: "Модель ИИ",
          status: "warn",
          message: `Адрес настроен (${llmConfig.endpoint}), но API ключ не введён`,
          hint: "Введите API ключ в Настройках — ключ хранится локально, по сети не передаётся.",
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
              title: "Модель ИИ",
              status: "ok",
              message: `OK · ${llmConfig.endpoint} · модель ${llmConfig.model}`,
            });
          } else {
            results.push({
              id: "llm-config",
              title: "Модель ИИ",
              status: "error",
              message: t.error_code === "invalid_key" ? "Неверный API ключ" : (t.error_code ?? "Ошибка"),
              hint: "Проверьте API ключ и адрес в Настройках.",
            });
          }
        } catch (e) {
          results.push({
            id: "llm-config",
            title: "Модель ИИ",
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
          <strong>Сервер приложения</strong> — внутренний процесс, который связывает чат, базу 1С
          и модель ИИ. Стартует автоматически вместе с приложением.
        </p>
        <p>
          <strong>База 1С</strong> — ваша рабочая база. К ней приложение обращается через специальную
          обработку, запущенную в самой 1С (ставит ИТ-отдел). Два режима: «Локально» — обработка
          на вашем компьютере; «Прокси» — на сервере, доступ через интернет.
        </p>
        <p>
          <strong>Справочник BSL</strong> — внутренний справочник по встроенным функциям 1С.
          Опционально. Помогает модели точнее называть методы платформы.
        </p>
        <p>
          <strong>Модель ИИ</strong> — внешний сервис (Xiaomi MiMo, OpenAI и т.п.), который читает
          ваши вопросы и решает, какие данные из 1С достать.
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
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-[var(--fg)]">{check.title}</span>
            {check.kind && <KindBadge kind={check.kind} />}
          </div>
          <div className="text-xs text-[var(--fg-muted)] mt-1 font-mono break-words">
            {check.message}
          </div>
          {check.tools && check.tools.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {check.tools.slice(0, 8).map((name) => (
                <span
                  key={name}
                  className="text-[10px] font-mono px-1.5 py-px rounded border border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-2)]"
                >
                  {name}
                </span>
              ))}
              {check.tools.length > 8 && (
                <span className="text-[10px] text-[var(--fg-3)] px-1">
                  +{check.tools.length - 8}
                </span>
              )}
            </div>
          )}
          {check.hint && (
            <div className="text-xs text-blue-400 mt-2">→ {check.hint}</div>
          )}
        </div>
      </div>
    </div>
  );
}

function titleForAux(name: string): string {
  switch (name) {
    case "bsl-context":
      return "Справочник BSL";
    default:
      return name;
  }
}

function placeholderRest(): Check[] {
  return [
    {
      id: "connections-skip",
      title: "База 1С",
      status: "warn" as const,
      message: "Проверка пропущена — сервер приложения не отвечает.",
    },
    {
      id: "llm-skip",
      title: "Модель ИИ",
      status: "warn" as const,
      message: "Проверка пропущена — сервер приложения не отвечает.",
    },
  ];
}
