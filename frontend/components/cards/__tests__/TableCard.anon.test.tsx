/**
 * Тесты анонимизации TableCard.
 * Plan 04-01.
 */

import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TableCard } from "../TableCard";
import type { TableCardPayload } from "@/lib/types";

// Подавляем toast в тестах
vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

const payloadWithTokens: TableCardPayload = {
  columns: [
    { name: "Контрагент", type: "String" },
    { name: "ИНН", type: "String" },
  ],
  rows: [
    ["[ORG-001]", "[INN-001]"],
    ["[ORG-002]", "[INN-002]"],
  ],
  total: 2,
  meta: {},
  card_id: "card-uuid-001",
};

const payloadNoTokens: TableCardPayload = {
  columns: [{ name: "Имя", type: "String" }],
  rows: [["ООО Ромашка"]],
  total: 1,
  meta: {},
  card_id: "card-uuid-002",
};

// ---------------------------------------------------------------------------

describe("TableCard anon", () => {
  it("ячейки с [ORG-001] рендерятся с amber highlight классом", () => {
    render(<TableCard payload={payloadWithTokens} />);

    // Ищем span с amber классом
    const amberSpans = document.querySelectorAll(
      "span[class*='amber']",
    );
    expect(amberSpans.length).toBeGreaterThan(0);
    // Проверяем, что хотя бы один span содержит токен
    const tokenSpan = Array.from(amberSpans).find(
      (s) => s.textContent === "[ORG-001]",
    );
    expect(tokenSpan).toBeTruthy();
  });

  it("footer показывает кнопку «Раскрыть» при наличии токенов", () => {
    const onDeanonymize = vi.fn().mockResolvedValue({});
    render(<TableCard payload={payloadWithTokens} onDeanonymize={onDeanonymize} />);

    const btn = screen.getByText(/раскрыть реальные значения/i);
    expect(btn).toBeTruthy();
  });

  it("нет кнопки «Раскрыть» когда токенов нет", () => {
    render(<TableCard payload={payloadNoTokens} />);

    const btn = screen.queryByText(/раскрыть реальные значения/i);
    expect(btn).toBeNull();
  });

  it("клик «Раскрыть» → вызывает onDeanonymize с извлечёнными токенами", async () => {
    const mapping = {
      "[ORG-001]": "ООО Ромашка",
      "[INN-001]": "7707123456",
      "[ORG-002]": "ИП Иванов",
      "[INN-002]": "123456789012",
    };
    const onDeanonymize = vi.fn().mockResolvedValue(mapping);

    render(<TableCard payload={payloadWithTokens} onDeanonymize={onDeanonymize} />);

    const btn = screen.getByText(/раскрыть реальные значения/i);
    await act(async () => { fireEvent.click(btn); });

    expect(onDeanonymize).toHaveBeenCalledOnce();
    const calledTokens: string[] = (onDeanonymize.mock.calls[0] as unknown[])[0] as string[];
    expect(calledTokens).toContain("[ORG-001]");
    expect(calledTokens).toContain("[INN-001]");
  });

  it("после раскрытия кнопка исчезает, бейдж «Реальные значения» появляется", async () => {
    const mapping = {
      "[ORG-001]": "ООО Ромашка",
      "[INN-001]": "7707123456",
      "[ORG-002]": "ИП Иванов",
      "[INN-002]": "123456789012",
    };
    const onDeanonymize = vi.fn().mockResolvedValue(mapping);

    render(<TableCard payload={payloadWithTokens} onDeanonymize={onDeanonymize} />);

    const btn = screen.getByText(/раскрыть реальные значения/i);
    await act(async () => { fireEvent.click(btn); });

    await waitFor(() => {
      expect(screen.queryByText(/раскрыть реальные значения/i)).toBeNull();
      expect(screen.getByText(/реальные значения/i)).toBeTruthy();
    });
  });

  it("при ошибке onDeanonymize — вызывается publishToast", async () => {
    const { publishToast } = await import("@/lib/toast");
    const onDeanonymize = vi.fn().mockRejectedValue(new Error("MCP Error"));

    render(<TableCard payload={payloadWithTokens} onDeanonymize={onDeanonymize} />);

    const btn = screen.getByText(/раскрыть реальные значения/i);
    await act(async () => { fireEvent.click(btn); });

    await waitFor(() => {
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });
  });
});
