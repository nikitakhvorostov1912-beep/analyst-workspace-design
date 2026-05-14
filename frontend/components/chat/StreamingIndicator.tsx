"use client";

export type StreamingStage = "thinking" | "calling_tool" | "formatting";

interface StreamingIndicatorProps {
  stage: StreamingStage | null;
  toolName?: string;
}

/**
 * Строчный индикатор текущей стадии стриминга.
 * Возвращает null когда stage=null.
 */
export function StreamingIndicator({ stage, toolName }: StreamingIndicatorProps) {
  if (stage === null) return null;

  const label =
    stage === "thinking"
      ? "Анализирую..."
      : stage === "calling_tool"
        ? `Вызываю ${toolName ?? "инструмент"}...`
        : "Формирую ответ...";

  return (
    <span className="inline-flex items-center gap-1.5 text-xs italic text-[var(--fg-muted)] animate-pulse">
      <span>⠿</span>
      <span>{label}</span>
    </span>
  );
}
