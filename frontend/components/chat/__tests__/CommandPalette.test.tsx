import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  searchMessages: vi.fn(),
}));

import { searchMessages } from "@/lib/api";
import { CommandPalette } from "../CommandPalette";
import type { SearchResponse } from "@/lib/types";

const mockSearchMessages = vi.mocked(searchMessages);

const mockResults = [
  {
    session_id: "sess-1",
    session_title: "Тест сессии",
    message_id: "msg-1",
    snippet: "Текст с <mark>ключевым</mark> словом",
    created_at: "2026-05-15T10:00:00",
    channel_id: "ch-1",
  },
];

function flushPromises() {
  return new Promise<void>((resolve) => setTimeout(resolve, 0));
}

describe("CommandPalette", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockPush.mockClear();
  });

  afterEach(() => {
    vi.runAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("open=true renders search input", () => {
    render(<CommandPalette open onClose={vi.fn()} />);
    expect(screen.getByPlaceholderText(/поиск по сессиям/i)).toBeInTheDocument();
  });

  it("shows prompt to enter 2+ chars when opened", () => {
    render(<CommandPalette open onClose={vi.fn()} />);
    expect(screen.getByText(/минимум 2 символа/i)).toBeInTheDocument();
  });

  it("typing triggers fetch /search after debounce", async () => {
    const mockResp: SearchResponse = { results: mockResults, total: 1, query: "оп" };
    mockSearchMessages.mockResolvedValue(mockResp);

    render(<CommandPalette open onClose={vi.fn()} channelId="ch-1" />);
    const input = screen.getByPlaceholderText(/поиск по сессиям/i);

    fireEvent.change(input, { target: { value: "оп" } });

    // До дебаунса — fetch не вызван
    expect(mockSearchMessages).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(mockSearchMessages).toHaveBeenCalledWith("оп", "ch-1");
  });

  it("renders results after fetch", async () => {
    const mockResp: SearchResponse = { results: mockResults, total: 1, query: "ключевым" };
    mockSearchMessages.mockResolvedValue(mockResp);

    render(<CommandPalette open onClose={vi.fn()} />);
    const input = screen.getByPlaceholderText(/поиск по сессиям/i);

    fireEvent.change(input, { target: { value: "ключевым" } });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    await act(() => flushPromises());

    expect(screen.getByText("Тест сессии")).toBeInTheDocument();
  });

  it("click result → router.push called and onClose triggered", async () => {
    const mockResp: SearchResponse = { results: mockResults, total: 1, query: "ключевым" };
    mockSearchMessages.mockResolvedValue(mockResp);
    const onClose = vi.fn();

    render(<CommandPalette open onClose={onClose} />);
    const input = screen.getByPlaceholderText(/поиск по сессиям/i);
    fireEvent.change(input, { target: { value: "ключевым" } });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    await act(() => flushPromises());

    const resultBtn = screen.getByText("Тест сессии").closest("button")!;
    fireEvent.click(resultBtn);

    expect(onClose).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith(
      "/sessions/sess-1#message-msg-1"
    );
  });

  it("Escape closes the palette", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("displays platform hotkey label (Cmd+K or Ctrl+K)", () => {
    render(<CommandPalette open onClose={vi.fn()} />);
    const kbd = document.querySelector("kbd");
    expect(kbd).toBeInTheDocument();
    expect(["Cmd+K", "Ctrl+K"]).toContain(kbd?.textContent);
  });

  it("snippet HTML is escaped except mark tags (XSS protection)", async () => {
    const resultsWithXss: SearchResponse = {
      results: [
        {
          session_id: "s1",
          session_title: "Test",
          message_id: "m1",
          snippet: "<script>alert('xss')</script> <mark>найдено</mark>",
          created_at: "2026-05-15T10:00:00",
          channel_id: "ch-1",
        },
      ],
      total: 1,
      query: "найдено",
    };
    mockSearchMessages.mockResolvedValue(resultsWithXss);

    render(<CommandPalette open onClose={vi.fn()} />);
    const input = screen.getByPlaceholderText(/поиск по сессиям/i);
    fireEvent.change(input, { target: { value: "найдено" } });

    act(() => {
      vi.advanceTimersByTime(300);
    });
    await act(() => flushPromises());

    expect(screen.getByText("Test")).toBeInTheDocument();

    const paragraphs = document.querySelectorAll("p");
    const snippetPara = Array.from(paragraphs).find((p) =>
      p.innerHTML.includes("найдено")
    );
    expect(snippetPara).toBeDefined();
    // Script не должен быть исполнен — innerHTML не содержит открытый script тег
    expect(snippetPara?.innerHTML).not.toContain("<script>");
    expect(snippetPara?.innerHTML).toContain("<mark>");
  });
});
