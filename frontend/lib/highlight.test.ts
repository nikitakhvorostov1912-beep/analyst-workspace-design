/**
 * Тесты для lib/highlight.ts — синтаксическая подсветка через prismjs.
 */

import { describe, expect, it } from "vitest";
import { highlight } from "./highlight";

describe("highlight", () => {
  it('BSL строка содержит class="token string"', () => {
    const result = highlight('"строка"', "bsl");
    expect(result).toContain('class="token string"');
  });

  it('SQL ключевое слово SELECT содержит class="token keyword"', () => {
    const result = highlight("SELECT id FROM table1", "sql");
    expect(result).toContain('class="token keyword"');
  });

  it('BSL число содержит class="token number"', () => {
    const result = highlight("123", "bsl");
    expect(result).toContain('class="token number"');
  });

  it('BSL ключевое слово Процедура содержит class="token keyword"', () => {
    const result = highlight("Процедура Имя()", "bsl");
    expect(result).toContain('class="token keyword"');
  });

  it("text language — экранирует HTML special chars", () => {
    const result = highlight("a & b < c > d", "text");
    expect(result).toContain("&amp;");
    expect(result).toContain("&lt;");
    expect(result).toContain("&gt;");
  });

  it("text language — <script> экранируется в &lt;script&gt;", () => {
    const result = highlight("<script>alert(1)</script>", "text");
    expect(result).toContain("&lt;script&gt;");
    expect(result).not.toContain("<script>");
  });

  it("BSL ВЫБРАТЬ → keyword token", () => {
    const result = highlight("ВЫБРАТЬ * ИЗ Справочник.Контрагенты", "bsl");
    expect(result).toContain('class="token keyword"');
  });
});
