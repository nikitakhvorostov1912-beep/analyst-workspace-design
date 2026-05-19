"use client";

import { useEffect, useState } from "react";
import { BookOpen, CheckCircle2, Info } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { StepIndicator } from "./StepIndicator";
import { MCPConnectionForm } from "@/components/settings/MCPConnectionForm";
import { LLMConfigForm } from "@/components/settings/LLMConfigForm";
import { pingConnection } from "@/lib/api";
import { setOnboardingCompleted } from "@/lib/onboarding-flag";
import { publishToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { MCPConnection } from "@/lib/types";

interface OnboardingDialogProps {
  open: boolean;
  onComplete: (firstChannelId: string | null) => void;
  onSkip: () => void;
}

type Step = 1 | 2 | 3 | 4;
const STEP_LABELS = ["База 1С", "Модель ИИ", "Обучение", "Готово"];
const LEARN_STORAGE_KEY = "analyst.learn_enabled";

function clampStep(value: number): Step {
  if (value < 1) return 1;
  if (value > 4) return 4;
  return value as Step;
}

/**
 * Compact local Switch (no extra Radix dependency).
 */
interface LearnSwitchProps {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  label: string;
}

function LearnSwitch({ checked, onCheckedChange, label }: LearnSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onCheckedChange(!checked)}
      data-state={checked ? "on" : "off"}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-normal ease-design-ease",
        checked
          ? "bg-[var(--accent)]"
          : "bg-[var(--bd-2)] hover:bg-[var(--bd-3)]",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform duration-normal ease-design-ease",
          checked ? "translate-x-[22px]" : "translate-x-[2px]",
        )}
      />
    </button>
  );
}

export function OnboardingDialog({
  open,
  onComplete,
  onSkip,
}: OnboardingDialogProps) {
  const [step, setStep] = useState<Step>(1);
  const [createdConnection, setCreatedConnection] =
    useState<MCPConnection | null>(null);
  const [pingPassed, setPingPassed] = useState(false);
  const [pingLoading, setPingLoading] = useState(false);
  const [llmTestPassed, setLlmTestPassed] = useState(false);
  const [learnOn, setLearnOn] = useState(false);

  // Сброс состояния при каждом открытии
  useEffect(() => {
    if (open) {
      setStep(1);
      setCreatedConnection(null);
      setPingPassed(false);
      setPingLoading(false);
      setLlmTestPassed(false);
      setLearnOn(false);
    }
  }, [open]);

  function handleSkip() {
    setOnboardingCompleted(true);
    onSkip();
  }

  function handleBack() {
    setStep((s) => clampStep(s - 1));
  }

  function handleNext() {
    setStep((s) => clampStep(s + 1));
  }

  function handleComplete() {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(LEARN_STORAGE_KEY, learnOn ? "true" : "false");
      } catch {
        // localStorage недоступен (privacy mode) — игнорируем
      }
    }
    setOnboardingCompleted(true);
    onComplete(createdConnection?.id ?? null);
  }

  async function handleMCPSaved(conn: MCPConnection) {
    setCreatedConnection(conn);
    setPingPassed(false);
    setPingLoading(true);
    try {
      await pingConnection(conn.id);
      setPingPassed(true);
      publishToast({ type: "info", message: "База 1С отвечает" });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось подключиться";
      publishToast({ type: "error", message });
      setPingPassed(false);
    } finally {
      setPingLoading(false);
    }
  }

  function handleLLMSaved() {
    setLlmTestPassed(true);
  }

  return (
    <Dialog open={open}>
      <DialogContent
        className="max-w-[640px] p-6"
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <StepIndicator current={step} total={4} labels={STEP_LABELS} />

        {step === 1 && (
          <div className="space-y-4 animate-fade-up">
            <div>
              <DialogTitle className="text-lg font-semibold text-[var(--fg-1)]">
                Подключите вашу базу 1С
              </DialogTitle>
              <p className="text-sm text-[var(--fg-3)] mt-1">
                В&nbsp;1С должна быть запущена обработка-обработчик от ИТ-отдела
                (по&nbsp;умолчанию на порту 6010). Адрес и имя уже подставлены —
                нажмите «Сохранить».
              </p>
            </div>

            <MCPConnectionForm initial={null} onSaved={handleMCPSaved} />

            {pingLoading && (
              <p className="text-xs text-[var(--fg-3)]">
                Проверяем соединение...
              </p>
            )}

            <div className="flex items-center justify-between pt-2">
              <Button variant="ghost" size="sm" onClick={handleSkip}>
                Пропустить
              </Button>
              <Button size="sm" onClick={handleNext} disabled={!pingPassed}>
                Далее →
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 animate-fade-up">
            <div>
              <DialogTitle className="text-lg font-semibold text-[var(--fg-1)]">
                Подключите модель ИИ
              </DialogTitle>
              <p className="text-sm text-[var(--fg-3)] mt-1">
                Введите API ключ от вашего поставщика (OpenAI, Aitunnel, Anthropic
                или другой). Нажмите «Тест» — потом «Сохранить». Адрес и название
                модели уже подставлены.
              </p>
            </div>

            <LLMConfigForm initial={null} onSaved={handleLLMSaved} />

            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleBack}>
                  ← Назад
                </Button>
                <Button variant="ghost" size="sm" onClick={handleSkip}>
                  Пропустить
                </Button>
              </div>
              <Button size="sm" onClick={handleNext} disabled={!llmTestPassed}>
                Далее →
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5 animate-fade-up" data-testid="onboarding-step-learn">
            <div>
              <div
                className="h-10 w-10 rounded-lg bg-[var(--accent-08)] border border-[var(--accent-20)] text-[var(--accent)] inline-flex items-center justify-center mb-3"
                aria-hidden="true"
              >
                <BookOpen className="h-5 w-5" />
              </div>
              <DialogTitle className="text-lg font-semibold text-[var(--fg-1)]">
                Обучение на ваших чатах
                <span className="ml-2 text-sm font-normal text-[var(--fg-3)]">
                  · опционально
                </span>
              </DialogTitle>
              <p className="text-sm text-[var(--fg-3)] mt-1 leading-relaxed">
                Модель будет помнить ваши прошлые ответы по этой базе. Полезно
                для повторяющихся задач: миграции, регулярные сверки, разбор
                частых ошибок. Можно включить позже в Настройках.
              </p>
            </div>

            <div className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--bd-2)] rounded-lg">
              <div className="flex-1 min-w-0 pr-3">
                <div className="text-sm font-medium text-[var(--fg-1)]">
                  Включить обучение сейчас
                </div>
                <div className="text-xs text-[var(--fg-3)] mt-0.5">
                  По умолчанию выключено · приватно
                </div>
              </div>
              <LearnSwitch
                checked={learnOn}
                onCheckedChange={setLearnOn}
                label="Включить обучение на сессиях"
              />
            </div>

            {learnOn && (
              <div className="animate-fade-up p-3 bg-[var(--accent-08)] border border-[var(--accent-20)] rounded-md flex gap-2">
                <Info className="h-4 w-4 text-[var(--accent)] flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="text-[13px] font-medium text-[var(--fg-1)]">
                    Готовим функцию обучения
                  </div>
                  <div className="text-xs text-[var(--fg-3)] mt-0.5 leading-relaxed">
                    Когда функция будет готова, ваши прошлые чаты будут использованы
                    автоматически. Сейчас включение запомнит ваш выбор — настройка
                    появится в Настройках → Обучение.
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleBack}>
                  ← Назад
                </Button>
                <Button variant="ghost" size="sm" onClick={handleSkip}>
                  Пропустить
                </Button>
              </div>
              <Button size="sm" onClick={handleNext}>
                Далее →
              </Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-6 animate-fade-up" data-testid="onboarding-step-done">
            <div>
              <div
                className="h-12 w-12 rounded-full bg-[var(--success-12)] border border-[var(--success-20)] text-[var(--success)] inline-flex items-center justify-center mb-3"
                aria-hidden="true"
              >
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <DialogTitle className="text-lg font-semibold text-[var(--fg-1)]">
                Готово!
              </DialogTitle>
              <p className="text-sm text-[var(--fg-3)] mt-1 leading-relaxed">
                База&nbsp;1С подключена
                {createdConnection && (
                  <>
                    {" "}
                    (<span className="font-mono text-[var(--fg-2)]">{createdConnection.name}</span>),
                  </>
                )}
                {" "}модель ИИ готова к работе
                {learnOn && (
                  <>
                    , обучение{" "}
                    <span className="text-[var(--accent)] font-medium">
                      включено
                    </span>
                  </>
                )}
                . Задайте первый вопрос, например: «Расскажи про базу».
              </p>
            </div>

            <div className="flex items-center justify-between gap-2">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                ← Назад
              </Button>
              <Button className="flex-1" onClick={handleComplete}>
                Начать работу
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
