import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { LogCard } from "../LogCard";
import type { LogCardPayload } from "@/lib/types";

function makePayload(overrides?: Partial<LogCardPayload>): LogCardPayload {
  return {
    entries: [
      { time: "2026-05-14T10:00:00Z", level: "Info", event: "_$Session$_.Start", user: "admin" },
      { time: "2026-05-14T10:01:00Z", level: "Warning", event: "_$Data$_.Update", user: "user1" },
      { time: "2026-05-14T10:02:00Z", level: "Error", event: "_$Access$_.Denied", user: "user2", comment: "Отказ в доступе" },
    ],
    next_cursor: null,
    ...overrides,
  };
}

describe("LogCard", () => {
  it("рендерит 3 записи (3 badge-элемента с уровнями)", () => {
    render(<LogCard payload={makePayload()} />);
    expect(screen.getByText("Info")).toBeTruthy();
    expect(screen.getByText("Warning")).toBeTruthy();
    expect(screen.getByText("Error")).toBeTruthy();
  });

  it("Critical запись имеет класс font-semibold", () => {
    const payload = makePayload({
      entries: [
        {
          time: "2026-05-14T10:00:00Z",
          level: "Critical",
          event: "_$Access$_.Hack",
        },
      ],
    });
    render(<LogCard payload={payload} />);
    const badge = screen.getByText("Critical");
    // badge имеет font-semibold в LEVEL_CLASSES["Critical"]
    expect(badge.className).toContain("font-semibold");
  });

  it("отображает время в ru-RU локали (toLocaleString)", () => {
    render(<LogCard payload={makePayload()} />);
    // Ожидаем что метки времени отрендерились (не пустые)
    const timeCells = screen.getAllByText(/2026/);
    expect(timeCells.length).toBeGreaterThan(0);
  });

  it("кнопка 'Загрузить ещё' disabled если нет onLoadMore", () => {
    const payload = makePayload({ next_cursor: "cursor_abc" });
    render(<LogCard payload={payload} />);
    const btn = screen.getByText("Загрузить ещё").closest("button");
    expect(btn).toBeTruthy();
    expect(btn).toBeDisabled();
  });

  it("кнопка 'Загрузить ещё' вызывает onLoadMore если передан", () => {
    const onLoadMore = vi.fn();
    const payload = makePayload({ next_cursor: "cursor_xyz" });
    render(<LogCard payload={payload} onLoadMore={onLoadMore} />);
    const btn = screen.getByText("Загрузить ещё").closest("button");
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn!);
    expect(onLoadMore).toHaveBeenCalledWith("cursor_xyz");
  });

  it("без next_cursor не показывает кнопку загрузки", () => {
    render(<LogCard payload={makePayload({ next_cursor: null })} />);
    expect(screen.queryByText("Загрузить ещё")).toBeNull();
  });

  it("comment отображается в details", () => {
    render(<LogCard payload={makePayload()} />);
    expect(screen.getByText("Комментарий")).toBeTruthy();
    // comment есть в DOM
    expect(screen.getByText("Отказ в доступе")).toBeTruthy();
  });

  it("пустой список entries показывает сообщение", () => {
    render(<LogCard payload={makePayload({ entries: [] })} />);
    expect(screen.getByText("Записи отсутствуют")).toBeTruthy();
  });
});

describe("LogCard load-more (wired)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("test_log_card_load_more_calls_api_and_appends_entries: клик загружает и аппендит новые записи, кнопка исчезает при null cursor", async () => {
    const newEntry = { time: "2026-05-14T11:00:00Z", level: "Info" as const, event: "new-event-e2" };
    const onLoadMore = vi.fn().mockResolvedValue({
      entries: [newEntry],
      next_cursor: null,
    });

    const payload = makePayload({ next_cursor: "cursor_abc" });
    render(<LogCard payload={payload} onLoadMore={onLoadMore} />);

    const btn = screen.getByText("Загрузить ещё").closest("button")!;
    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() => {
      expect(screen.getByText("new-event-e2")).toBeTruthy();
    });
    // кнопка должна исчезнуть когда next_cursor = null
    await waitFor(() => {
      expect(screen.queryByText("Загрузить ещё")).toBeNull();
    });
  });

  it("test_log_card_load_more_api_failure_shows_error_toast: ошибка load-more → dispatch toast error", async () => {
    const onLoadMore = vi.fn().mockRejectedValue(new Error("Network fail"));
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    const payload = makePayload({ next_cursor: "cursor_xyz" });
    render(<LogCard payload={payload} onLoadMore={onLoadMore} />);

    const btn = screen.getByText("Загрузить ещё").closest("button")!;
    await act(async () => {
      fireEvent.click(btn);
    });

    // Ожидаем что publishToast(error) был вызван
    const toastEvents = dispatchSpy.mock.calls.filter(
      ([e]) => e instanceof CustomEvent && (e as CustomEvent).type === "app:toast"
    );
    expect(toastEvents.length).toBeGreaterThan(0);
    const evt = toastEvents[0]![0] as CustomEvent;
    expect(evt.detail.type).toBe("error");
  });
});
