import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

vi.mock("@/lib/storage", () => ({
  getStreamStepsExpanded: vi.fn(() => false),
  setStreamStepsExpanded: vi.fn(),
}));

import { StreamProgress } from "@/components/chat/StreamProgress";
import {
  getStreamStepsExpanded,
  setStreamStepsExpanded,
} from "@/lib/storage";
import type { Stage } from "@/components/chat/StreamingStages";

const mockGet = getStreamStepsExpanded as ReturnType<typeof vi.fn>;
const mockSet = setStreamStepsExpanded as ReturnType<typeof vi.fn>;

const stages: Stage[] = [{ kind: "analyzing" }];

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockReturnValue(false);
});

describe("StreamProgress", () => {
  it("свёрнут по умолчанию: видна строка-индикатор, НЕ виден детальный StreamingStages", () => {
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    expect(screen.getByTestId("stream-progress")).toBeInTheDocument();
    expect(screen.queryByTestId("streaming-stages")).not.toBeInTheDocument();
  });

  it("клик по тогглу разворачивает детальные шаги + пишет в storage", () => {
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    fireEvent.click(screen.getByTestId("stream-progress-toggle"));
    expect(screen.getByTestId("streaming-stages")).toBeInTheDocument();
    expect(mockSet).toHaveBeenCalledWith(true);
  });

  it("инициализируется развёрнутым, если в storage true", () => {
    mockGet.mockReturnValue(true);
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    expect(screen.getByTestId("streaming-stages")).toBeInTheDocument();
  });

  it("показывает живой таймер от startedAt", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000);
    try {
      render(<StreamProgress stages={stages} activeIndex={0} startedAt={1_000} />);
      act(() => {
        vi.setSystemTime(4_200);
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByTestId("stream-progress-timer").textContent).toContain("3");
    } finally {
      vi.useRealTimers();
    }
  });
});
