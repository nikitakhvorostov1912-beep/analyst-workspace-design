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

  // === W1.6: XSS-защита через двойной слой (Prism encode + DOMPurify) ===

  it("W1.6: <script> в SQL — не выполняется, санируется", () => {
    const payload = "SELECT * FROM users; <script>alert('xss')</script>";
    const result = highlight(payload, "sql");
    expect(result).not.toContain("<script>");
    expect(result).not.toContain("</script>");
  });

  it("W1.6: <img onerror=...> в BSL — НЕ исполняется (Prism encode'ит < в &lt;)", () => {
    const payload = `Сообщить("<img src=x onerror=alert(1)>");`;
    const result = highlight(payload, "bsl");
    // Не должно быть РЕАЛЬНОГО тега <img (только text/encoded &lt;img)
    expect(result).not.toMatch(/<img\s/i);
    // Encoded версия — допустима (это безопасный текст)
    expect(result).toContain("&lt;img");
  });

  it("W1.6: </span><script> — попытка вырваться из token закрывается", () => {
    const payload = `</span><script>alert(1)</script><span>`;
    const result = highlight(payload, "bsl");
    expect(result).not.toContain("<script");
    expect(result).not.toContain("</script>");
  });

  it("W1.6: javascript: ссылки — НЕ исполняются (нет реального <a> тега)", () => {
    const payload = `<a href="javascript:alert(1)">click</a>`;
    const result = highlight(payload, "bsl");
    // Не должно быть реального <a> тега
    expect(result).not.toMatch(/<a\s/i);
    expect(result).not.toMatch(/<a>/i);
    // <a> в исходнике превращается в encoded &lt;a (безопасный текст)
    expect(result).toContain("&lt;a");
  });

  it("W1.6: iframe полностью strip'ается", () => {
    const payload = `<iframe src="evil.com"></iframe>`;
    const result = highlight(payload, "json");
    expect(result).not.toContain("<iframe");
  });

  it("W1.6: разрешает span с class (Prism токены)", () => {
    const result = highlight("SELECT 1", "sql");
    // Whitelist не должен strip'ать корректную подсветку
    expect(result).toContain('<span class="token');
  });
});
