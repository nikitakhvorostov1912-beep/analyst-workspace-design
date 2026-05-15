"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { StepIndicator } from "./StepIndicator";
import { MCPConnectionForm } from "@/components/settings/MCPConnectionForm";
import { LLMConfigForm } from "@/components/settings/LLMConfigForm";
import { pingConnection } from "@/lib/api";
import { setOnboardingCompleted } from "@/lib/onboarding-flag";
import { publishToast } from "@/lib/toast";
import type { MCPConnection } from "@/lib/types";

interface OnboardingDialogProps {
  open: boolean;
  onComplete: (firstChannelId: string | null) => void;
  onSkip: () => void;
}

export function OnboardingDialog({
  open,
  onComplete,
  onSkip,
}: OnboardingDialogProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [createdConnection, setCreatedConnection] =
    useState<MCPConnection | null>(null);
  const [pingPassed, setPingPassed] = useState(false);
  const [pingLoading, setPingLoading] = useState(false);
  const [llmTestPassed, setLlmTestPassed] = useState(false);

  // Сброс состояния при каждом открытии
  useEffect(() => {
    if (open) {
      setStep(1);
      setCreatedConnection(null);
      setPingPassed(false);
      setPingLoading(false);
      setLlmTestPassed(false);
    }
  }, [open]);

  function handleSkip() {
    setOnboardingCompleted(true);
    onSkip();
  }

  function handleBack() {
    setStep((s) => (Math.max(1, s - 1) as 1 | 2 | 3));
  }

  function handleNext() {
    setStep((s) => (Math.min(3, s + 1) as 1 | 2 | 3));
  }

  function handleComplete() {
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
      publishToast({ type: "info", message: "MCP подключён" });
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
      <DialogContent className="max-w-[640px] p-6" onPointerDownOutside={(e) => e.preventDefault()}>
        <StepIndicator current={step} total={3} />

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-[var(--fg)]">
                Подключите вашу базу 1С
              </h2>
              <p className="text-sm text-[var(--fg-muted)] mt-1">
                Адрес MCP Toolkit (обычно{" "}
                <code className="font-mono text-xs">
                  http://localhost:6010/mcp
                </code>{" "}
                или{" "}
                <code className="font-mono text-xs">:6003/mcp</code>)
              </p>
            </div>

            <MCPConnectionForm
              initial={null}
              onSaved={handleMCPSaved}
            />

            {pingLoading && (
              <p className="text-xs text-[var(--fg-muted)]">
                Проверяем соединение...
              </p>
            )}

            <div className="flex items-center justify-between pt-2">
              <Button variant="ghost" size="sm" onClick={handleSkip}>
                Пропустить
              </Button>
              <Button
                size="sm"
                onClick={handleNext}
                disabled={!pingPassed}
              >
                Далее →
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-[var(--fg)]">
                Настройте LLM
              </h2>
              <p className="text-sm text-[var(--fg-muted)] mt-1">
                OpenAI-совместимый endpoint, например{" "}
                <code className="font-mono text-xs">
                  http://localhost:1234/v1
                </code>{" "}
                для LM Studio. Нажмите «Тест», затем «Сохранить».
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
              <Button
                size="sm"
                onClick={handleNext}
                disabled={!llmTestPassed}
              >
                Далее →
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--fg)]">
                Готово!
              </h2>
              <p className="text-sm text-[var(--fg-muted)] mt-1">
                Подключение и LLM настроены. Задайте первый вопрос, например:
                «Расскажи про базу»
              </p>
            </div>

            <Button
              className="w-full"
              onClick={handleComplete}
            >
              Начать работу
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
