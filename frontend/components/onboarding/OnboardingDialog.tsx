"use client";

import { useEffect, useState } from "react";
import { BookMarked, BookOpen, Boxes, CheckCircle2, Database, Info } from "lucide-react";
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
  /**
   * Sprint 04 (handoff O-5): юзер выбрал quick-start вопрос на финальном шаге.
   * Если задан — completes onboarding и сразу создаёт сессию с этим вопросом.
   * Если не задан — quick-start чипы скрыты, fallback на «Начать работу».
   */
  onCompleteWithQuestion?: (
    firstChannelId: string | null,
    question: string,
  ) => void;
}

// Sprint 04 (handoff O-5): quick-start примеры вопросов, показываются на step=4.
// Аналогичны WELCOME_TEMPLATES, но без «{пустота}» — это финальный onboarding,
// нужны полные готовые вопросы.
const QUICK_START_QUESTIONS = [
  "Расскажи про базу — какая конфигурация и сколько объектов",
  "Покажи последние документы за неделю",
  "Какие пользователи самые активные сегодня",
];

type Step = 1 | 2 | 3 | 4;
// Sprint 04 (handoff O-6): «Обучение» → «Память» — согласовано с Settings → Memory.
const STEP_LABELS = ["База 1С", "Модель ИИ", "Память", "Готово"];
const LEARN_STORAGE_KEY = "analyst.learn_enabled";

// Sprint 04 (handoff O-1): persistance прогресса между перезагрузками.
// Если юзер закрыл вкладку посередине — при следующем заходе откроет с того
// же шага с восстановленными флагами.
const PROGRESS_STORAGE_KEY = "analyst.onboarding-progress";

interface PersistedProgress {
  step: Step;
  createdConnectionId: string | null;
  llmTestPassed: boolean;
  learnOn: boolean;
}

function loadProgress(): PersistedProgress | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PROGRESS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedProgress;
    // Sanity: step должен быть 1..4
    if (parsed.step < 1 || parsed.step > 4) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveProgress(p: PersistedProgress): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(p));
  } catch {
    // приватный режим — игнорируем
  }
}

function clearProgress(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(PROGRESS_STORAGE_KEY);
  } catch {
    // ignore
  }
}

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
  onCompleteWithQuestion,
}: OnboardingDialogProps) {
  const [step, setStep] = useState<Step>(1);
  const [createdConnection, setCreatedConnection] =
    useState<MCPConnection | null>(null);
  const [pingPassed, setPingPassed] = useState(false);
  const [pingLoading, setPingLoading] = useState(false);
  const [llmTestPassed, setLlmTestPassed] = useState(false);
  const [learnOn, setLearnOn] = useState(false);

  // Sprint 04 (O-1): сброс ИЛИ восстановление прогресса при открытии.
  // Note: createdConnection не восстанавливаем из backend (требует доп fetch) —
  // достаточно сохранить id и проигнорировать его в восстановлении: если
  // юзер вернулся, он либо уже видит свою базу в списке, либо начнёт заново.
  useEffect(() => {
    if (!open) return;
    const saved = loadProgress();
    if (saved) {
      setStep(saved.step);
      setLlmTestPassed(saved.llmTestPassed);
      setLearnOn(saved.learnOn);
      // pingPassed восстановим оптимистично — если сохранён connectionId,
      // считаем что ping был пройден (иначе step бы не сдвинулся).
      setPingPassed(saved.createdConnectionId !== null);
      setPingLoading(false);
    } else {
      setStep(1);
      setCreatedConnection(null);
      setPingPassed(false);
      setPingLoading(false);
      setLlmTestPassed(false);
      setLearnOn(false);
    }
  }, [open]);

  // Sprint 04 (O-1): persist при каждом изменении ключевого state.
  useEffect(() => {
    if (!open) return;
    saveProgress({
      step,
      createdConnectionId: createdConnection?.id ?? null,
      llmTestPassed,
      learnOn,
    });
  }, [open, step, createdConnection?.id, llmTestPassed, learnOn]);

  function handleSkip() {
    clearProgress();
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
    clearProgress();
    setOnboardingCompleted(true);
    onComplete(createdConnection?.id ?? null);
  }

  function handleStartWithQuestion(question: string) {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(
          LEARN_STORAGE_KEY,
          learnOn ? "true" : "false",
        );
      } catch {
        // ignore
      }
    }
    clearProgress();
    setOnboardingCompleted(true);
    // Если caller подписан на onCompleteWithQuestion — используем его,
    // иначе fallback на обычный onComplete (потеряем question).
    if (onCompleteWithQuestion) {
      onCompleteWithQuestion(createdConnection?.id ?? null, question);
    } else {
      onComplete(createdConnection?.id ?? null);
    }
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
                Память по этой базе
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
                    Опция сохранена
                  </div>
                  <div className="text-xs text-[var(--fg-3)] mt-0.5 leading-relaxed">
                    Когда память запустится, она подхватит ваши прошлые ответы
                    по&nbsp;этой базе. Управлять можно в&nbsp;Настройки →&nbsp;Память.
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
          <div className="space-y-5 animate-fade-up" data-testid="onboarding-step-done">
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
                    , память{" "}
                    <span className="text-[var(--accent)] font-medium">
                      включена
                    </span>
                  </>
                )}
                .
              </p>
            </div>

            {/* P1 user-facing: три источника знаний — пользователь сразу
                понимает, что спрашивать можно не только про свою базу. */}
            <div className="rounded-lg border border-[var(--bd-2)] bg-[var(--bg-2)] p-3 space-y-2.5">
              <div className="text-[11px] font-medium text-[var(--fg-1)]">
                Что я умею — три источника знаний:
              </div>
              {[
                {
                  icon: Database,
                  title: "Ваша база 1С",
                  desc: "данные, структура, журнал регистрации",
                },
                {
                  icon: Boxes,
                  title: "Типовая конфигурация",
                  desc: "как устроена УТ / ERP / КА / БП — движения, цепочки",
                },
                {
                  icon: BookMarked,
                  title: "ИТС · Напарник",
                  desc: "методики, стандарты, инструкции 1С",
                },
              ].map((s) => {
                const Icon = s.icon;
                return (
                  <div key={s.title} className="flex items-start gap-2.5">
                    <Icon className="h-4 w-4 text-[var(--accent)] flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <span className="text-[12.5px] font-medium text-[var(--fg-1)]">
                        {s.title}
                      </span>
                      <span className="text-[12px] text-[var(--fg-3)]"> — {s.desc}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Sprint 04 (handoff O-5): quick-start примеры. Если caller
                не передал onCompleteWithQuestion — чипы не показываем,
                чтобы клик не «терял» вопрос. */}
            {onCompleteWithQuestion && (
              <div className="space-y-2">
                <div
                  className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)]"
                  style={{
                    fontFamily:
                      "var(--font-jb-mono), ui-monospace, monospace",
                  }}
                >
                  Попробуйте начать с одного из вопросов:
                </div>
                {QUICK_START_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleStartWithQuestion(q)}
                    className="w-full text-left px-3 py-2 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)] hover:border-[var(--accent-32)] hover:bg-[var(--accent-08)] transition-colors text-[13px] text-[var(--fg-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-1)]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              <Button variant="ghost" size="sm" onClick={handleBack}>
                ← Назад
              </Button>
              <Button className="flex-1" onClick={handleComplete}>
                {onCompleteWithQuestion
                  ? "Начать с пустого чата"
                  : "Начать работу"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
