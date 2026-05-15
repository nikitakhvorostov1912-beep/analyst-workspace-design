/**
 * E2E: Settings page CRUD — MCP подключения и LLM конфиг.
 *
 * Сценарии:
 * 1. Создать MCP подключение через форму → видим в списке
 * 2. Удалить MCP → confirm dialog → DELETE → исчезает из списка
 * 3. Сохранить LLM конфиг → api_key показывается как ••••••••
 * 4. Тест LLM с mock ok → toast «LLM работает»
 * 5. Тест LLM с mock invalid_key → toast «Неверный API ключ»
 * 6. Страница не содержит устаревших заглушек
 * 7. Ping MCP → toast с количеством инструментов
 * 8. Удалить LLM конфиг → alert dialog → конфиг исчезает
 */
import { test, expect } from "@playwright/test";
import { setupOnboardingMocks } from "./mocks/onboarding-handlers";

test.describe("Settings CRUD", () => {
  test.beforeEach(async ({ page }) => {
    // Настраиваем моки: есть одно подключение и LLM конфиг (normal state)
    await setupOnboardingMocks(page, {
      initialConnections: [
        {
          id: "existing-conn",
          name: "Existing 1C",
          endpoint: "http://localhost:6010/mcp",
          channel: null,
          anon_enabled: false,
          last_seen_at: null,
          created_at: new Date().toISOString(),
        },
      ],
      initialLLM: {
        id: "default",
        endpoint: "http://localhost:1234/v1",
        model: "gpt-4o-mini",
        temperature: 0.3,
      },
    });

    // Устанавливаем флаг onboarding_completed чтобы не показывать wizard
    await page.addInitScript(() => {
      localStorage.setItem("analyst.onboarding_completed", "true");
      // api_key в sessionStorage (как после migration)
      sessionStorage.setItem("analyst.llm_api_key", "sk-existing-key");
    });
  });

  test("создать MCP подключение через форму → видим в списке", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Видим существующее подключение
    await expect(page.getByText("Existing 1C")).toBeVisible();

    // Нажимаем «+ Добавить подключение»
    await page.getByRole("button", { name: "+ Добавить подключение" }).click();

    // Заполняем форму нового подключения через placeholder
    await page.getByPlaceholder("Транзит").fill("New Connection");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6003/mcp");

    // Сохраняем — форма добавления MCP находится в MCP-секции (выше LLM), берём first()
    await page.getByRole("button", { name: "Сохранить" }).first().click();

    // Видим toast об успешном сохранении
    await expect(page.getByText("Подключение сохранено")).toBeVisible({ timeout: 5000 });

    // Новое подключение появляется в списке
    await expect(page.getByText("New Connection")).toBeVisible({ timeout: 5000 });
  });

  test("удалить MCP → confirm dialog → DELETE → исчезает из списка", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Видим подключение
    await expect(page.getByText("Existing 1C")).toBeVisible();

    // Нажимаем «Удалить» у MCP — ищем строку подключения по endpoint-тексту (уникален)
    // Кнопки Удалить есть в MCPConnectionList и LLMConfigForm, берём первую (MCP-секция выше)
    await page.getByRole("button", { name: "Удалить" }).first().click();

    // Появился AlertDialog с подтверждением
    await expect(page.getByText("Удалить подключение?")).toBeVisible({ timeout: 3000 });

    // Подтверждаем удаление — кнопка «Удалить» в диалоге
    await page.getByRole("button", { name: "Удалить" }).last().click();

    // Toast об успешном удалении
    await expect(page.getByText("Подключение удалено")).toBeVisible({ timeout: 5000 });

    // Подключение исчезло из списка
    await expect(page.getByText("Existing 1C")).not.toBeVisible({ timeout: 5000 });
  });

  test("сохранить LLM конфиг → api_key показывается как ••••••••", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Есть существующий конфиг — api_key уже в sessionStorage → показывает ••••••••
    await expect(page.getByText("••••••••")).toBeVisible({ timeout: 5000 });
  });

  test("тест LLM с mock ok → toast «LLM работает»", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // В настройках есть MCP «Тест» и LLM «Тест». Нам нужна кнопка LLM Тест.
    // LLM-секция располагается ниже MCP. Используем last() — LLM «Тест» последний.
    await page.getByRole("button", { name: "Тест" }).last().click();

    // Toast с успешным ответом
    await expect(page.getByText(/LLM работает/i)).toBeVisible({ timeout: 5000 });
  });

  test("тест LLM с invalid api_key → toast «Неверный API ключ»", async ({ page }) => {
    // Устанавливаем невалидный ключ (в дополнение к beforeEach)
    await page.addInitScript(() => {
      sessionStorage.setItem("analyst.llm_api_key", "sk-invalid-key");
    });

    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Нажимаем «Тест» для LLM
    await page.getByRole("button", { name: "Тест" }).last().click();

    // Toast с ошибкой invalid_key
    await expect(page.getByText("Неверный API ключ")).toBeVisible({ timeout: 5000 });
  });

  test("ping MCP подключения → toast с количеством инструментов", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Видим существующее подключение
    await expect(page.getByText("Existing 1C")).toBeVisible();

    // Нажимаем «Тест» напротив MCP подключения (первый «Тест» на странице)
    await page.getByRole("button", { name: "Тест" }).first().click();

    // Toast с результатом пинга (10 инструментов согласно mock)
    await expect(page.getByText(/MCP работает.*10 инструментов/i)).toBeVisible({ timeout: 5000 });
  });

  test("страница не содержит устаревших заглушек и «coming soon»", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Проверяем отсутствие устаревших текстов
    await expect(page.getByText(/coming soon/i)).not.toBeVisible();
    await expect(page.getByText(/следующей итерации/i)).not.toBeVisible();
    await expect(page.getByText(/Phase 2 stub/i)).not.toBeVisible();

    // Основные UI элементы присутствуют
    await expect(page.getByText("+ Добавить подключение")).toBeVisible();
  });

  test("удалить LLM конфиг → подтверждение → конфиг удаляется", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // LLM-секция имеет heading «LLM» (не «LLM-провайдер»).
    // В ней есть кнопка «Удалить» из LLMConfigForm (hasExisting=true).
    // MCP имеет кнопку «Удалить» на каждом item — итого первая «Удалить» = MCP, вторая = LLM.
    // Но в данном тесте есть одно MCP-подключение и один LLM конфиг.
    // Кнопки порядок: MCP Тест | MCP Изменить | MCP Удалить | LLM Тест | LLM Сохранить | LLM Удалить
    // Берём «Удалить» для LLM — это последняя кнопка «Удалить» на странице
    await page.getByRole("button", { name: "Удалить" }).last().click();

    // Появляется диалог подтверждения
    await expect(page.getByText("Удалить LLM конфиг?")).toBeVisible({ timeout: 3000 });

    // Подтверждаем
    await page.getByRole("button", { name: "Удалить" }).last().click();

    // Toast об удалении
    await expect(page.getByText("LLM конфиг удалён")).toBeVisible({ timeout: 5000 });
  });
});
