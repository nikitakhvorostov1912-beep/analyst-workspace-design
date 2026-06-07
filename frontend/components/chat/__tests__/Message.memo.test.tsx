import { describe, it, expect } from "vitest";
import { areMessagePropsEqual } from "../Message";
import type { ChatMessage } from "@/lib/types";

function msg(id: string, content = ""): ChatMessage {
  return { id, role: "assistant", content, created_at: "2026-06-07T00:00:00Z" };
}

/**
 * Гарантия фикса «зависает всё»: история (НЕ стримящееся сообщение) не должна
 * пере-рендериться/пере-парсить разметку на каждый throttled-сброс дельт.
 * Компаратор memo пропускает рендер, когда ССЫЛКА message и флаги стрима те же.
 */
describe("areMessagePropsEqual (Message memo)", () => {
  const stable = {
    isStreaming: false,
    streamingStage: null,
    currentToolName: null,
    streamStartedAt: null,
    sessionId: "s1",
  } as const;

  it("пропускает рендер: тот же message ref + те же флаги стрима", () => {
    const m = msg("a", "ответ");
    expect(
      areMessagePropsEqual({ message: m, ...stable }, { message: m, ...stable }),
    ).toBe(true);
  });

  it("рендерит: message ref изменился (растущее стримящееся сообщение)", () => {
    const a = msg("a", "час");
    const b = msg("a", "часть");
    expect(
      areMessagePropsEqual(
        { message: a, ...stable, isStreaming: true, streamStartedAt: 1 },
        { message: b, ...stable, isStreaming: true, streamStartedAt: 1 },
      ),
    ).toBe(false);
  });

  it("рендерит: isStreaming сменился (финализация на done)", () => {
    const m = msg("a", "ответ");
    expect(
      areMessagePropsEqual(
        { message: m, ...stable, isStreaming: true, streamStartedAt: 1 },
        { message: m, ...stable, isStreaming: false, streamStartedAt: 1 },
      ),
    ).toBe(false);
  });

  it("рендерит: сменилась streamingStage у активного сообщения", () => {
    const m = msg("a", "ответ");
    expect(
      areMessagePropsEqual(
        { message: m, ...stable, isStreaming: true, streamingStage: "thinking" },
        { message: m, ...stable, isStreaming: true, streamingStage: "formatting" },
      ),
    ).toBe(false);
  });

  it("игнорирует identity onRepeat (новое замыкание Thread не дёргает историю)", () => {
    const m = msg("a", "ответ");
    expect(
      areMessagePropsEqual(
        { message: m, ...stable, onRepeat: () => {} },
        { message: m, ...stable, onRepeat: () => {} },
      ),
    ).toBe(true);
  });
});
