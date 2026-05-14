/**
 * Утилита для формирования curl-команды из MCP tool call.
 * Используется в ToolTrace для кнопки «Скопировать как curl».
 * Plan 03-04 (TRACE-03).
 */

import type { ToolCallRecord } from "./types";

/**
 * Формирует curl-команду для вызова MCP tools/call endpoint.
 *
 * @param toolCall - запись о вызове инструмента
 * @param mcpEndpoint - URL MCP endpoint (если пустой → placeholder <MCP_ENDPOINT>)
 * @param mcpSessionId - опциональный Mcp-Session-Id header
 * @returns строка готовая для paste в терминал
 */
export function buildCurlCommand(
  toolCall: ToolCallRecord,
  mcpEndpoint: string,
  mcpSessionId?: string,
): string {
  const endpoint = mcpEndpoint || "<MCP_ENDPOINT>";

  const body = {
    jsonrpc: "2.0",
    id: 1,
    method: "tools/call",
    params: { name: toolCall.name, arguments: toolCall.args },
  };

  const headers: string[] = [
    "-H 'Content-Type: application/json'",
    "-H 'Accept: application/json, text/event-stream'",
  ];

  if (mcpSessionId) {
    headers.push(`-H 'Mcp-Session-Id: ${mcpSessionId}'`);
  }

  // Экранирование одинарных кавычек для shell: ' → '\''
  const jsonStr = JSON.stringify(body).replace(/'/g, "'\\''");

  return `curl -X POST '${endpoint}' \\\n  ${headers.join(" \\\n  ")} \\\n  -d '${jsonStr}'`;
}
