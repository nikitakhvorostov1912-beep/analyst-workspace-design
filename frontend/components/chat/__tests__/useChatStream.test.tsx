import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useChatStream } from "../useChatStream";
import type { SSEEvent } from "@/lib/types";

// Мокаем fetchChat из api.ts
vi.mock("@/lib/api", () => ({
  fetchChat: vi.fn(),
}));

// Мокаем getLLMConfig
vi.mock("@/lib/storage", () => ({
  getLLMConfig: () => ({
    endpoint: "http://localhost:1234/v1",
    api_key: "sk-test",
    model: "test-model",
    temperature: 0.3,
  }),
}));

import { fetchChat } from "@/lib/api";

async function* makeStream(events: SSEEvent[]): AsyncIterable<SSEEvent> {
  for (const e of events) {
    yield e;
  }
}

describe("useChatStream", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("начинает с initialMessages", () => {
    const initial = [
      {
        id: "m1",
        role: "user" as const,
        content: "Привет",
        created_at: new Date().toISOString(),
      },
    ];
    const { result } = renderHook(() =>
      useChatStream({
        sessionId: "s1",
        channelId: "ch1",
        initialMessages: initial,
      }),
    );
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]!.content).toBe("Привет");
  });

  it("send добавляет user message и placeholder assistant", async () => {
    vi.mocked(fetchChat).mockReturnValue(makeStream([]));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("Тестовый запрос");
    });

    // user + assistant (пустой после пустого стрима)
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]!.role).toBe("user");
    expect(result.current.messages[0]!.content).toBe("Тестовый запрос");
    expect(result.current.messages[1]!.role).toBe("assistant");
  });

  it("delta события накапливаются в assistant.content", async () => {
    const events: SSEEvent[] = [
      { event: "status", data: { stage: "thinking" } },
      { event: "delta", data: { content: "Привет" } },
      { event: "delta", data: { content: " мир" } },
      { event: "done", data: { message_id: "done-id", total_duration_ms: 100 } },
    ];
    vi.mocked(fetchChat).mockReturnValue(makeStream(events));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("вопрос");
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    expect(assistant?.content).toBe("Привет мир");
    expect(assistant?.id).toBe("done-id");
    expect(assistant?.duration_ms).toBe(100);
  });

  it("card event добавляется в assistant.cards", async () => {
    const events: SSEEvent[] = [
      {
        event: "card",
        data: {
          type: "table",
          payload: { columns: [], rows: [], total: 0, meta: {} },
        },
      } as SSEEvent,
      { event: "done", data: { message_id: "m1", total_duration_ms: 50 } },
    ];
    vi.mocked(fetchChat).mockReturnValue(makeStream(events));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("покажи таблицу");
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    expect(assistant?.cards?.length).toBe(1);
    expect(assistant?.cards?.[0]?.type).toBe("table");
  });

  it("tool_call/tool_result обновляет tool_calls в assistant", async () => {
    const events: SSEEvent[] = [
      { event: "tool_call", data: { id: "tc1", name: "execute_query", args: {} } },
      {
        event: "tool_result",
        data: { id: "tc1", ok: true, result: { data: [] }, error: null, duration_ms: 42 },
      },
      { event: "done", data: { message_id: "m1", total_duration_ms: 200 } },
    ];
    vi.mocked(fetchChat).mockReturnValue(makeStream(events));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("запрос");
    });

    const assistant = result.current.messages.find((m) => m.role === "assistant");
    expect(assistant?.tool_calls?.length).toBe(1);
    expect(assistant?.tool_calls?.[0]?.name).toBe("execute_query");
    expect(assistant?.tool_calls?.[0]?.ok).toBe(true);
    expect(assistant?.tool_calls?.[0]?.duration_ms).toBe(42);
  });

  it("error event устанавливает error и сбрасывает streaming", async () => {
    const events: SSEEvent[] = [
      { event: "error", data: { message: "Ошибка соединения", code: "mcp_error" } },
    ];
    vi.mocked(fetchChat).mockReturnValue(makeStream(events));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("вопрос");
    });

    expect(result.current.error).toBe("Ошибка соединения");
    expect(result.current.isStreaming).toBe(false);
  });

  it("isStreaming false после завершения", async () => {
    const events: SSEEvent[] = [
      { event: "done", data: { message_id: "m1", total_duration_ms: 10 } },
    ];
    vi.mocked(fetchChat).mockReturnValue(makeStream(events));

    const { result } = renderHook(() =>
      useChatStream({ sessionId: "s1", channelId: "ch1" }),
    );

    await act(async () => {
      await result.current.send("вопрос");
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });
  });
});
