"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog";
import {
  saveLLMConfig,
  updateLLMConfig,
  deleteLLMConfig,
  testLLMConfig,
} from "@/lib/api";
import { llmConfigSchema } from "@/lib/form-schemas";
import { getLLMApiKey, setLLMApiKey, clearLLMApiKey } from "@/lib/api-keys";
import { publishToast } from "@/lib/toast";
import type { LLMConfigResponse } from "@/lib/types";

interface LLMConfigFormProps {
  initial: LLMConfigResponse | null;
  onSaved?: () => void;
}

function translateErrorCode(code: string | null | undefined): string {
  switch (code) {
    case "invalid_key":
      return "Неверный API ключ";
    case "network_error":
      return "Не удалось подключиться";
    case "timeout":
      return "Таймаут (10с)";
    case "server_error":
      return "Сервер LLM вернул ошибку";
    default:
      return code ?? "Неизвестная ошибка";
  }
}

export function LLMConfigForm({ initial, onSaved }: LLMConfigFormProps) {
  const storedKey = getLLMApiKey();
  const hasExisting = initial !== null;

  const [endpoint, setEndpoint] = useState(
    initial?.endpoint ?? "http://localhost:1234/v1",
  );
  const [model, setModel] = useState(initial?.model ?? "gpt-4o-mini");
  const [temperature, setTemperature] = useState(
    initial?.temperature ?? 0.3,
  );
  const [apiKey, setApiKey] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(
    !(hasExisting && storedKey),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  function getEffectiveApiKey(): string {
    if (showKeyInput) return apiKey;
    return storedKey ?? "";
  }

  function validate() {
    const effectiveKey = getEffectiveApiKey();
    const result = llmConfigSchema.safeParse({
      endpoint,
      model,
      temperature,
      api_key: effectiveKey,
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
      return null;
    }
    setErrors({});
    return result.data;
  }

  async function handleTest() {
    const data = validate();
    if (!data) return;

    setTesting(true);
    try {
      const result = await testLLMConfig(
        { endpoint: data.endpoint, model: data.model, temperature: data.temperature },
        data.api_key,
      );

      if (result.ok) {
        publishToast({
          type: "info",
          message: `LLM работает, модель: ${data.model}`,
        });
      } else {
        publishToast({
          type: "error",
          message: translateErrorCode(result.error_code),
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка теста";
      publishToast({ type: "error", message });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    const data = validate();
    if (!data) return;

    setLoading(true);
    try {
      setLLMApiKey(data.api_key);

      const configPayload = {
        endpoint: data.endpoint,
        model: data.model,
        temperature: data.temperature,
      };

      if (hasExisting) {
        await updateLLMConfig(configPayload);
      } else {
        await saveLLMConfig(configPayload);
      }

      publishToast({ type: "info", message: "LLM конфиг сохранён" });
      onSaved?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка сохранения";
      publishToast({ type: "error", message });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    setShowDeleteDialog(false);
    try {
      await deleteLLMConfig();
      clearLLMApiKey();
      publishToast({ type: "info", message: "LLM конфиг удалён" });
      onSaved?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка удаления";
      publishToast({ type: "error", message });
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Endpoint
        </label>
        <Input
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
          placeholder="http://localhost:1234/v1"
        />
        {errors.endpoint && (
          <p className="text-xs text-red-400 mt-1">{errors.endpoint}</p>
        )}
      </div>

      <div>
        <label className="block text-xs text-[var(--fg-muted)] mb-1">
          Модель
        </label>
        <Input
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder="gpt-4o-mini"
          maxLength={100}
        />
        {errors.model && (
          <p className="text-xs text-red-400 mt-1">{errors.model}</p>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-[var(--fg-muted)]">Температура</label>
          <span className="text-xs text-[var(--fg)] font-mono">
            {temperature.toFixed(1)}
          </span>
        </div>
        <Slider
          value={[temperature]}
          onValueChange={([v]) => v !== undefined && setTemperature(v)}
          min={0}
          max={2}
          step={0.1}
        />
        {errors.temperature && (
          <p className="text-xs text-red-400 mt-1">{errors.temperature}</p>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-[var(--fg-muted)]">API ключ</label>
          {hasExisting && storedKey && (
            <button
              type="button"
              className="text-xs text-[var(--accent)] hover:underline"
              onClick={() => setShowKeyInput(!showKeyInput)}
            >
              {showKeyInput ? "Скрыть" : "Изменить ключ"}
            </button>
          )}
        </div>
        {showKeyInput ? (
          <Input
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
          />
        ) : (
          <div className="flex h-9 items-center px-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--fg-muted)] font-mono">
            ••••••••
          </div>
        )}
        {errors.api_key && (
          <p className="text-xs text-red-400 mt-1">{errors.api_key}</p>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleTest}
          disabled={testing}
        >
          {testing ? "Тестирование..." : "Тест"}
        </Button>
        <Button size="sm" onClick={handleSave} disabled={loading}>
          {loading ? "Сохранение..." : "Сохранить"}
        </Button>
        {hasExisting && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteDialog(true)}
          >
            Удалить
          </Button>
        )}
      </div>

      <AlertDialog open={showDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Удалить LLM конфиг?</AlertDialogTitle>
            <AlertDialogDescription>
              Конфиг и API ключ будут удалены. Чат перестанет работать до
              повторной настройки.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setShowDeleteDialog(false)}>
              Отмена
            </AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-800 hover:bg-red-700"
              onClick={handleDelete}
            >
              Удалить
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
