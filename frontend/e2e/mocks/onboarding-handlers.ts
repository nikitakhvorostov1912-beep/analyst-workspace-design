/**
 * Onboarding + Settings mock-обработчики для E2E тестов.
 *
 * Функция setupOnboardingMocks регистрирует все page.route() хендлеры
 * для backend API с closure-state (имитация persistence между запросами).
 */
import type { Page, Route } from "@playwright/test";
import type { MCPConnection, LLMConfigResponse } from "../../lib/types";

const BACKEND = "http://localhost:8010";

export interface OnboardingMockOpts {
  /** Начальный список MCP-подключений ([] = first-run) */
  initialConnections?: MCPConnection[];
  /** Начальный LLM конфиг (null = не настроен) */
  initialLLM?: LLMConfigResponse | null;
}

/**
 * Настраивает mock-обработчики для всех эндпоинтов onboarding + settings.
 * Использует closure-state для имитации persistence между запросами в тесте.
 */
export async function setupOnboardingMocks(
  page: Page,
  opts: OnboardingMockOpts = {},
): Promise<void> {
  // Closure state — имитируем backend между запросами
  let connections: MCPConnection[] = opts.initialConnections?.map((c) => ({
    ...c,
  })) ?? [];
  let llmConfig: LLMConfigResponse | null = opts.initialLLM ?? null;

  // --- /health ---
  await page.route(`${BACKEND}/health`, (route) =>
    route.fulfill({
      json: { status: "ok", version: "5.0.0", db: "ok" },
    }),
  );

  // --- /connections (GET / POST) ---
  await page.route(`${BACKEND}/connections`, async (route: Route) => {
    const method = route.request().method();

    if (method === "GET") {
      return route.fulfill({ json: { connections } });
    }

    if (method === "POST") {
      let body: Record<string, unknown> = {};
      try {
        body = (route.request().postDataJSON() as Record<string, unknown>) ?? {};
      } catch {
        // ignore parse errors
      }
      const newConn: MCPConnection = {
        id: `conn-${Date.now()}`,
        name: (body["name"] as string) ?? "New Connection",
        endpoint: (body["endpoint"] as string) ?? "",
        channel: (body["channel"] as string | null) ?? null,
        anon_enabled: (body["anon_enabled"] as boolean) ?? false,
        last_seen_at: null,
        created_at: new Date().toISOString(),
      };
      connections = [...connections, newConn];
      return route.fulfill({ status: 201, json: newConn });
    }

    return route.continue();
  });

  // --- /connections/:id (GET / DELETE) ---
  await page.route(`${BACKEND}/connections/*`, async (route: Route) => {
    const method = route.request().method();
    const url = route.request().url();

    // Ping — более специфичный маршрут, не перехватывать здесь
    if (url.includes("/ping") || url.includes("/test")) {
      return route.continue();
    }

    const id = url.split("/").pop() ?? "";

    if (method === "GET") {
      const conn = connections.find((c) => c.id === id);
      if (conn) return route.fulfill({ json: conn });
      return route.fulfill({ status: 404, json: { detail: "not found" } });
    }

    if (method === "DELETE") {
      connections = connections.filter((c) => c.id !== id);
      return route.fulfill({ status: 204, body: "" });
    }

    if (method === "PATCH" || method === "PUT") {
      let body: Record<string, unknown> = {};
      try {
        body = (route.request().postDataJSON() as Record<string, unknown>) ?? {};
      } catch {
        // ignore
      }
      const idx = connections.findIndex((c) => c.id === id);
      if (idx === -1) {
        return route.fulfill({ status: 404, json: { detail: "not found" } });
      }
      const updated: MCPConnection = {
        ...connections[idx]!,
        ...(body as Partial<MCPConnection>),
        id,
      };
      connections = connections.map((c) => (c.id === id ? updated : c));
      return route.fulfill({ json: updated });
    }

    return route.continue();
  });

  // --- /connections/:id/ping ---
  await page.route(`${BACKEND}/connections/*/ping`, (route) =>
    route.fulfill({
      json: {
        mcp_version: "1.0",
        tool_count: 10,
        session_id: "mock-session",
        duration_ms: 42,
        last_seen_at: new Date().toISOString(),
      },
    }),
  );

  // --- /llm-config (GET / POST / PATCH) ---
  await page.route(`${BACKEND}/llm-config`, async (route: Route) => {
    const method = route.request().method();

    if (method === "GET") {
      if (llmConfig === null) {
        // Backend возвращает HTTP 200 с null-телом когда конфиг не задан (не 404)
        return route.fulfill({
          status: 200,
          headers: { "content-type": "application/json" },
          body: "null",
        });
      }
      return route.fulfill({ json: llmConfig });
    }

    if (method === "POST") {
      let body: Record<string, unknown> = {};
      try {
        body = (route.request().postDataJSON() as Record<string, unknown>) ?? {};
      } catch {
        // ignore
      }
      llmConfig = {
        id: "default",
        endpoint: (body["endpoint"] as string) ?? "",
        model: (body["model"] as string) ?? "",
        temperature: (body["temperature"] as number) ?? 0.3,
      };
      return route.fulfill({ status: 201, json: llmConfig });
    }

    if (method === "PATCH" || method === "PUT") {
      let body: Record<string, unknown> = {};
      try {
        body = (route.request().postDataJSON() as Record<string, unknown>) ?? {};
      } catch {
        // ignore
      }
      if (llmConfig) {
        llmConfig = { ...llmConfig, ...(body as Partial<LLMConfigResponse>) };
      }
      return route.fulfill({ json: llmConfig ?? {} });
    }

    return route.continue();
  });

  // --- /llm-config/default (DELETE) ---
  await page.route(`${BACKEND}/llm-config/default`, async (route: Route) => {
    const method = route.request().method();
    if (method === "DELETE") {
      llmConfig = null;
      return route.fulfill({ status: 204, body: "" });
    }
    return route.continue();
  });

  // --- /llm-config/test (POST) ---
  await page.route(`${BACKEND}/llm-config/test`, async (route: Route) => {
    if (route.request().method() !== "POST") return route.continue();

    // Читаем api_key из заголовка X-LLM-API-Key
    const apiKey = route.request().headers()["x-llm-api-key"] ?? "";

    if (apiKey === "sk-invalid-key") {
      return route.fulfill({
        json: { ok: false, error_code: "invalid_key", duration_ms: 0 },
      });
    }

    return route.fulfill({
      json: { ok: true, duration_ms: 30 },
    });
  });

  // --- /sessions (GET / POST) ---
  await page.route(`${BACKEND}/sessions`, (route: Route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        json: { today: [], yesterday: [], this_week: [], earlier: [] },
      });
    }
    if (route.request().method() === "POST") {
      let body: Record<string, unknown> = {};
      try {
        body = (route.request().postDataJSON() as Record<string, unknown>) ?? {};
      } catch {
        // ignore
      }
      return route.fulfill({
        json: {
          id: `s-${Date.now()}`,
          title: null,
          channel_id: (body["channel_id"] as string) ?? "default",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
    }
    return route.continue();
  });
}
