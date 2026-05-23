"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/FieldError";
import { createConnection, updateConnection, pingConnection } from "@/lib/api";
import { mcpConnectionSchema } from "@/lib/form-schemas";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { MCPConnection, MCPKind } from "@/lib/types";

interface MCPConnectionFormProps {
  initial?: MCPConnection | null;
  onSaved: (conn: MCPConnection) => void;
  onCancel?: () => void;
}

// Дефолты, к которым аналитик не должен подходить руками.
// Встроенный сервер EPF MCP_Toolkit по умолчанию слушает 6010 — это наш канон.
const DEFAULT_EMBEDDED_HOST = "localhost";
const DEFAULT_EMBEDDED_PORT = "6010";
// Прокси-сервер user-specific (HF Spaces у Khvorostov). Аналитик может оставить
// дефолт или подменить, если у конторы свой прокси.
const DEFAULT_PROXY_BASE = "https://nikoiuy12-mcp-proxy.hf.space/mcp";

/**
 * Парсит существующий endpoint обратно в (kind, host, port, channel, proxyBase),
 * чтобы при редактировании показать те же поля, которыми его создавали.
 */
function parseEndpoint(
  endpoint: string,
  kindHint: MCPKind | undefined,
): { kind: MCPKind; host: string; port: string; channel: string; proxyBase: string } {
  try {
    const u = new URL(endpoint);
    const channel = u.searchParams.get("channel") ?? "";
    const isProxy =
      kindHint === "proxy" ||
      channel !== "" ||
      u.hostname.includes("proxy") ||
      u.protocol === "https:";
    if (isProxy) {
      const base = `${u.protocol}//${u.host}${u.pathname}`;
      return {
        kind: "proxy",
        host: DEFAULT_EMBEDDED_HOST,
        port: DEFAULT_EMBEDDED_PORT,
        channel,
        proxyBase: base,
      };
    }
    return {
      kind: "embedded",
      host: u.hostname || DEFAULT_EMBEDDED_HOST,
      port: u.port || DEFAULT_EMBEDDED_PORT,
      channel: "",
      proxyBase: DEFAULT_PROXY_BASE,
    };
  } catch {
    return {
      kind: kindHint ?? "embedded",
      host: DEFAULT_EMBEDDED_HOST,
      port: DEFAULT_EMBEDDED_PORT,
      channel: "",
      proxyBase: DEFAULT_PROXY_BASE,
    };
  }
}

function buildEndpoint(args: {
  kind: MCPKind;
  host: string;
  port: string;
  channel: string;
  proxyBase: string;
}): string {
  if (args.kind === "embedded") {
    const host = args.host.trim() || DEFAULT_EMBEDDED_HOST;
    const port = args.port.trim() || DEFAULT_EMBEDDED_PORT;
    return `http://${host}:${port}/mcp`;
  }
  const base = (args.proxyBase.trim() || DEFAULT_PROXY_BASE).replace(/\?.*$/, "");
  const channel = encodeURIComponent(args.channel.trim());
  return `${base}?channel=${channel}`;
}

export function MCPConnectionForm({
  initial,
  onSaved,
  onCancel,
}: MCPConnectionFormProps) {
  const parsed = useMemo(
    () =>
      initial
        ? parseEndpoint(initial.endpoint, initial.kind)
        : {
            kind: "embedded" as MCPKind,
            host: DEFAULT_EMBEDDED_HOST,
            port: DEFAULT_EMBEDDED_PORT,
            channel: "",
            proxyBase: DEFAULT_PROXY_BASE,
          },
    [initial],
  );

  const [name, setName] = useState(initial?.name ?? "Моя база");
  const [kind, setKind] = useState<MCPKind>(parsed.kind);
  const [port, setPort] = useState(parsed.port);
  const [channel, setChannel] = useState(parsed.channel);
  const [proxyBase, setProxyBase] = useState(parsed.proxyBase);
  const [anonEnabled, setAnonEnabled] = useState(initial?.anon_enabled ?? false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  // Advanced раскрывается автоматически, если редактируется proxy-подключение —
  // там поля для канала и адреса прокси.
  const [advancedOpen, setAdvancedOpen] = useState(parsed.kind === "proxy");

  const computedEndpoint = useMemo(
    () =>
      buildEndpoint({
        kind,
        host: DEFAULT_EMBEDDED_HOST,
        port,
        channel,
        proxyBase,
      }),
    [kind, port, channel, proxyBase],
  );

  function isValidUrl(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  async function handleSave() {
    const result = mcpConnectionSchema.safeParse({
      name,
      endpoint: computedEndpoint,
      channel: kind === "proxy" ? channel : undefined,
      anon_enabled: anonEnabled,
      kind,
    });

    if (!result.success) {
      const fieldErrors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const field = issue.path[0] as string;
        if (field && !fieldErrors[field]) {
          fieldErrors[field] = issue.message;
        }
      }
      setErrors(fieldErrors);
      // Если ошибка в полях канала / прокси — раскрываем advanced чтобы пользователь увидел
      if (fieldErrors.channel || fieldErrors.endpoint) {
        setAdvancedOpen(true);
      }
      return;
    }

    setErrors({});
    setLoading(true);
    try {
      const payload = {
        name: result.data.name,
        endpoint: result.data.endpoint,
        channel: result.data.channel || undefined,
        anon_enabled: result.data.anon_enabled,
        kind: result.data.kind,
      };

      const saved = initial
        ? await updateConnection(initial.id, payload)
        : await createConnection(payload);

      publishToast({ type: "info", message: "Подключение сохранено" });
      onSaved(saved);
    } catch (err) {
      const raw = err instanceof Error ? err.message : "";
      const isDup = raw.includes("409") || raw.toLowerCase().includes("duplicate");
      const message = isDup
        ? `Подключение с адресом ${computedEndpoint} уже есть. Откройте его на редактирование.`
        : raw || "Ошибка сохранения";
      publishToast({ type: "error", message });
    } finally {
      setLoading(false);
    }
  }

  async function handleTest() {
    if (!initial?.id) {
      publishToast({
        type: "warning",
        message: "Сначала сохраните, потом тестируйте",
      });
      return;
    }

    setTesting(true);
    try {
      const result = await pingConnection(initial.id);
      publishToast({
        type: "info",
        message: `База 1С отвечает · ${result.tool_count} инструментов · ${result.duration_ms} мс`,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка теста";
      publishToast({ type: "error", message });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="space-y-4 p-4 border border-[var(--border)] rounded-md bg-[var(--bg)]">
      {/* Название — единственное обязательное текстовое поле верхнего уровня. */}
      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Название
        </label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Моя база"
          maxLength={50}
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "name-error" : undefined}
        />
        <FieldError id="name-error" message={errors.name} />
      </div>

      {/* Порт встроенного сервера — главное что аналитик настраивает.
          Тип подключения по умолчанию embedded. Прокси/канал — за advanced. */}
      {kind === "embedded" && (
        <div>
          <label className="block text-xs text-[var(--fg-muted)] mb-1">
            Порт обработки в 1С
          </label>
          <Input
            value={port}
            onChange={(e) => setPort(e.target.value.replace(/[^0-9]/g, ""))}
            placeholder="6010"
            maxLength={5}
            className="font-mono"
            data-testid="port-input"
            inputMode="numeric"
          />
          <p className="text-xs text-[var(--fg-3)] mt-1">
            Тот же номер, что указан в обработке 1С на вкладке «Встроенный сервер». По умолчанию <span className="font-mono">6010</span>.
          </p>
        </div>
      )}

      {/* Маскировка имён — частая настройка, оставляем наверху. */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="anon_enabled"
          checked={anonEnabled}
          onChange={(e) => setAnonEnabled(e.target.checked)}
          className="h-4 w-4 accent-[var(--accent)]"
        />
        <label
          htmlFor="anon_enabled"
          className="text-sm text-[var(--fg-muted)] cursor-pointer"
        >
          Маскировка имён по умолчанию
        </label>
      </div>

      {/* Расширенные — тип подключения, прокси, базовый адрес. */}
      <div className="border-t border-[var(--bd-1)] pt-3">
        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors"
          aria-expanded={advancedOpen}
        >
          {advancedOpen ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          <span>Расширенные настройки</span>
        </button>

        {advancedOpen && (
          <div className="space-y-4 mt-3 pl-4 border-l border-[var(--bd-1)]">
            <div>
              <label className="block text-xs text-[var(--fg-muted)] mb-2">
                Тип подключения
              </label>
              <div
                className="flex gap-2"
                role="radiogroup"
                aria-label="Тип подключения"
              >
                <KindCard
                  checked={kind === "embedded"}
                  title="Встроенный сервер"
                  description="Обработка-обработчик запущена на этом компьютере"
                  onSelect={() => setKind("embedded")}
                  data-testid="kind-embedded"
                />
                <KindCard
                  checked={kind === "proxy"}
                  title="Прокси"
                  description="Обработка на сервере, доступ через интернет"
                  onSelect={() => setKind("proxy")}
                  data-testid="kind-proxy"
                />
              </div>
            </div>

            {kind === "proxy" && (
              <>
                <div>
                  <label className="block text-xs text-[var(--fg-muted)] mb-1">
                    Профиль (для прокси)
                  </label>
                  <Input
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    placeholder="tranzit-prod"
                    maxLength={60}
                    className="font-mono"
                    data-testid="channel-input"
                    aria-invalid={!!errors.channel}
                    aria-describedby={errors.channel ? "channel-error" : "channel-hint"}
                  />
                  {errors.channel ? (
                    <FieldError id="channel-error" message={errors.channel} />
                  ) : (
                    <p id="channel-hint" className="text-xs text-[var(--fg-3)] mt-1">
                      Идентификатор, под которым прокси-шлюз отдаёт ваше подключение.
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-xs text-[var(--fg-muted)] mb-1">
                    Адрес прокси-сервера
                  </label>
                  <Input
                    value={proxyBase}
                    onChange={(e) => setProxyBase(e.target.value)}
                    placeholder={DEFAULT_PROXY_BASE}
                    className="font-mono text-[11px]"
                    data-testid="proxy-base-input"
                  />
                  <p className="text-xs text-[var(--fg-3)] mt-1">
                    По умолчанию — публичный прокси. Поменяйте, если у компании свой.
                  </p>
                </div>
              </>
            )}

            {/* Превью URL — только в advanced. На основном экране техника не нужна. */}
            <div className="text-xs text-[var(--fg-3)] bg-[var(--bg-elevated)] border border-[var(--border)] rounded p-2 font-mono break-all">
              Адрес: {computedEndpoint || "—"}
            </div>
            <FieldError message={errors.endpoint} />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleTest}
          disabled={!initial?.id || testing || !isValidUrl(computedEndpoint)}
          // HIGH-7 (2026-05-24): tooltip объясняет почему «Тест» disabled.
          // Браузер сам рендерит native tooltip из title attribute.
          title={
            !initial?.id
              ? "Сначала сохраните подключение, потом тестируйте"
              : !isValidUrl(computedEndpoint)
                ? "Невалидный адрес — проверьте поля выше"
                : undefined
          }
        >
          {testing ? "Тестирование..." : "Тест"}
        </Button>
        <Button size="sm" onClick={handleSave} disabled={loading}>
          {loading ? "Сохранение..." : "Сохранить"}
        </Button>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Отмена
          </Button>
        )}
      </div>
    </div>
  );
}

interface KindCardProps {
  checked: boolean;
  title: string;
  description: string;
  onSelect: () => void;
  "data-testid"?: string;
}

function KindCard({
  checked,
  title,
  description,
  onSelect,
  "data-testid": testId,
}: KindCardProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      onClick={onSelect}
      data-testid={testId}
      className={cn(
        // HIGH-8 (2026-05-24): min-h-[88px] чтобы карточки не «прыгали» по
        // высоте между «embedded» (1 строка description) и «proxy» (2 строки).
        "flex-1 text-left p-3 rounded-md border transition-colors min-h-[88px]",
        checked
          ? "border-[var(--accent)] bg-[var(--accent-08)]"
          : "border-[var(--border)] bg-[var(--bg)] hover:border-[var(--bd-3)]",
      )}
    >
      <div className="flex items-start gap-2">
        <div
          className={cn(
            "mt-0.5 h-4 w-4 rounded-full border-2 flex-none",
            checked
              ? "border-[var(--accent)] bg-[var(--accent)] ring-2 ring-[var(--accent-20)] ring-offset-0"
              : "border-[var(--bd-3)]",
          )}
          aria-hidden="true"
        />
        <div className="min-w-0">
          <div className="text-sm font-medium text-[var(--fg-1)]">{title}</div>
          <div className="text-[11px] text-[var(--fg-3)] mt-0.5 leading-snug">
            {description}
          </div>
        </div>
      </div>
    </button>
  );
}
