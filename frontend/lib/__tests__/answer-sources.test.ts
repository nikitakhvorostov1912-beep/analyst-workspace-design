import { describe, expect, it } from "vitest";

import { deriveAnswerSources } from "../answer-sources";

describe("deriveAnswerSources", () => {
  it("buddy.* и search_its → ИТС", () => {
    expect(deriveAnswerSources([{ name: "buddy.search_its" }])).toEqual(["итс"]);
    expect(deriveAnswerSources([{ name: "buddy.fetch_its" }])).toEqual(["итс"]);
    expect(deriveAnswerSources([{ name: "search_its" }])).toEqual(["итс"]);
    expect(deriveAnswerSources([{ name: "search_bsp" }])).toEqual(["итс"]);
  });

  it("*_typical* → Типовая", () => {
    expect(deriveAnswerSources([{ name: "explain_typical_object" }])).toEqual([
      "типовая",
    ]);
    expect(deriveAnswerSources([{ name: "trace_typical_movements" }])).toEqual([
      "типовая",
    ]);
    expect(deriveAnswerSources([{ name: "compare_with_typical" }])).toEqual([
      "типовая",
    ]);
  });

  it("обычные MCP-инструменты → Ваша база", () => {
    expect(deriveAnswerSources([{ name: "get_metadata" }])).toEqual(["база"]);
    expect(deriveAnswerSources([{ name: "execute_query" }])).toEqual(["база"]);
  });

  it("служебные (memory_/todo_/clarify) не источник", () => {
    expect(
      deriveAnswerSources([
        { name: "memory_write" },
        { name: "todo_add" },
        { name: "clarify_question" },
      ]),
    ).toEqual([]);
  });

  it("несколько источников — стабильный порядок база→типовая→ИТС", () => {
    const got = deriveAnswerSources([
      { name: "buddy.search_its" },
      { name: "explain_typical_object" },
      { name: "get_metadata" },
    ]);
    expect(got).toEqual(["база", "типовая", "итс"]);
  });

  it("дедуп и пустой/без имени", () => {
    expect(
      deriveAnswerSources([
        { name: "execute_query" },
        { name: "get_metadata" },
        { name: "" },
        {},
      ]),
    ).toEqual(["база"]);
    expect(deriveAnswerSources([])).toEqual([]);
  });
});
