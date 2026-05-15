import { describe, expect, it } from "vitest";
import { SLASH_COMMANDS, expandSlashCommand } from "./slash-commands";

describe("SLASH_COMMANDS", () => {
  it("has 5 items", () => {
    expect(SLASH_COMMANDS).toHaveLength(5);
  });

  it("contains sql, journal, find, audit, clear keys", () => {
    const keys = SLASH_COMMANDS.map((c) => c.key);
    expect(keys).toContain("sql");
    expect(keys).toContain("journal");
    expect(keys).toContain("find");
    expect(keys).toContain("audit");
    expect(keys).toContain("clear");
  });
});

describe("expandSlashCommand", () => {
  it("/sql SELECT 1 → prompt containing Выполни запрос and SELECT 1", () => {
    const result = expandSlashCommand("/sql SELECT 1");
    expect(result).not.toBeNull();
    expect("prompt" in result!).toBe(true);
    if (result && "prompt" in result) {
      expect(result.prompt).toContain("Выполни запрос");
      expect(result.prompt).toContain("SELECT 1");
    }
  });

  it("/clear → isClientAction clear", () => {
    const result = expandSlashCommand("/clear");
    expect(result).toEqual({ isClientAction: "clear" });
  });

  it("/journal Период=Час → prompt containing журнал", () => {
    const result = expandSlashCommand("/journal Период=Час");
    expect(result).not.toBeNull();
    if (result && "prompt" in result) {
      expect(result.prompt.toLowerCase()).toContain("журнал");
    }
  });

  it("/find Контрагент → prompt containing Найди where and Контрагент", () => {
    const result = expandSlashCommand("/find Контрагент");
    expect(result).not.toBeNull();
    if (result && "prompt" in result) {
      expect(result.prompt).toContain("Найди");
      expect(result.prompt).toContain("Контрагент");
    }
  });

  it("/audit Документ.ОПП → prompt containing аудит and Документ.ОПП", () => {
    const result = expandSlashCommand("/audit Документ.ОПП");
    expect(result).not.toBeNull();
    if (result && "prompt" in result) {
      expect(result.prompt.toLowerCase()).toContain("аудит");
      expect(result.prompt).toContain("Документ.ОПП");
    }
  });

  it("normal text → null", () => {
    const result = expandSlashCommand("normal text");
    expect(result).toBeNull();
  });

  it("/unknown args → null", () => {
    const result = expandSlashCommand("/unknown args");
    expect(result).toBeNull();
  });

  it("/sql without args → prompt containing Выполни запрос", () => {
    const result = expandSlashCommand("/sql");
    expect(result).not.toBeNull();
    if (result && "prompt" in result) {
      expect(result.prompt).toContain("Выполни запрос");
    }
  });

  it("empty string → null", () => {
    const result = expandSlashCommand("");
    expect(result).toBeNull();
  });
});
