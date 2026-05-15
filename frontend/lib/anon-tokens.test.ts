/**
 * Тесты anon-tokens утилит.
 * Plan 04-01.
 */

import { describe, expect, it } from "vitest";
import React from "react";
import { highlightAnonTokens, extractAnonTokens } from "./anon-tokens";

// ---------------------------------------------------------------------------
// highlightAnonTokens
// ---------------------------------------------------------------------------

describe("highlightAnonTokens", () => {
  it("возвращает text-only array для текста без токенов", () => {
    const result = highlightAnonTokens("Привет мир");
    expect(result).toEqual(["Привет мир"]);
  });

  it("выделяет токен amber span", () => {
    const result = highlightAnonTokens("Контрагент [ORG-001] оплатил");
    expect(result).toHaveLength(3);
    // Первый элемент — строка
    expect(result[0]).toBe("Контрагент ");
    // Второй — React-элемент с amber классом
    const el = result[1] as React.ReactElement;
    expect(el.type).toBe("span");
    expect((el.props as { className: string }).className).toContain("amber");
    expect((el.props as { children: string }).children).toBe("[ORG-001]");
    // Третий — строка
    expect(result[2]).toBe(" оплатил");
  });

  it("с replacements рендерит реальное значение emerald span", () => {
    const result = highlightAnonTokens("[INN-001]", { "[INN-001]": "7707123456" });
    expect(result).toHaveLength(1);
    const el = result[0] as React.ReactElement;
    expect(el.type).toBe("span");
    expect((el.props as { className: string }).className).toContain("emerald");
    expect((el.props as { children: string }).children).toBe("7707123456");
  });

  it("несколько токенов в одной строке", () => {
    const result = highlightAnonTokens("[ORG-001] + [INN-001]");
    // ["", React, " + ", React, ""] или ["" omit] - проверяем spans
    const spans = result.filter(
      (r) => typeof r !== "string"
    ) as React.ReactElement[];
    expect(spans).toHaveLength(2);
  });

  it("текст с только токеном без окружения", () => {
    const result = highlightAnonTokens("[FIO-001]");
    expect(result).toHaveLength(1);
    const el = result[0] as React.ReactElement;
    expect(el.type).toBe("span");
  });

  it("смешанные replacements: один раскрытый, один нет", () => {
    const result = highlightAnonTokens("[ORG-001] и [INN-001]", {
      "[ORG-001]": "ООО Ромашка",
    });
    const spans = result.filter(
      (r) => typeof r !== "string"
    ) as React.ReactElement[];
    expect(spans).toHaveLength(2);
    // Первый span — emerald (раскрытый)
    const span0 = spans[0];
    const span1 = spans[1];
    expect(span0).toBeDefined();
    expect(span1).toBeDefined();
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect((span0!.props as { className: string }).className).toContain("emerald");
    // Второй span — amber (нераскрытый)
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    expect((span1!.props as { className: string }).className).toContain("amber");
  });
});

// ---------------------------------------------------------------------------
// extractAnonTokens
// ---------------------------------------------------------------------------

describe("extractAnonTokens", () => {
  it("находит токены в строке", () => {
    const result = extractAnonTokens("[ORG-001] контрагент [INN-001]");
    expect(result).toContain("[ORG-001]");
    expect(result).toContain("[INN-001]");
  });

  it("обходит nested object", () => {
    const result = extractAnonTokens({
      header: { name: "[FIO-001]" },
      attributes: [{ value: "[INN-001]" }],
    });
    expect(result).toContain("[FIO-001]");
    expect(result).toContain("[INN-001]");
  });

  it("обходит nested array", () => {
    const result = extractAnonTokens([["[ORG-001]"], "[INN-001]"]);
    expect(result).toContain("[ORG-001]");
    expect(result).toContain("[INN-001]");
  });

  it("возвращает unique sorted", () => {
    const result = extractAnonTokens("[ORG-001] [ORG-001] [INN-001]");
    expect(result).toEqual(["[INN-001]", "[ORG-001]"]);
  });

  it("возвращает [] для null", () => {
    expect(extractAnonTokens(null)).toEqual([]);
  });

  it("возвращает [] для undefined", () => {
    expect(extractAnonTokens(undefined)).toEqual([]);
  });

  it("возвращает [] для числа", () => {
    expect(extractAnonTokens(42)).toEqual([]);
  });

  it("возвращает [] для текста без токенов", () => {
    expect(extractAnonTokens("ООО Ромашка")).toEqual([]);
  });
});
