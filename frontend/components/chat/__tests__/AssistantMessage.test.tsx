import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/storage", () => ({
  getStreamStepsExpanded: vi.fn(() => false),
  setStreamStepsExpanded: vi.fn(),
  getMCPConnections: vi.fn(() => []),
  getActiveChannelId: vi.fn(() => null),
}));

import { AssistantMessage } from "@/components/chat/AssistantMessage";
import type { ChatMessage } from "@/lib/types";

const baseMsg: ChatMessage = {
  id: "m1",
  role: "assistant",
  content: "",
  created_at: new Date(0).toISOString(),
  cards: [],
  tool_calls: [],
};

beforeEach(() => vi.clearAllMocks());

describe("AssistantMessage — индикатор стрима", () => {
  it("isStreaming=true БЕЗ streamingStage → StreamProgress виден сразу (фикс мёртвой зоны)", () => {
    render(
      <AssistantMessage
        message={baseMsg}
        isStreaming
        streamingStage={null}
        streamStartedAt={1000}
      />,
    );
    expect(screen.getByTestId("stream-progress")).toBeInTheDocument();
  });

  it("isStreaming=false + есть content + duration → маркер «готово за Xс»", () => {
    render(
      <AssistantMessage
        message={{ ...baseMsg, content: "Ответ", duration_ms: 4100 }}
        isStreaming={false}
        streamingStage={null}
      />,
    );
    expect(screen.getByTestId("done-marker").textContent).toMatch(/готово/i);
    expect(screen.queryByTestId("stream-progress")).not.toBeInTheDocument();
  });

  it("message.error → Alert + кнопка «Повторить» (если onRepeat задан)", () => {
    const onRepeat = vi.fn();
    render(
      <AssistantMessage
        message={{ ...baseMsg, error: { message: "[SSL] bad record mac", code: "llm_network_error" } }}
        isStreaming={false}
        streamingStage={null}
        onRepeat={onRepeat}
      />,
    );
    expect(screen.getByText(/SSL/)).toBeInTheDocument();
    const retry = screen.getByTestId("error-retry");
    retry.click();
    expect(onRepeat).toHaveBeenCalled();
  });
});
