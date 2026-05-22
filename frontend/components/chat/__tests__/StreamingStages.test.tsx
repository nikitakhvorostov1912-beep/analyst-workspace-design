import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StreamingStages, type Stage } from "@/components/chat/StreamingStages";

const PIPELINE: Stage[] = [
  { kind: "analyzing" },
  { kind: "tool", tool: "execute_query" },
  { kind: "tool_done", doneIn: 87 },
  { kind: "finalizing" },
];

describe("StreamingStages", () => {
  it("renders nothing when stages array is empty", () => {
    const { container } = render(<StreamingStages stages={[]} activeIndex={0} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders container with data-active-index", () => {
    render(<StreamingStages stages={PIPELINE} activeIndex={1} />);
    const root = screen.getByTestId("streaming-stages");
    expect(root).toHaveAttribute("data-active-index", "1");
    expect(root).toHaveAttribute("role", "status");
  });

  it("marks stages by state: done / active / future", () => {
    const { container } = render(
      <StreamingStages stages={PIPELINE} activeIndex={1} />,
    );

    const stages = container.querySelectorAll("[data-stage-kind]");
    expect(stages).toHaveLength(4);

    // index 0 → done (we're past it)
    expect(stages[0]).toHaveAttribute("data-stage-state", "done");
    // index 1 → active
    expect(stages[1]).toHaveAttribute("data-stage-state", "active");
    expect(stages[1]).toHaveAttribute("data-stage-kind", "tool");
    // index 2,3 → future
    expect(stages[2]).toHaveAttribute("data-stage-state", "future");
    expect(stages[3]).toHaveAttribute("data-stage-state", "future");
  });

  it("renders user-friendly Russian label for tool stage (W3.2)", () => {
    // W3.2 (2026-05-22): tool name НЕ должен светиться в UI как snake_case.
    // execute_query → «Выполняю запрос» (per CLAUDE.md «аналитик НЕ знает про MCP-tools»).
    render(<StreamingStages stages={PIPELINE} activeIndex={1} />);
    expect(screen.getByText("Выполняю запрос")).toBeInTheDocument();
    // raw snake_case НЕ должно быть видно
    expect(screen.queryByText("execute_query")).not.toBeInTheDocument();
  });

  it("renders tool_done with duration", () => {
    render(<StreamingStages stages={PIPELINE} activeIndex={2} />);
    expect(screen.getByText(/Получил данные \(87ms\)/)).toBeInTheDocument();
  });

  it("renders 'Анализирую…' with ellipsis on active analyzing stage", () => {
    render(
      <StreamingStages
        stages={[{ kind: "analyzing" }]}
        activeIndex={0}
      />,
    );
    expect(screen.getByText("Анализирую…")).toBeInTheDocument();
  });

  it("renders Learn stage with BookOpen label", () => {
    render(
      <StreamingStages
        stages={[{ kind: "learn" }, { kind: "finalizing" }]}
        activeIndex={0}
      />,
    );
    expect(screen.getByText(/Ищу прошлые ответы/)).toBeInTheDocument();
  });

  it("applies animate-spin only to active tool stage", () => {
    const { container } = render(
      <StreamingStages stages={PIPELINE} activeIndex={1} />,
    );
    const activeTool = container.querySelector(
      '[data-stage-kind="tool"][data-stage-state="active"]',
    );
    expect(activeTool?.querySelector(".animate-spin")).toBeInTheDocument();
  });
});
