import { describe, it, expect } from "vitest";
import { sessionToMarkdown, sessionExportFilename } from "../session-export";
import type { ChatMessage, SessionDetail } from "../types";

const detail: SessionDetail = {
  id: "11111111-2222-3333-4444-555555555555",
  title: "Анализ выручки и контрагенты",
  channel_id: "ch-1",
  created_at: "2026-05-19T10:30:00Z",
  updated_at: "2026-05-19T10:45:00Z",
};

const userMessage: ChatMessage = {
  id: "m1",
  role: "user",
  content: "Покажи 32 ОПП за 30.04 без шапки",
  created_at: "2026-05-19T10:31:00Z",
};

const assistantMessage: ChatMessage = {
  id: "m2",
  role: "assistant",
  content: "Нашёл 32 документа.",
  created_at: "2026-05-19T10:31:05Z",
  duration_ms: 4321,
  tool_calls: [
    {
      id: "tc-1",
      name: "execute_query",
      args: { query: "ВЫБРАТЬ ИЗ Документ.ОПП ГДЕ Дата = &Дата", params: { Дата: "2026-04-30" } },
      ok: true,
      duration_ms: 156,
      result: { rows: [["A", 1], ["B", 2]], total: 2 },
    },
  ],
  cards: [
    {
      type: "table",
      payload: {
        columns: [{ name: "name", type: "String" }, { name: "qty", type: "Number" }],
        rows: [["A", 1], ["B", 2]],
        total: 2,
        meta: { query: "Q1", duration_ms: 156 },
      },
    },
  ],
};

describe("sessionToMarkdown", () => {
  it("включает заголовок сессии и метаданные", () => {
    const md = sessionToMarkdown(detail, [userMessage]);
    expect(md).toContain("# Сессия: Анализ выручки и контрагенты");
    expect(md).toContain(detail.id);
    expect(md).toContain("ch-1");
    expect(md).toContain("сообщений: 1");
  });

  it("экспортирует user message с пометкой 'Вы'", () => {
    const md = sessionToMarkdown(detail, [userMessage]);
    expect(md).toContain("## 🟢 Вы");
    expect(md).toContain("Покажи 32 ОПП за 30.04 без шапки");
  });

  it("экспортирует tool_calls с аргументами и результатом", () => {
    const md = sessionToMarkdown(detail, [assistantMessage]);
    expect(md).toContain("Вызвано инструментов: 1");
    expect(md).toContain("`execute_query`");
    expect(md).toContain("✓"); // ok=true → галочка
    expect(md).toContain("Дата"); // в args
    expect(md).toContain("156 мс"); // duration_ms
    expect(md).toContain("Аргументы:");
    expect(md).toContain("Результат:");
  });

  it("экспортирует cards с типом и payload", () => {
    const md = sessionToMarkdown(detail, [assistantMessage]);
    expect(md).toContain("Карточки: 1");
    expect(md).toContain("`table`");
    expect(md).toContain('"columns"');
  });

  it("включает reasoning_content в спойлере если есть", () => {
    const withReasoning = {
      ...assistantMessage,
      reasoning_content: "Думаю шаг 1...\nДумаю шаг 2...",
    } as ChatMessage & { reasoning_content: string };
    const md = sessionToMarkdown(detail, [withReasoning]);
    expect(md).toContain("<details>");
    expect(md).toContain("reasoning");
    expect(md).toContain("Думаю шаг 1");
  });

  it("корректно обрабатывает пустую сессию без detail", () => {
    const md = sessionToMarkdown(null, []);
    expect(md).toContain("# Сессия: Без названия");
    expect(md).toContain("сообщений: 0");
  });

  it("обрезает длинные tool результаты с указанием полного размера", () => {
    const big = "A".repeat(5000);
    const msg: ChatMessage = {
      ...assistantMessage,
      tool_calls: [
        {
          id: "tc-2",
          name: "execute_query",
          args: {},
          ok: true,
          result: big,
        },
      ],
    };
    const md = sessionToMarkdown(detail, [msg]);
    expect(md).toContain("обрезано, всего 5000 символов");
  });

  it("показывает ошибку tool_call если есть", () => {
    const msg: ChatMessage = {
      ...assistantMessage,
      tool_calls: [
        {
          id: "tc-3",
          name: "execute_query",
          args: { q: "broken" },
          ok: false,
          error: "Синтаксическая ошибка запроса",
        },
      ],
    };
    const md = sessionToMarkdown(detail, [msg]);
    expect(md).toContain("✗"); // ok=false
    expect(md).toContain("**Ошибка:**");
    expect(md).toContain("Синтаксическая ошибка запроса");
  });

  it("включает duration_ms сообщения в заголовок", () => {
    const md = sessionToMarkdown(detail, [assistantMessage]);
    expect(md).toContain("4321 мс");
  });
});

describe("sessionExportFilename", () => {
  it("транслитерирует кириллический заголовок", () => {
    const fn = sessionExportFilename(detail);
    expect(fn).toBe("session-analiz-vyruchki-i-kontragenty.md");
  });

  it("использует первые символы id если title пуст", () => {
    const fn = sessionExportFilename({ ...detail, title: null });
    expect(fn).toMatch(/^session-[a-f0-9]{8}\.md$/);
  });

  it("возвращает untitled при пустом detail", () => {
    expect(sessionExportFilename(null)).toBe("session-untitled.md");
  });

  it("обрезает длинные slug до 60 символов", () => {
    const longTitle = "А".repeat(200);
    const fn = sessionExportFilename({ ...detail, title: longTitle });
    expect(fn.length).toBeLessThanOrEqual(`session-${"a".repeat(60)}.md`.length);
  });
});
