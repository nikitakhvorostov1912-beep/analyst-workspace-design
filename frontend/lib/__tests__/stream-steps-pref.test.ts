import { describe, it, expect, beforeEach } from "vitest";
import {
  getStreamStepsExpanded,
  setStreamStepsExpanded,
} from "@/lib/storage";

beforeEach(() => {
  window.localStorage.clear();
});

describe("stream steps pref", () => {
  it("по умолчанию свёрнуто (false)", () => {
    expect(getStreamStepsExpanded()).toBe(false);
  });

  it("сохраняет true и читает обратно", () => {
    setStreamStepsExpanded(true);
    expect(getStreamStepsExpanded()).toBe(true);
  });

  it("сохраняет false", () => {
    setStreamStepsExpanded(true);
    setStreamStepsExpanded(false);
    expect(getStreamStepsExpanded()).toBe(false);
  });
});
