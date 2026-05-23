/**
 * Adapter: SSE streaming state → StreamingStages pipeline.
 *
 * Phase 11.4 integration — преобразует флаги useChatStream
 * (streamingStage + currentToolName + completed tool_calls) в линейный
 * массив этапов для визуального компонента StreamingStages.
 */

import type { Stage } from "@/components/chat/StreamingStages";
import type { ToolCallRecord } from "@/lib/types";

/**
 * Стадия SSE-стриминга, отдаваемая backend'ом в event=status / event=delta.
 *
 * REM-5 (2026-05-24): тип перенесён сюда из deprecated `StreamingIndicator.tsx`
 * который удалён в Sprint 01. `StreamingStages` теперь единственный рендерер
 * pipeline'а — buildStreamingStages() ниже превращает SSE state в массив этапов.
 */
export type StreamingStage = "thinking" | "calling_tool" | "formatting";

interface BuildStagesInput {
  streamingStage: StreamingStage | null;
  currentToolName: string | null;
  toolCalls: ToolCallRecord[];
}

interface BuildStagesResult {
  stages: Stage[];
  activeIndex: number;
}

/**
 * Превращает текущее SSE state в линейный pipeline.
 *
 * Возвращает null, если стриминг неактивен — caller должен скрыть индикатор.
 *
 * Маппинг:
 *   - streamingStage === "thinking" → [analyzing*]
 *   - streamingStage === "calling_tool" → [analyzing, ...completed, tool*]
 *   - streamingStage === "formatting" → [analyzing, ...completed, finalizing*]
 *
 * "completed" — tool_calls с заполненным duration_ms (получили tool_result).
 */
export function buildStreamingStages(
  input: BuildStagesInput,
): BuildStagesResult | null {
  const { streamingStage, currentToolName, toolCalls } = input;

  if (streamingStage === null) return null;

  const stages: Stage[] = [{ kind: "analyzing" }];

  // Добавляем завершённые tool calls (с duration_ms из tool_result)
  const completed = toolCalls.filter(
    (tc) => typeof tc.duration_ms === "number",
  );

  for (const tc of completed) {
    stages.push({ kind: "tool", tool: tc.name });
    stages.push({ kind: "tool_done", doneIn: tc.duration_ms });
  }

  if (streamingStage === "thinking") {
    return { stages, activeIndex: 0 };
  }

  if (streamingStage === "calling_tool") {
    // Если есть currentToolName — добавляем активный tool stage
    if (currentToolName) {
      // Не дублируем если уже добавили этот tool как completed
      const lastCompletedTool = completed[completed.length - 1];
      const alreadyCompleted =
        lastCompletedTool &&
        lastCompletedTool.name === currentToolName &&
        typeof lastCompletedTool.duration_ms === "number";

      if (!alreadyCompleted) {
        stages.push({ kind: "tool", tool: currentToolName });
      }
    }
    return { stages, activeIndex: stages.length - 1 };
  }

  if (streamingStage === "formatting") {
    stages.push({ kind: "finalizing" });
    return { stages, activeIndex: stages.length - 1 };
  }

  // Fallback (не должен случаться при правильной типизации)
  return { stages, activeIndex: 0 };
}
