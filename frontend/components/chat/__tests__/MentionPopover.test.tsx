import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createRef } from "react";

// Мокируем api.ts
vi.mock("@/lib/api", () => ({
  metadataSuggest: vi.fn(),
}));

import { metadataSuggest } from "@/lib/api";
import { MentionPopover } from "../MentionPopover";
import type { MetadataSuggestResponse } from "@/lib/types";

const mockMetadataSuggest = vi.mocked(metadataSuggest);

const mockItems = [
  { object_type: "Документ", name: "ОПП", full_path: "Документ.ОПП", presentation: "Оформление перевозки" },
  { object_type: "Справочник", name: "Контрагенты", full_path: "Справочник.Контрагенты", presentation: null },
];

/** Flush all micro-tasks and pending promises */
function flushPromises() {
  return new Promise<void>((resolve) => setTimeout(resolve, 0));
}

describe("MentionPopover", () => {
  const anchorRef = createRef<HTMLElement>();

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("fetches metadata after debounce when query changes", async () => {
    const mockResp: MetadataSuggestResponse = { items: mockItems, cached: true, stale: false };
    mockMetadataSuggest.mockResolvedValue(mockResp);

    render(
      <MentionPopover
        open
        query="ОПП"
        channelId="ch-1"
        onSelect={vi.fn()}
        anchor={anchorRef}
      />
    );

    // До истечения debounce — fetch не вызван
    expect(mockMetadataSuggest).not.toHaveBeenCalled();

    // Продвигаем таймер
    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(mockMetadataSuggest).toHaveBeenCalledWith("ch-1", "ОПП");
  });

  it("renders items from response", async () => {
    const mockResp: MetadataSuggestResponse = { items: mockItems, cached: true, stale: false };
    mockMetadataSuggest.mockResolvedValue(mockResp);

    render(
      <MentionPopover
        open
        query="ОП"
        channelId="ch-1"
        onSelect={vi.fn()}
        anchor={anchorRef}
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });
    // Flush resolved promise
    await act(() => flushPromises());

    expect(screen.getByText("ОПП")).toBeInTheDocument();
    expect(screen.getByText("Контрагенты")).toBeInTheDocument();
  });

  it("shows empty state when items=[]", async () => {
    const mockResp: MetadataSuggestResponse = { items: [], cached: true, stale: false };
    mockMetadataSuggest.mockResolvedValue(mockResp);

    render(
      <MentionPopover
        open
        query="xyz"
        channelId="ch-1"
        onSelect={vi.fn()}
        anchor={anchorRef}
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });
    await act(() => flushPromises());

    expect(screen.getByText("Ничего не найдено")).toBeInTheDocument();
  });

  it("shows stale badge when response.stale=true", async () => {
    const mockResp: MetadataSuggestResponse = { items: mockItems, cached: true, stale: true };
    mockMetadataSuggest.mockResolvedValue(mockResp);

    render(
      <MentionPopover
        open
        query="ОП"
        channelId="ch-1"
        onSelect={vi.fn()}
        anchor={anchorRef}
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });
    await act(() => flushPromises());

    expect(screen.getByText("устаревший кеш")).toBeInTheDocument();
  });

  it("keyboard nav Enter triggers onSelect with active item", async () => {
    const mockResp: MetadataSuggestResponse = { items: mockItems, cached: true, stale: false };
    mockMetadataSuggest.mockResolvedValue(mockResp);
    const onSelect = vi.fn();

    render(
      <MentionPopover
        open
        query="ОП"
        channelId="ch-1"
        onSelect={onSelect}
        anchor={anchorRef}
      />
    );

    act(() => {
      vi.advanceTimersByTime(250);
    });
    await act(() => flushPromises());

    expect(screen.getByText("ОПП")).toBeInTheDocument();

    // Enter → onSelect с первым item
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    });

    expect(onSelect).toHaveBeenCalledWith(mockItems[0]);
  });

  it("listbox role present", () => {
    render(
      <MentionPopover
        open
        query="Д"
        channelId="ch-1"
        onSelect={vi.fn()}
        anchor={anchorRef}
      />
    );
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });
});
