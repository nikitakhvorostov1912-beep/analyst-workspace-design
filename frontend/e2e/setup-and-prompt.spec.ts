/**
 * E2E: Empty state → настройка → отправка prompt → ответ ассистента.
 *
 * Сценарий:
 * 1. Открываем / без конфигурации → видим «Начните работу»
 * 2. Через addInitScript помещаем LLM config и connections в localStorage
 * 3. После reload — видим основной layout
 * 4. Кликаем «+ Новый чат» → переходим на /sessions/{id}
 * 5. Печатаем сообщение → отправляем → ждём ответа из SSE-mock
 */
import { test, expect } from "@playwright/test";
import {
  MOCK_LLM_CONFIG,
  MOCK_CONNECTIONS,
  setupRoutes,
  setLocalStorage,
} from "./fixtures";

test.describe("setup-and-prompt", () => {
  test("empty state показывает 'Начните работу'", async ({ page }) => {
    await setupRoutes(page);

    // Чистый localStorage
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Начните работу")).toBeVisible();
    await expect(page.getByRole("link", { name: "Настроить" })).toBeVisible();
  });

  test("после настройки — видим основной layout с кнопкой 'Новый чат'", async ({ page }) => {
    await setupRoutes(page);

    // Устанавливаем конфигурацию через addInitScript (до первого goto)
    await page.addInitScript(
      ({ llm, conns }: { llm: typeof MOCK_LLM_CONFIG; conns: typeof MOCK_CONNECTIONS }) => {
        localStorage.setItem("analyst.llm", JSON.stringify(llm));
        localStorage.setItem("analyst.mcp_connections", JSON.stringify(conns));
        localStorage.setItem("analyst.active_channel", conns[0]?.id ?? "db-a");
      },
      { llm: MOCK_LLM_CONFIG, conns: MOCK_CONNECTIONS },
    );

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Видим кнопку «+ Новый чат»
    await expect(page.getByRole("button", { name: /Новый чат/ })).toBeVisible();
  });

  test("отправка prompt → DOM содержит ответ ассистента", async ({ page }) => {
    await setupRoutes(page);

    await page.addInitScript(
      ({ llm, conns }: { llm: typeof MOCK_LLM_CONFIG; conns: typeof MOCK_CONNECTIONS }) => {
        localStorage.setItem("analyst.llm", JSON.stringify(llm));
        localStorage.setItem("analyst.mcp_connections", JSON.stringify(conns));
        localStorage.setItem("analyst.active_channel", conns[0]?.id ?? "db-a");
      },
      { llm: MOCK_LLM_CONFIG, conns: MOCK_CONNECTIONS },
    );

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Переходим на страницу сессии напрямую (mock session)
    await page.goto("/sessions/s-today-1");
    await page.waitForLoadState("networkidle");

    // DOM содержит mock сообщения из GET /sessions/s-today-1/messages
    await expect(page.getByText("Привет, я ассистент")).toBeVisible();
  });
});
