import { describe, it, expect } from "vitest";
import { buildStreamingStages } from "@/lib/streaming-stages";
import type { ToolCallRecord } from "@/lib/types";

const completedTool = (name: string, ms: number): ToolCallRecord => ({
  id: `tc-${name}`,
  name,
  args: {},
  duration_ms: ms,
  ok: true,
});

describe("buildStreamingStages", () => {
  it("возвращает null когда streamingStage=null (стриминг неактивен)", () => {
    const result = buildStreamingStages({
      streamingStage: null,
      currentToolName: null,
      toolCalls: [],
    });
    expect(result).toBeNull();
  });

  it("thinking — один analyzing stage, активный", () => {
    const result = buildStreamingStages({
      streamingStage: "thinking",
      currentToolName: null,
      toolCalls: [],
    });
    expect(result).not.toBeNull();
    expect(result?.stages).toEqual([{ kind: "analyzing" }]);
    expect(result?.activeIndex).toBe(0);
  });

  it("calling_tool без completed — analyzing + tool активный", () => {
    const result = buildStreamingStages({
      streamingStage: "calling_tool",
      currentToolName: "execute_query",
      toolCalls: [],
    });
    expect(result?.stages).toEqual([
      { kind: "analyzing" },
      { kind: "tool", tool: "execute_query" },
    ]);
    expect(result?.activeIndex).toBe(1);
  });

  it("calling_tool с одним completed tool — добавляет tool_done и текущий", () => {
    const result = buildStreamingStages({
      streamingStage: "calling_tool",
      currentToolName: "execute_query",
      toolCalls: [completedTool("get_metadata", 45)],
    });
    expect(result?.stages).toEqual([
      { kind: "analyzing" },
      { kind: "tool", tool: "get_metadata" },
      { kind: "tool_done", doneIn: 45 },
      { kind: "tool", tool: "execute_query" },
    ]);
    expect(result?.activeIndex).toBe(3);
  });

  it("calling_tool — если currentToolName совпадает с последним completed, не дублирует", () => {
    const result = buildStreamingStages({
      streamingStage: "calling_tool",
      currentToolName: "get_metadata",
      toolCalls: [completedTool("get_metadata", 30)],
    });
    expect(result?.stages).toEqual([
      { kind: "analyzing" },
      { kind: "tool", tool: "get_metadata" },
      { kind: "tool_done", doneIn: 30 },
    ]);
    expect(result?.activeIndex).toBe(2);
  });

  it("formatting — финализируется после всех completed", () => {
    const result = buildStreamingStages({
      streamingStage: "formatting",
      currentToolName: null,
      toolCalls: [
        completedTool("get_metadata", 20),
        completedTool("execute_query", 87),
      ],
    });
    expect(result?.stages).toEqual([
      { kind: "analyzing" },
      { kind: "tool", tool: "get_metadata" },
      { kind: "tool_done", doneIn: 20 },
      { kind: "tool", tool: "execute_query" },
      { kind: "tool_done", doneIn: 87 },
      { kind: "finalizing" },
    ]);
    expect(result?.activeIndex).toBe(5);
  });

  it("игнорирует tool_calls без duration_ms (не завершённые)", () => {
    const incomplete: ToolCallRecord = {
      id: "tc-partial",
      name: "execute_query",
      args: {},
      // no duration_ms
    };
    const result = buildStreamingStages({
      streamingStage: "thinking",
      currentToolName: null,
      toolCalls: [incomplete],
    });
    expect(result?.stages).toEqual([{ kind: "analyzing" }]);
  });

  it("calling_tool без currentToolName — pipeline без tool stage (edge case)", () => {
    const result = buildStreamingStages({
      streamingStage: "calling_tool",
      currentToolName: null,
      toolCalls: [],
    });
    expect(result?.stages).toEqual([{ kind: "analyzing" }]);
    expect(result?.activeIndex).toBe(0);
  });
});
