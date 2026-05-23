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
  fetchLogPath,
  getBackendUrl,
  pingConnection,
  testLLMConfig,
} from "@/lib/api";
import type { LogPathResponse } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import { getLLMApiKey } from "@/lib/api-keys";
import { KindBadge } from "@/components/shell/KindBadge";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/CopyButton";
import { cn } from "@/lib/utils";
import { describeMcpTool } from "@/lib/mcp-tool-descriptions";
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

/**
 * Sprint 03 (handoff 06 · Status split): высокоуровневая карточка состояния.
 * Показывает один из трёх блоков (Базы / Модель / Серверная часть) — большой
 * номер/имя сверху, мелкая мета снизу, цвет точки соответствует статусу.
 */
interface StatusCardProps {
  label: string;
  state: CheckStatus;
  headline: string;
  subtitle: string;
}

function StatusCard({ label, state, headline, subtitle }: StatusCardProps) {
  const stateClasses: Record<CheckStatus, string> = {
    loading: "text-[var(--fg-3)]",
    ok: "text-[var(--success)]",
    warn: "text-[var(--warning)]",
    error: "text-[var(--error)]",
  };
  return (
    <div className="rounded-lg bg-[var(--bg-elevated)] border border-[var(--border)] p-4">
      <div
        className={cn(
          "text-[10px] tracking-[0.16em] uppercase mb-2 flex items-center gap-1.5",
          stateClasses[state],
        )}
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        {label}
      </div>
      <div
        className="font-semibold text-base leading-tight text-[var(--fg-1)] truncate"
        style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
      >
        {headline}
      </div>
      <div className="text-xs text-[var(--fg-3)] mt-1 truncate">{subtitle}</div>
    </div>
  );
}

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
  const [logInfo, setLogInfo] = useState<LogPathResponse | null>(null);
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

    // Лог-файл — для кнопки «Открыть папку с логами». На старом backend
    // (< v1.2.13) endpoint отсутствует → просто не показываем секцию.
    let logResp: LogPathResponse | null = null;
    try {
      logResp = await fetchLogPath();
    } catch {
      logResp = null;
    }
    setLogInfo(logResp);

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

  // Sprint 03 (handoff 06 · Status split): агрегируем все checks в 3 верхнеуровневые
  // карточки. «Базы 1С» (все mcp-*), «Модель ИИ» (llm-config), «Серверная часть»
  // (backend + bsl-context aux). Технические детали уезжают в <details>.
  const highLevelCards = aggregateCards(checks);

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
        <div className="ml-auto flex items-center gap-2">
          <Button
            onClick={() => void runChecks()}
            variant="secondary"
            disabled={running}
            className="gap-2"
          >
            <RefreshCw size={14} className={running ? "animate-spin" : ""} />
            {running ? "Проверяем..." : "Обновить"}
          </Button>
          <ThemeToggle />
        </div>
      </div>

      {checks.length > 0 && (
        <div
          className={`mb-6 p-4 rounded-lg border ${
            allOk
              ? "border-[var(--success-40)] bg-[var(--success-12)]"
              : anyError
                ? "border-[var(--error-40)] bg-[var(--error-12)]"
                : "border-[var(--warning-40)] bg-[var(--warning-12)]"
          }`}
        >
          <p className="text-sm">
            {allOk && (
              <span className="text-[var(--success)]">
                ✓ Всё работает. Можно задавать вопросы на главной странице.
              </span>
            )}
            {anyError && (
              <span className="text-[var(--error)]">
                ✗ Найдены проблемы. Раскройте «Технические подробности» — там детали и подсказки по исправлению.
              </span>
            )}
            {!allOk && !anyError && (
              <span className="text-[var(--warning)]">
                ⚠ Есть незавершённые настройки. Раскройте «Технические подробности».
              </span>
            )}
          </p>
        </div>
      )}

      {/* Sprint 03 (handoff 06 · Status split): высокоуровневые карточки —
          самое важное, что аналитик видит без раскрытия. */}
      {checks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
          <StatusCard {...highLevelCards.bases} />
          <StatusCard {...highLevelCards.llm} />
          <StatusCard {...highLevelCards.backend} />
        </div>
      )}

      {checks.length === 0 && (
        <div className="text-center text-[var(--fg-muted)] py-8 text-sm">
          Запускаем проверки...
        </div>
      )}

      {/* Sprint 03: технические подробности — старая раскладка CheckRow + Env + Log.
          По дефолту свёрнуто. Здесь живут endpoint URL, версии MCP, channel id —
          инфа для разработчика, не для аналитика. */}
      {checks.length > 0 && (
        <details className="border-t border-[var(--border)] pt-4 mt-2 group">
          <summary
            className="cursor-pointer text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-2 select-none list-none [&::-webkit-details-marker]:hidden"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            <ChevronRight
              size={12}
              className="transition-transform group-open:rotate-90"
              aria-hidden="true"
            />
            Технические подробности (для разработчика)
          </summary>
          <div className="mt-4 space-y-2">
            {checks.map((check) => (
              <CheckRow key={check.id} check={check} />
            ))}
            {env && (
              <div className="pt-3">
                <EnvSection env={env} />
              </div>
            )}
            {logInfo && (
              <div className="pt-3">
                <LogSection info={logInfo} />
              </div>
            )}
          </div>
        </details>
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
          <strong>Модель ИИ</strong> — внешний сервис (NVIDIA NIM с DeepSeek V4 Flash
          по умолчанию, либо Cloud.ru для 152-ФЗ, либо свой OpenAI-совместимый
          endpoint), который читает ваши вопросы и решает, какие данные из 1С достать.
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
    summary: `OK · БД ${health.db === "ok" ? "в порядке" : "ошибка"}`,
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
      { label: "Версия протокола", value: ping.mcp_version, mono: true },
      { label: "Обработка 1С", value: ping.server_name || "—" },
      { label: "Доступно операций", value: String(ping.tool_count) },
      { label: "Ответ за", value: `${ping.duration_ms} мс` },
    );
  }

  if (errorMsg) {
    const hint =
      conn.kind === "proxy"
        ? `Проверьте, что обработка-мост запущена на сервере и канал «${channel || "?"}» включён.`
        : `В 1С на этом компьютере откройте обработку-мост и нажмите «Запустить». Адрес: ${conn.endpoint}`;
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
    summary: `OK · ${kindLabel}${channelInfo} · ${ping?.tool_count ?? 0} инструментов`,
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
  // env-fallback: backend получает ключ из embedded.env (NVIDIA NIM зашит в дистрибутиве).
  // Если has_env_api_key=true — у нас есть рабочий ключ, даже если localStorage пуст.
  const hasEnvKey = Boolean(llmConfig?.has_env_api_key);
  const hasKey = Boolean(apiKey) || hasEnvKey;

  if (!llmConfig) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "warn",
      summary: "Не настроена",
      hint: "Откройте Настройки и введите API ключ.",
    };
  }

  const keyDescription = apiKey
    ? "Введён · хранится локально, по сети не передаётся"
    : hasEnvKey
      ? "Задан в .env сервера · зашит в дистрибутиве"
      : "Не введён";

  const fields: FieldRow[] = [
    { label: "Модель", value: llmConfig.model, copy: true, mono: true },
    { label: "Температура", value: String(llmConfig.temperature) },
    { label: "API-ключ", value: keyDescription },
  ];
  if (llmConfig.updated_at) {
    fields.push({ label: "Обновлён", value: formatDate(llmConfig.updated_at) });
  }

  if (!hasKey) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "warn",
      summary: "API ключ не введён",
      hint: "Введите API ключ в Настройках — ключ хранится локально, по сети не передаётся.",
      fields,
    };
  }

  // Если ключ только из .env (не от пользователя) — пропускаем real test (backend
  // /llm-config/test ждёт ключ в header, env-fallback там нет). Чат всё равно
  // отработает через /chat/stream который умеет env-fallback.
  if (!apiKey && hasEnvKey) {
    return {
      id: "llm-config",
      title: "Модель ИИ",
      status: "ok",
      summary: `OK · модель ${llmConfig.model} · ключ из .env`,
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
      apiKey ?? "",
    );
    if (t.ok) {
      fields.push({ label: "Последний тест", value: `Успешно · ${t.duration_ms ?? 0} мс` });
      return {
        id: "llm-config",
        title: "Модель ИИ",
        status: "ok",
        summary: `OK · модель ${llmConfig.model}`,
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
    ? "text-[var(--success)]"
    : check.status === "error"
      ? "text-[var(--error)]"
      : check.status === "warn"
        ? "text-[var(--warning)]"
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
            <div className="text-xs text-[var(--accent)] mt-2">→ {check.hint}</div>
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
                    title={`${name}: ${describeMcpTool(name)}`}
                    className="text-[10px] font-mono px-1.5 py-px rounded border border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-2)] cursor-help"
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

/**
 * Блок «Лог-файл» — путь к backend.log + кнопка «Открыть папку». Самый
 * частый use-case: коллега ловит баг, мы просим прислать backend.log.
 * Без кнопки путь в %LOCALAPPDATA% коллеге найти трудно — отсюда IPC
 * в Electron (preload: window.electronAPI.openPath).
 */
function LogSection({ info }: { info: LogPathResponse }) {
  const [open, setOpen] = useState(false);

  // window.electronAPI пробрасывается через preload.js. В браузерном dev-режиме
  // его нет — кнопка просто не рендерится, остаётся только путь с copy.
  type ElectronAPI = { openPath?: (target: string) => Promise<string> };
  const electronAPI =
    typeof window !== "undefined"
      ? ((window as unknown as { electronAPI?: ElectronAPI }).electronAPI ?? null)
      : null;

  async function handleOpen() {
    if (!electronAPI?.openPath) return;
    const result = await electronAPI.openPath(info.log_dir);
    if (result) {
      publishToast({
        type: "error",
        message: `Не удалось открыть папку: ${result}`,
      });
    }
  }

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
          <div className="font-medium text-sm text-[var(--fg)]">Лог-файл backend</div>
          <div className="text-xs text-[var(--fg-muted)] mt-1">
            {info.exists
              ? "Журнал работы приложения. Пришли этот файл если что-то сломалось — поможет разобраться."
              : "Логи будут писаться сюда — файл появится после первой записи."}
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
        <div className="border-t border-[var(--border)] px-4 py-3 space-y-3">
          <FieldKV
            field={{
              label: "Папка",
              value: info.log_dir,
              copy: true,
              mono: true,
            }}
          />
          <FieldKV
            field={{
              label: "Файл",
              value: info.log_file,
              copy: true,
              mono: true,
              hint: info.exists
                ? "Существует — можно открыть и прислать"
                : "Пока пустой — будет создан при следующей записи",
            }}
          />
          {electronAPI?.openPath && (
            <Button size="sm" variant="secondary" onClick={() => void handleOpen()}>
              Открыть папку
            </Button>
          )}
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

/**
 * Sprint 03: агрегирует низкоуровневые checks в 3 high-level cards.
 *
 * - «Базы 1С»: статус = worst(connection checks); headline = «N из M»;
 *   subtitle = краткие имена через · (макс 3, остальные →«и ещё X»).
 * - «Модель ИИ»: ровно один llm-config check; headline = model name;
 *   subtitle = последний тест / API-ключ.
 * - «Серверная часть»: backend + aux bsl-context; headline = версия;
 *   subtitle = БД + кол-во записей где-то.
 */
function aggregateCards(checks: Check[]): {
  bases: StatusCardProps;
  llm: StatusCardProps;
  backend: StatusCardProps;
} {
  const bases = aggregateBases(checks);
  const llm = aggregateLlm(checks);
  const backend = aggregateBackend(checks);
  return { bases, llm, backend };
}

function aggregateBases(checks: Check[]): StatusCardProps {
  const mcpChecks = checks.filter((c) => c.id.startsWith("mcp-"));
  const empty = checks.find((c) => c.id === "connections-empty");
  if (empty) {
    return {
      label: "Базы 1С",
      state: "warn",
      headline: "0 из 0",
      subtitle: "подключений ещё нет",
    };
  }
  if (mcpChecks.length === 0) {
    return {
      label: "Базы 1С",
      state: "loading",
      headline: "—",
      subtitle: "проверяю...",
    };
  }
  const okCount = mcpChecks.filter((c) => c.status === "ok").length;
  const total = mcpChecks.length;
  const state: CheckStatus =
    okCount === total ? "ok" : okCount === 0 ? "error" : "warn";
  const names = mcpChecks
    .map((c) => c.title.replace(/^База «(.+)»$/, "$1"))
    .slice(0, 3);
  const extras = mcpChecks.length - names.length;
  const subtitle =
    names.join(" · ") + (extras > 0 ? ` · и ещё ${extras}` : "");
  return {
    label: "Базы 1С",
    state,
    headline: `${okCount} из ${total}`,
    subtitle,
  };
}

function aggregateLlm(checks: Check[]): StatusCardProps {
  const llm = checks.find((c) => c.id === "llm-config");
  if (!llm) {
    return {
      label: "Модель ИИ",
      state: "loading",
      headline: "—",
      subtitle: "проверяю...",
    };
  }
  // Из summary вытаскиваем имя модели если есть.
  const modelMatch = llm.summary.match(/модель\s+(\S+)/i);
  const headline = modelMatch ? (modelMatch[1] ?? "—") : "—";
  // Время отклика — из fields «Последний тест»
  const lastTest = llm.fields?.find((f) => f.label === "Последний тест");
  let subtitle = "";
  if (lastTest) {
    subtitle = lastTest.value;
  } else if (llm.status === "warn") {
    subtitle = llm.summary;
  } else if (llm.status === "error") {
    subtitle = llm.summary;
  } else {
    subtitle = "связь установлена";
  }
  return {
    label: "Модель ИИ",
    state: llm.status === "loading" ? "loading" : llm.status,
    headline,
    subtitle,
  };
}

function aggregateBackend(checks: Check[]): StatusCardProps {
  const backend = checks.find((c) => c.id === "backend");
  if (!backend) {
    return {
      label: "Серверная часть",
      state: "loading",
      headline: "—",
      subtitle: "проверяю...",
    };
  }
  const versionField = backend.fields?.find((f) => f.label === "Версия");
  const dbField = backend.fields?.find((f) => f.label === "База данных");
  const headline = versionField ? `v${versionField.value}` : "—";
  const subtitle = dbField
    ? `База данных · ${dbField.value.toLowerCase()}`
    : backend.summary;
  return {
    label: "Серверная часть",
    state: backend.status === "loading" ? "loading" : backend.status,
    headline,
    subtitle,
  };
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
