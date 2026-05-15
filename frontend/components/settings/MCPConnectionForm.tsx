"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { createConnection, updateConnection, pingConnection } from "@/lib/api";
import { mcpConnectionSchema } from "@/lib/form-schemas";
import { publishToast } from "@/lib/toast";
import type { MCPConnection } from "@/lib/types";

interface MCPConnectionFormProps {
  initial?: MCPConnection | null;
  onSaved: (conn: MCPConnection) => void;
  onCancel?: () => void;
}

export function MCPConnectionForm({
  initial,
  onSaved,
  onCancel,
}: MCPConnectionFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [endpoint, setEndpoint] = useState(initial?.endpoint ?? "");
  const [channel, setChannel] = useState(initial?.channel ?? "");
  const [anonEnabled, setAnonEnabled] = useState(
    initial?.anon_enabled ?? false,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

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
      endpoint,
      channel: channel || undefined,
      anon_enabled: anonEnabled,
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
      };

      const saved = initial
        ? await updateConnection(initial.id, payload)
        : await createConnection(payload);

      publishToast({ type: "info", message: "Подключение сохранено" });
      onSaved(saved);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка сохранения";
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
        message: `MCP работает: ${result.tool_count} инструментов, ${result.duration_ms}мс`,
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
      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Название
        </label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Транзит"
          maxLength={50}
        />
        {errors.name && (
          <p className="text-xs text-red-400 mt-1">{errors.name}</p>
        )}
      </div>

      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Endpoint
        </label>
        <Input
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="http://localhost:6010/mcp"
        />
        {errors.endpoint && (
          <p className="text-xs text-red-400 mt-1">{errors.endpoint}</p>
        )}
      </div>

      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Канал (необязательно)
        </label>
        <Input
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          placeholder="default"
          maxLength={30}
        />
        {errors.channel && (
          <p className="text-xs text-red-400 mt-1">{errors.channel}</p>
        )}
      </div>

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
          Анонимизация
        </label>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleTest}
          disabled={!initial?.id || testing || !isValidUrl(endpoint)}
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
