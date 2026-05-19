"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  HelpCircle,
  RefreshCw,
  XCircle,
} from "lucide-react";
import {
  fetchAuxDiagnostics,
  fetchHealth,
  fetchConnections,
  fetchEnvDiagnostics,
  fetchLLMConfig,
  getBackendUrl,
  pingConnection,
  testLLMConfig,
} from "@/lib/api";
import { getLLMApiKey } from "@/lib/api-keys";
import { KindBadge } from "@/components/shell/KindBadge";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/CopyButton";
import { cn } from "@/lib/utils";
import type {
  AuxMCPStatus,
  EnvDiagnosticsResponse,
  HealthResponse,
  LLMConfigResponse,
  MCPConnection,
  MCPKind,
  MCPPingResponse,
} from "@/lib/types";

type CheckStatus = "loading" | "ok" | "warn" | "error";

interface FieldRow {
  label: string;
  value: string;
  copy?: boolean;
  hint?: string;
  mono?: boolean;
}

interface Check {
  id: string;
  title: string;
  status: CheckStatus;
  summary: string;
  hint?: string;
  kind?: MCPKind;
  /** Подробные параметры (ключ → значение), раскрываются по клику. */
  fields?: FieldRow[];
  /** Чипы — для tool_names. */
  chips?: string[];
}

export default function StatusPage() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [env, setEnv] = useState<EnvDiagnosticsResponse | null>(null);
  const [running, setRunning] = useState(false);

  async function runChecks() {
    setRunning(true);
    const results: Check[] = [];

    // 1. Сервер приложения + env
    let health: HealthResponse | null = null;
    try {
      health = await fetchHealth();
    } catch {
      results.push({
        id: "backend",
        title: "Сервер приложения",
        status: "error",
        summary: "Не отвечает",
        hint: "Перезапустите приложение «1С Аналитик» — фоновый сервер не отвечает.",
      });
      setChecks([...results, ...placeholderRest()]);
      setRunning(false);
      return;
    }

    let envInfo: EnvDiagnosticsResponse | null = null;
    try {
      envInfo = await fetchEnvDiagnostics();
    } catch {
      envInfo = null;
    }
    setEnv(envInfo);

    results.push(backendCheck(health, envInfo));

    // 2. Базы 1С
    let connections: MCPConnection[] = [];
    try {
      connections = await fetchConnections();
    } catch {
      results.push({
        id: "connections-error",
        title: "Базы 1С",
        status: "error",
        summary: "Не удалось получить список",
      });
    }

    if (connections.length === 0) {
      results.push({
        id: "connections-empty",
        title: "База 1С",
        status: "warn",
        summary: "Подключений нет",
        hint: "Откройте Настройки и добавьте адрес вашей базы 1С.",
      });
    } else {
      for (const conn of connections) {
        results.push(await mcpConnectionCheck(conn));
      }
    }

    // 3. Aux MCP
    try {
      const aux = await fetchAuxDiagnostics();
      for (const item of aux.aux) {
        results.push(auxCheck(item, envInfo));
      }
    } catch {
      // старый backend без /diagnostics/aux — секцию скрываем
    }

    // 4. LLM
    let llmConfig: LLMConfigResponse | null = null;
    try {
      llmConfig = await fetchLLMConfig();
    } catch {
      llmConfig = null;
    }
    results.push(await llmCheck(llmConfig));

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
                ✗ Найдены проблемы. Раскройте строки ниже — там детали и подсказки по исправлению.
              </span>
            )}
            {!allOk && !anyError && (
              <span className="text-yellow-400">
                ⚠ Есть незавершённые настройки. Раскройте строки ниже.
              </span>
            )}
          </p>
        </div>
      )}

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

      {env && (
        <div className="mt-6">
          <EnvSection env={env} />
        </div>
      )}

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
        <p>
          <strong>Окружение приложения</strong> — параметры, с которыми запустился backend.
          Полезно при обращении в ИТ-отдел: можно скопировать адрес и переслать.
        </p>
      </div>
    </div>
  );
}

function backendCheck(health: HealthResponse, env: EnvDiagnosticsResponse | null): Check {
  const backendUrl = getBackendUrl();
  const fields: FieldRow[] = [
    { label: "Адрес backend", value: backendUrl, copy: true, mono: true },
    { label: "Версия", value: health.version },
    {
      label: "База данных",
      value: health.db === "ok" ? "OK" : "ошибка чтения",
    },
  ];
  if (env) {
    fields.push(
      {
        label: "Режим",
        value: env.environment === "prod" ? "production" : "разработка",
      },
      {
        label: "Файл SQLite",
        value: env.sqlite_path,
        copy: true,
        mono: true,
      },
      {
        label: "Разрешённые источники (CORS)",
        value: env.cors_origins.length > 0 ? env.cors_origins.join(", ") : "—",
        mono: true,
      },
    );
  }
  return {
    id: "backend",
    title: "Сервер приложения",
    status: "ok",
    summary: `OK · версия ${health.version} · БД ${health.db}`,
    fields,
  };
}

async function mcpConnectionCheck(conn: MCPConnection): Promise<Check> {
  let ping: MCPPingResponse | null = null;
  let errorMsg: string | null = null;
  try {
    ping = await pingConnection(conn.id);
  } catch (e) {
    errorMsg = e instanceof Error ? e.message : "Не отвечает";
  }

  const url = new URL(conn.endpoint);
  const host = url.hostname;
  const port = url.port || (url.protocol === "https:" ? "443" : "80");
  const channel = conn.channel ?? url.searchParams.get("channel") ?? "";

  const fields: FieldRow[] = [
    {
      label: "Тип подключения",
      value: conn.kind === "proxy" ? "Прокси (обработка на сервере)" : "Локально (на этом компьютере)",
    },
    {
      label: "Полный адрес",
      value: conn.endpoint,
      copy: true,
      mono: true,
    },
  ];

  if (conn.kind === "embedded") {
    fields.push(
      { label: "Хост", value: host, copy: true, mono: true },
      { label: "Порт", value: port, copy: true, mono: true },
    );
  } else {
    const proxyBase = `${url.protocol}//${url.host}${url.pathname}`;
    fields.push(
      { label: "Адрес прокси-сервера", value: proxyBase, copy: true, mono: true },
      { label: "Канал", value: channel || "—", copy: !!channel, mono: true },
    );
  }

  fields.push({
    label: "Маскировка имён",
    value: conn.anon_enabled ? "Включена" : "Выключена",
  });

  if (conn.last_seen_at) {
    fields.push({
      label: "Последний успешный пинг",
      value: formatDate(conn.last_seen_at),
    });
  }

  if (ping) {
    fields.push(
      { label: "Версия MCP", value: ping.mcp_version, mono: true },
      { label: "Сервер MCP", value: ping.server_name || "—" },
      { label: "Количество инструментов", value: String(ping.tool_count) },
      { label: "Ответ за", value: `${ping.duration_ms} мс` },
    );
  }

  if (errorMsg) {
    const hint =
      conn.kind === "proxy"
        ? `Проверьте, что обработка MCP_Toolkit запущена на сервере и канал «${channel || "?"}» включён.`
        : `В 1С на этом компьютере откройте обработку MCP_Toolkit и нажмите «Запустить». Адрес: ${conn.endpoint}`;
    return {
      id: `mcp-${conn.id}`,
      title: `База «${conn.name}»`,
      status: "error",
      summary: errorMsg,
      hint,
      kind: conn.kind,
      fields,
    };
  }

  const kindLabel = conn.kind === "proxy" ? "Прокси" : "Локально";
  const channelInfo = conn.kind === "proxy" && channel ? ` · канал ${channel}` : "";
  return {
    id: `mcp-${conn.id}`,
    title: `База «${conn.name}»`,
    status: "ok",
    summary: `OK · ${kindLabel}${channelInfo} · ${ping?.tool_count ?? 0} инструментов · ${conn.endpoint}`,
    kind: conn.kind,
    fields,
    chips: ping?.tool_names ?? [],
  };
}

function auxCheck(item: AuxMCPStatus, env: EnvDiagnosticsResponse | null): Check {
  const fields: FieldRow[] = [];
  if (env && item.name === "bsl-context") {
    fields.push(
      {
        label: "Путь к JAR",
        value: env.bsl_context_jar || "(не задан) — env BSL_CONTEXT_JAR_PATH",
        copy: !!env.bsl_context_jar,
        mono: true,
      },
      {
        label: "Java",
        value: env.bsl_context_java,
        copy: true,
        mono: true,
      },
      {
        label: "Путь к платформе 1С",
        value:
          env.bsl_context_platform_path ||
          "(не задан) — env BSL_CONTEXT_PLATFORM_PATH",
        copy: !!env.bsl_context_platform_path,
        mono: true,
      },
    );
  }
  if (item.tool_count > 0) {
    fields.push({ label: "Количество инструментов", value: String(item.tool_count) });
  }

  if (item.status === "ok") {
    return {
      id: `aux-${item.name}`,
      title: titleForAux(item.name),
      status: "ok",
      summary: `OK · ${item.tool_count} инструментов`,
      fields,
    };
  }
  if (item.status === "not_configured") {
    return {
      id: `aux-${item.name}`,
      title: titleForAux(item.name),
      status: "warn",
      summary: "Не подключён (опционально)",
      hint: item.error_hint ?? undefined,
      fields,
    };
  }
  return {
    id: `aux-${item.name}`,
    title: titleForAux(item.name),
    status: "error",
    summary: "Не запускается",
    hint: item.error_hint ?? undefined,
    fields,
  };
}

async function llmCheck(llmConfig: LLMConfigResponse | null): Promise<Check> {
  const apiKey = getLLMApiKey();
  if (!llmConfig) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "warn",
      summary: "Не настроена",
      hint: "Откройте Настройки и введите API ключ.",
    };
  }

  const fields: FieldRow[] = [
    { label: "Адрес сервиса", value: llmConfig.endpoint, copy: true, mono: true },
    { label: "Модель", value: llmConfig.model, copy: true, mono: true },
    { label: "Температура", value: String(llmConfig.temperature) },
    {
      label: "API-ключ",
      value: apiKey ? "Введён · хранится локально, по сети не передаётся" : "Не введён",
    },
  ];
  if (llmConfig.updated_at) {
    fields.push({ label: "Обновлён", value: formatDate(llmConfig.updated_at) });
  }

  if (!apiKey) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "warn",
      summary: `Адрес настроен (${llmConfig.endpoint}), но API ключ не введён`,
      hint: "Введите API ключ в Настройках — ключ хранится локально, по сети не передаётся.",
      fields,
    };
  }

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
      fields.push({ label: "Последний тест", value: `Успешно · ${t.duration_ms ?? 0} мс` });
      return {
        id: "llm-config",
        title: "Модель ИИ",
        status: "ok",
        summary: `OK · ${llmConfig.endpoint} · модель ${llmConfig.model}`,
        fields,
      };
    }
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "error",
      summary: t.error_code === "invalid_key" ? "Неверный API ключ" : (t.error_code ?? "Ошибка"),
      hint: "Проверьте API ключ и адрес в Настройках.",
      fields,
    };
  } catch (e) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "error",
      summary: e instanceof Error ? e.message : "Не отвечает",
      fields,
    };
  }
}

function CheckRow({ check }: { check: Check }) {
  const [open, setOpen] = useState(false);
  const Icon = check.status === "ok"
    ? CheckCircle2
    : check.status === "error"
      ? XCircle
      : check.status === "warn"
        ? AlertCircle
        : HelpCircle;
  const iconColor = check.status === "ok"
    ? "text-green-500"
    : check.status === "error"
      ? "text-red-500"
      : check.status === "warn"
        ? "text-yellow-500"
        : "text-[var(--fg-muted)]";

  const hasDetails = (check.fields && check.fields.length > 0) || (check.chips && check.chips.length > 0);

  return (
    <div className="border border-[var(--border)] rounded-md bg-[var(--bg-elevated)]">
      <button
        type="button"
        onClick={() => hasDetails && setOpen((v) => !v)}
        className={cn(
          "w-full p-4 flex items-start gap-3 text-left",
          hasDetails ? "cursor-pointer hover:bg-[var(--bg-hover)]" : "cursor-default",
        )}
        aria-expanded={open}
        aria-disabled={!hasDetails}
      >
        <Icon className={`${iconColor} flex-none mt-0.5`} size={18} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-[var(--fg)]">{check.title}</span>
            {check.kind && <KindBadge kind={check.kind} />}
          </div>
          <div className="text-xs text-[var(--fg-muted)] mt-1 font-mono break-words">
            {check.summary}
          </div>
          {check.hint && (
            <div className="text-xs text-blue-400 mt-2">→ {check.hint}</div>
          )}
        </div>
        {hasDetails && (
          <ChevronRight
            size={16}
            className={cn(
              "flex-none mt-1 text-[var(--fg-3)] transition-transform",
              open && "rotate-90",
            )}
          />
        )}
      </button>

      {hasDetails && open && (
        <div className="border-t border-[var(--border)] px-4 py-3 space-y-2">
          {check.fields?.map((f) => (
            <FieldKV key={f.label} field={f} />
          ))}
          {check.chips && check.chips.length > 0 && (
            <div className="pt-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--fg-3)] mb-1">
                Инструменты ({check.chips.length})
              </div>
              <div className="flex flex-wrap gap-1">
                {check.chips.map((name) => (
                  <span
                    key={name}
                    className="text-[10px] font-mono px-1.5 py-px rounded border border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-2)]"
                  >
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FieldKV({ field }: { field: FieldRow }) {
  return (
    <div className="grid grid-cols-[180px_1fr_auto] gap-2 items-start text-xs">
      <div className="text-[var(--fg-3)] pt-0.5">{field.label}</div>
      <div
        className={cn(
          "min-w-0 break-words text-[var(--fg-1)]",
          field.mono && "font-mono",
        )}
      >
        {field.value}
      </div>
      {field.copy && field.value && field.value !== "—" ? (
        <CopyButton value={field.value} label={`Скопировать «${field.label}»`} />
      ) : (
        <div />
      )}
    </div>
  );
}

function EnvSection({ env }: { env: EnvDiagnosticsResponse }) {
  const [open, setOpen] = useState(false);
  const backendUrl = getBackendUrl();
  const fields: FieldRow[] = [
    { label: "Адрес backend", value: backendUrl, copy: true, mono: true },
    { label: "Версия приложения", value: env.app_version },
    {
      label: "Режим работы",
      value: env.environment === "prod" ? "production" : "разработка",
    },
    {
      label: "Файл базы (SQLite)",
      value: env.sqlite_path,
      copy: true,
      mono: true,
    },
    {
      label: "LLM по умолчанию",
      value: `${env.default_llm_endpoint} · ${env.default_llm_model}`,
      copy: true,
      mono: true,
      hint: env.env_var_names.default_llm_endpoint
        ? `Переопределить через env ${env.env_var_names.default_llm_endpoint}`
        : undefined,
    },
    {
      label: "Справочник BSL — JAR",
      value: env.bsl_context_jar || `(не задан) · env ${env.env_var_names.bsl_context_jar ?? "BSL_CONTEXT_JAR_PATH"}`,
      copy: !!env.bsl_context_jar,
      mono: true,
    },
    {
      label: "Справочник BSL — Java",
      value: env.bsl_context_java,
      copy: true,
      mono: true,
    },
    {
      label: "Справочник BSL — Платформа 1С",
      value:
        env.bsl_context_platform_path ||
        `(не задан) · env ${env.env_var_names.bsl_context_platform_path ?? "BSL_CONTEXT_PLATFORM_PATH"}`,
      copy: !!env.bsl_context_platform_path,
      mono: true,
    },
    {
      label: "Разрешённые источники (CORS)",
      value: env.cors_origins.length > 0 ? env.cors_origins.join(", ") : "—",
      mono: true,
    },
  ];

  return (
    <div className="border border-[var(--border)] rounded-md bg-[var(--bg-elevated)]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full p-4 flex items-start gap-3 text-left cursor-pointer hover:bg-[var(--bg-hover)]"
        aria-expanded={open}
      >
        <HelpCircle className="text-[var(--fg-3)] flex-none mt-0.5" size={18} />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-[var(--fg)]">Окружение приложения</div>
          <div className="text-xs text-[var(--fg-muted)] mt-1">
            Все адреса и пути, с которыми запустился backend. Скопируйте и пришлите ИТ-отделу, если что-то не работает.
          </div>
        </div>
        <ChevronRight
          size={16}
          className={cn(
            "flex-none mt-1 text-[var(--fg-3)] transition-transform",
            open && "rotate-90",
          )}
        />
      </button>
      {open && (
        <div className="border-t border-[var(--border)] px-4 py-3 space-y-2">
          {fields.map((f) => (
            <FieldKV key={f.label} field={f} />
          ))}
        </div>
      )}
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

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

function placeholderRest(): Check[] {
  return [
    {
      id: "connections-skip",
      title: "База 1С",
      status: "warn" as const,
      summary: "Проверка пропущена — сервер приложения не отвечает.",
    },
    {
      id: "llm-skip",
      title: "Модель ИИ",
      status: "warn" as const,
      summary: "Проверка пропущена — сервер приложения не отвечает.",
    },
  ];
}
