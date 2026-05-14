import { describe, it, expect } from "vitest";
import { buildCurlCommand } from "@/lib/curl-builder";
import type { ToolCallRecord } from "@/lib/types";

const makeTC = (overrides: Partial<ToolCallRecord> = {}): ToolCallRecord => ({
  id: "tc1",
  name: "execute_query",
  args: { query: "SELECT 1" },
  ...overrides,
});

describe("buildCurlCommand", () => {
  it("test_build_curl_command_minimal: содержит curl -X POST и endpoint", () => {
    const cmd = buildCurlCommand(makeTC(), "http://localhost:6010/mcp");
    expect(cmd).toContain("curl -X POST 'http://localhost:6010/mcp'");
    expect(cmd).toContain("-H 'Content-Type: application/json'");
    expect(cmd).toContain("-H 'Accept: application/json, text/event-stream'");
    expect(cmd).toContain("tools/call");
    expect(cmd).toContain("execute_query");
    expect(cmd).toContain("SELECT 1");
  });

  it("test_build_curl_command_with_session_id: включает Mcp-Session-Id header", () => {
    const cmd = buildCurlCommand(makeTC(), "http://localhost:6010/mcp", "abc-session");
    expect(cmd).toContain("-H 'Mcp-Session-Id: abc-session'");
  });

  it("test_build_curl_command_escapes_single_quotes_in_json: экранирует одинарные кавычки", () => {
    const tc = makeTC({ args: { q: "O'Brien" } });
    const cmd = buildCurlCommand(tc, "http://localhost:6010/mcp");
    // Одинарные кавычки в JSON должны быть экранированы для shell
    expect(cmd).toContain("'\\''");
  });

  it("test_build_curl_command_no_endpoint_placeholder: пустой endpoint → placeholder", () => {
    const cmd = buildCurlCommand(makeTC(), "");
    expect(cmd).toContain("<MCP_ENDPOINT>");
  });
});
