import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SessionList } from "../SessionList";
import type { SessionsGrouped } from "@/lib/types";

// next/link мокаем как простой <a>
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

const makeItem = (id: string, title: string | null, updated_at: string, message_count = 3) => ({
  id,
  title,
  channel_id: "ch-1",
  updated_at,
  message_count,
});

const NOW = new Date().toISOString();

describe("SessionList", () => {
  it("показывает 'Истории пока нет' если все группы пусты", () => {
    const empty: SessionsGrouped = {
      today: [],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    render(<SessionList grouped={empty} activeId={null} onDelete={() => {}} />);
    expect(screen.getByText("Истории пока нет")).toBeTruthy();
  });

  it("рендерит группу Сегодня если есть items", () => {
    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Запрос ОПП", NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    render(<SessionList grouped={grouped} activeId={null} onDelete={() => {}} />);
    expect(screen.getByText("Сегодня")).toBeTruthy();
    expect(screen.getByText("Запрос ОПП")).toBeTruthy();
  });

  it("скрывает пустые группы", () => {
    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Тест", NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    render(<SessionList grouped={grouped} activeId={null} onDelete={() => {}} />);
    expect(screen.queryByText("Вчера")).toBeNull();
    expect(screen.queryByText("На этой неделе")).toBeNull();
    expect(screen.queryByText("Раньше")).toBeNull();
  });

  it("показывает все 4 группы когда есть данные", () => {
    const yesterday = new Date(Date.now() - 86400000).toISOString();
    const week = new Date(Date.now() - 3 * 86400000).toISOString();
    const old = new Date(Date.now() - 30 * 86400000).toISOString();

    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Чат-1", NOW)],
      yesterday: [makeItem("s2", "Чат-2", yesterday)],
      this_week: [makeItem("s3", "Чат-3", week)],
      earlier: [makeItem("s4", "Чат-4", old)],
    };
    render(<SessionList grouped={grouped} activeId={null} onDelete={() => {}} />);
    // Используем getAllByText т.к. заголовок группы и title сессии могут совпадать
    expect(screen.getByText("Сегодня", { selector: "div.uppercase" })).toBeTruthy();
    expect(screen.getByText("Вчера", { selector: "div.uppercase" })).toBeTruthy();
    expect(screen.getByText("На этой неделе")).toBeTruthy();
    expect(screen.getByText("Раньше")).toBeTruthy();
  });

  it("title=null показывает 'Новый чат' italic", () => {
    const grouped: SessionsGrouped = {
      today: [makeItem("s1", null, NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    render(<SessionList grouped={grouped} activeId={null} onDelete={() => {}} />);
    const el = screen.getByText("Новый чат");
    expect(el).toBeTruthy();
    // italic class
    expect(el.className).toContain("italic");
  });

  it("активная сессия получает border-l-2 класс", () => {
    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Активная", NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    const { container } = render(
      <SessionList grouped={grouped} activeId="s1" onDelete={() => {}} />,
    );
    const link = container.querySelector("a[href='/sessions/s1']");
    expect(link?.className).toContain("border-l-2");
  });

  it("click на кнопку удаления вызывает onDelete после confirm", () => {
    const onDelete = vi.fn();
    // мокаем window.confirm → true
    vi.stubGlobal("confirm", () => true);

    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Удалить меня", NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    const { container } = render(
      <SessionList grouped={grouped} activeId={null} onDelete={onDelete} />,
    );

    const btn = container.querySelector("button[aria-label='Удалить сессию']");
    expect(btn).not.toBeNull();
    fireEvent.click(btn!);
    expect(onDelete).toHaveBeenCalledWith("s1");

    vi.unstubAllGlobals();
  });

  it("click на удаление с confirm=false НЕ вызывает onDelete", () => {
    const onDelete = vi.fn();
    vi.stubGlobal("confirm", () => false);

    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Не удалять", NOW)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    const { container } = render(
      <SessionList grouped={grouped} activeId={null} onDelete={onDelete} />,
    );
    const btn = container.querySelector("button[aria-label='Удалить сессию']");
    fireEvent.click(btn!);
    expect(onDelete).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("message_count отображается в meta строке", () => {
    const grouped: SessionsGrouped = {
      today: [makeItem("s1", "Тест", NOW, 42)],
      yesterday: [],
      this_week: [],
      earlier: [],
    };
    render(<SessionList grouped={grouped} activeId={null} onDelete={() => {}} />);
    expect(screen.getByText(/42 сообщ\./)).toBeTruthy();
  });
});
