"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { LiveTestResult } from "@/components/ui/LiveTestResult";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { llmConfigSchema, llmConfigUpdateSchema } from "@/lib/form-schemas";
import { getLLMApiKey, setLLMApiKey, clearLLMApiKey } from "@/lib/api-keys";
import {
  CUSTOM_MODEL_ID,
  DEFAULT_PRESET_ID,
  PROVIDERS,
  resolveProviderAndModel,
} from "@/lib/llm-providers";
import { publishToast } from "@/lib/toast";
import type { LLMConfigResponse } from "@/lib/types";

interface LLMConfigFormProps {
  initial: LLMConfigResponse | null;
  onSaved?: () => void;
}

/**
 * Каталог провайдеров вынесен в `lib/llm-providers.ts` — переиспользуется
 * ModelBadge popover'ом в шапке для быстрого переключения модели.
 */

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
  // Backend получит ключ из env DEFAULT_LLM_API_KEY (зашитый при сборке инсталлятора —
  // обычно MiMo). Для других провайдеров ключ не подойдёт, поэтому UI показывает env-плашку
  // только когда выбран MiMo. Если пользователь сменил провайдера — попросим ввести свой.
  const hasEnvApiKey = Boolean(initial?.has_env_api_key);

  const initialId = initial ? initial.model : DEFAULT_PRESET_ID;
  const initialMatch = resolveProviderAndModel(initialId);
  const initialPresetId = initialMatch ? initialId : CUSTOM_MODEL_ID;

  const [presetId, setPresetId] = useState<string>(initialPresetId);
  const [customModel, setCustomModel] = useState(initial?.model ?? "");
  const [customEndpoint, setCustomEndpoint] = useState(initial?.endpoint ?? "");
  const [temperature, setTemperature] = useState(initial?.temperature ?? 0.3);
  const [apiKey, setApiKey] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(
    !(hasExisting && storedKey) && !hasEnvApiKey,
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(initialPresetId === CUSTOM_MODEL_ID);
  // Sprint 02 (handoff B · LiveTestResult): inline-чип результата теста — см. MCPConnectionForm.
  const [testState, setTestState] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");
  const [testMs, setTestMs] = useState<number | undefined>(undefined);
  const [testDetail, setTestDetail] = useState<string | undefined>(undefined);
  const [testError, setTestError] = useState<string | undefined>(undefined);

  // activePreset = текущий выбор (плоский preset или null если custom).
  const activePreset = useMemo(() => {
    if (presetId === CUSTOM_MODEL_ID) return null;
    return resolveProviderAndModel(presetId);
  }, [presetId]);

  const isCustom = presetId === CUSTOM_MODEL_ID;

  // Эффективные значения для отправки в backend.
  const effectiveModel = isCustom ? customModel : presetId;
  const effectiveEndpoint = isCustom
    ? customEndpoint
    : activePreset?.provider.endpoint ?? "";

  // Env-ключ применим ТОЛЬКО к встроенному провайдеру MiMo. Для остальных провайдеров
  // backend всё равно пошлёт env-ключ — но удалённый сервер вернёт 401, что собьёт пользователя.
  // Поэтому UI явно показывает env-плашку только для MiMo, иначе требует ввод.
  const envKeyApplies =
    hasEnvApiKey && Boolean(activePreset?.provider.embedKeyAvailable);

  function getEffectiveApiKey(): string {
    if (showKeyInput) return apiKey;
    return storedKey ?? "";
  }

  function validate() {
    const effectiveKey = getEffectiveApiKey();
    const skipKeyCheck = envKeyApplies && !effectiveKey;
    const schema = skipKeyCheck ? llmConfigUpdateSchema : llmConfigSchema;
    const result = schema.safeParse({
      endpoint: effectiveEndpoint,
      model: effectiveModel,
      temperature,
      ...(skipKeyCheck ? {} : { api_key: effectiveKey }),
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
    return { ...result.data, api_key: effectiveKey };
  }

  async function handleTest() {
    const data = validate();
    if (!data) return;

    setTesting(true);
    setTestState("testing");
    setTestError(undefined);
    const t0 = performance.now();
    try {
      const result = await testLLMConfig(
        { endpoint: data.endpoint, model: data.model, temperature: data.temperature },
        data.api_key,
      );

      if (result.ok) {
        const elapsed = Math.round(performance.now() - t0);
        setTestMs(elapsed);
        setTestDetail(data.model);
        setTestState("success");
        publishToast({
          type: "info",
          message: `Модель отвечает: ${data.model}`,
        });
      } else {
        const message = translateErrorCode(result.error_code);
        setTestError(message);
        setTestState("error");
        publishToast({
          type: "error",
          message,
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка теста";
      setTestError(message);
      setTestState("error");
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
      // 2026-05-24: если переключение на провайдер с embedded env-ключом
      // (NVIDIA NIM) И пользователь не вводил свой ключ — очищаем legacy
      // localStorage от чужого ключа (например, оставшегося от MiMo). Иначе
      // backend получит MiMo-ключ при вызове NVIDIA — `401 Unauthorized`.
      if (envKeyApplies && !apiKey) {
        clearLLMApiKey();
      } else if (data.api_key) {
        setLLMApiKey(data.api_key);
      }

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

      publishToast({ type: "info", message: "Настройки модели ИИ сохранены" });
      // 2026-05-24: уведомляем шапку (ModelBadge) что конфиг сменился.
      // Без этого ModelBadge оставался со старой моделью пока юзер не
      // перезагрузит страницу — самый частый «не работает» сценарий.
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("llm-config-updated"));
      }
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
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("llm-config-updated"));
      }
      onSaved?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ошибка удаления";
      publishToast({ type: "error", message });
    }
  }

  function handlePresetChange(next: string) {
    setPresetId(next);
    if (next === CUSTOM_MODEL_ID) {
      setAdvancedOpen(true);
      // Если custom-поля пусты — подставим заготовки из initial либо предыдущего preset.
      if (!customModel && initial?.model) setCustomModel(initial.model);
      if (!customEndpoint) {
        setCustomEndpoint(initial?.endpoint ?? "https://api.openai.com/v1");
      }
    }
    // Сменился провайдер → возможно изменилась применимость env-ключа.
    // Если переключились с MiMo (env-applies) на другого провайдера и нет
    // локального ключа — показать поле ввода.
    const newMatch = next === CUSTOM_MODEL_ID ? null : resolveProviderAndModel(next);
    const newEnvApplies = hasEnvApiKey && Boolean(newMatch?.provider.embedKeyAvailable);
    if (!newEnvApplies && !storedKey) {
      setShowKeyInput(true);
    }
  }

  return (
    <div className="space-y-4">
      {/* Выбор модели. Заголовок «Модель ИИ» + описание уже стоит в шапке секции
          SettingsPage — здесь не дублируем. SelectValue рендерит ТОЛЬКО короткое
          название (например «MiMo v2.5 Pro»), чтобы trigger остался однострочным
          и текст не центрировался от двухстрочного SelectItem. */}
      <div>
        <Select value={presetId} onValueChange={handlePresetChange}>
          <SelectTrigger
            data-testid="model-preset-select"
            aria-label="Модель ИИ"
          >
            <SelectValue>
              {presetId === CUSTOM_MODEL_ID
                ? "Произвольная модель"
                : activePreset?.model.label ?? "Выберите модель"}
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="max-h-[400px]">
            {PROVIDERS.map((provider, idx) => (
              <SelectGroup key={provider.id}>
                {idx > 0 && <SelectSeparator />}
                <SelectLabel>{provider.label}</SelectLabel>
                {provider.models.map((preset) => (
                  <SelectItem key={preset.id} value={preset.id}>
                    <div className="flex flex-col">
                      <span className="font-medium">{preset.label}</span>
                      <span className="text-xs text-[var(--fg-muted)]">
                        {preset.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
            <SelectSeparator />
            <SelectGroup>
              <SelectLabel>Другое</SelectLabel>
              <SelectItem value={CUSTOM_MODEL_ID}>
                <div className="flex flex-col">
                  <span className="font-medium">Произвольная модель</span>
                  <span className="text-xs text-[var(--fg-muted)]">
                    Свой OpenAI-совместимый сервер
                  </span>
                </div>
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        {/* Под dropdown — провайдер + compliance badge (P3.3).
            Badge показывает 152-ФЗ статус: «РФ-ДЦ ✓» для Cloud.ru / GigaChat /
            YandexGPT (когда добавим), «За рубежом» для зарубежных. */}
        {activePreset && (
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <p className="text-xs text-[var(--fg-3)]">
              Провайдер:{" "}
              <span className="font-mono text-[var(--fg-2)]">
                {activePreset.provider.label}
              </span>
            </p>
            {activePreset.provider.compliance?.russian_dc && (
              <span
                data-testid="compliance-badge-ru"
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wide bg-[var(--success-12)] text-[var(--success)] border border-[var(--success-40)]"
                title="Хостится в РФ-дата-центре. Безопасно по 152-ФЗ без отдельного согласия субъектов ПД."
              >
                РФ-ДЦ ✓ 152-ФЗ
              </span>
            )}
            {activePreset.provider.compliance &&
              !activePreset.provider.compliance.russian_dc && (
                <span
                  data-testid="compliance-badge-foreign"
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wide bg-[var(--warning-12)] text-[var(--warning)] border border-[var(--warning-40)]"
                  title="Провайдер за рубежом. По 152-ФЗ передача ПД требует согласия субъектов."
                >
                  За рубежом
                </span>
              )}
          </div>
        )}
        {errors.model && (
          <p className="text-xs text-[var(--error)] mt-1">{errors.model}</p>
        )}
      </div>

      {/* API ключ. Логика отображения:
          - envKeyApplies (выбран MiMo + есть ключ в .env) → зелёная плашка
          - storedKey есть → •••• с кнопкой «Изменить ключ»
          - иначе → поле ввода */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-[var(--fg-muted)]">API ключ</label>
          {(storedKey || envKeyApplies) && (
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
            placeholder={
              envKeyApplies
                ? "Оставьте пустым — будет использован ключ из .env"
                : activePreset?.provider.keyHint ?? "sk-..."
            }
          />
        ) : envKeyApplies && !storedKey ? (
          <div className="flex h-9 items-center px-3 rounded-md border border-[var(--success-40)] bg-[var(--success-12)] text-sm text-[var(--success)] font-mono">
            ✓ Ключ задан в окружении сервера (.env)
          </div>
        ) : (
          <div className="flex h-9 items-center px-3 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] text-sm text-[var(--fg-muted)] font-mono">
            ••••••••
          </div>
        )}
        {/* Если выбран НЕ-MiMo провайдер с env-ключом — предупредим пользователя */}
        {hasEnvApiKey &&
          activePreset &&
          !activePreset.provider.embedKeyAvailable &&
          !storedKey &&
          showKeyInput &&
          !apiKey && (
            <p className="text-xs text-[var(--warning)] mt-1">
              Зашитый в дистрибутиве ключ работает только для Xiaomi MiMo. Для{" "}
              {activePreset.provider.label} введите свой ключ.
            </p>
          )}
        {activePreset && !storedKey && showKeyInput && (
          <p className="text-xs text-[var(--fg-3)] mt-1">
            Где взять:{" "}
            <span className="font-mono text-[var(--fg-2)]">
              {activePreset.provider.keyDocsUrl}
            </span>
          </p>
        )}
        {errors.api_key && (
          <p className="text-xs text-[var(--error)] mt-1">{errors.api_key}</p>
        )}
      </div>

      {/* Расширенные — кастомный preset + temperature. */}
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
            {isCustom && (
              <>
                <div>
                  <label className="block text-xs text-[var(--fg-muted)] mb-1">
                    Идентификатор модели
                  </label>
                  <Input
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    placeholder="gpt-4o, claude-3-5-sonnet, ..."
                    maxLength={100}
                  />
                  <p className="text-xs text-[var(--fg-3)] mt-1">
                    Точный id модели как принимает OpenAI-совместимый API.
                  </p>
                </div>

                <div>
                  <label className="block text-xs text-[var(--fg-muted)] mb-1">
                    Адрес сервера
                  </label>
                  <Input
                    value={customEndpoint}
                    onChange={(e) => setCustomEndpoint(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                  />
                  {errors.endpoint ? (
                    <p className="text-xs text-[var(--error)] mt-1">{errors.endpoint}</p>
                  ) : (
                    <p className="text-xs text-[var(--fg-3)] mt-1">
                      Базовый URL OpenAI-совместимого API.
                    </p>
                  )}
                </div>
              </>
            )}

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-[var(--fg-muted)]">
                  Температура
                </label>
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
              <p className="text-xs text-[var(--fg-3)] mt-1">
                0 — строгие ответы, 1 — баланс, 2 — креативные. По умолчанию 0.3.
              </p>
              {errors.temperature && (
                <p className="text-xs text-[var(--error)] mt-1">{errors.temperature}</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1 flex-wrap">
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
        <LiveTestResult
          state={testState}
          ms={testMs}
          detail={testDetail}
          errorMessage={testError}
        />
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
              className="bg-[var(--error)] hover:opacity-90"
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
