/**
 * E2E: First-run onboarding wizard (3 шага).
 *
 * Сценарии:
 * 1. Пустая БД + новый пользователь → показывает onboarding → проходит 3 шага
 * 2. «Пропустить» закрывает модалку и ставит флаг в localStorage
 * 3. Legacy: backend уже имеет данные → onboarding не показывается
 * 4. Повторный refresh → localStorage флаг = onboarding не открывается
 * 5. Шаг 1 «Далее» заблокирован до успешного пинга
 * 6. Шаг 2 «Далее» заблокирован до сохранения LLM
 * 7. Кнопка «← Назад» возвращает на шаг 1
 */
import { test, expect } from "@playwright/test";
import { setupOnboardingMocks } from "./mocks/onboarding-handlers";

test.describe("First-run onboarding", () => {
  test("показывает onboarding на пустой БД и проводит через 3 шага", async ({ page }) => {
    const start = Date.now();

    // Пустая БД + чистый localStorage (first-run)
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Шаг 1: видим wizard с заголовком
    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible({ timeout: 10000 });

    // Заполняем MCPConnectionForm через placeholders (labels не имеют htmlFor)
    await page.getByPlaceholder("Транзит").fill("Local 1C");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6010/mcp");

    // Сохраняем подключение
    await page.getByRole("button", { name: "Сохранить" }).click();

    // После onSaved → pingConnection → toast «MCP подключён»
    await expect(page.getByText("MCP подключён")).toBeVisible({ timeout: 10000 });

    // Кнопка «Далее» теперь активна (ping прошёл)
    const nextBtn = page.getByRole("button", { name: /Далее/ });
    await expect(nextBtn).not.toBeDisabled({ timeout: 10000 });
    await nextBtn.click();

    // Шаг 2: видим форму LLM
    await expect(page.getByText("Настройте LLM")).toBeVisible();

    // Заполняем LLMConfigForm — placeholders из LLMConfigForm.tsx
    await page.getByPlaceholder("http://localhost:1234/v1").fill("http://localhost:1234/v1");
    await page.getByPlaceholder("gpt-4o-mini").fill("gpt-4o-mini");
    await page.getByPlaceholder("sk-...").fill("sk-test-1234567890");

    // Тест LLM
    await page.getByRole("button", { name: "Тест" }).click();
    await expect(page.getByText(/LLM работает/i)).toBeVisible({ timeout: 10000 });

    // Сохраняем LLM конфиг
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("LLM конфиг сохранён")).toBeVisible({ timeout: 10000 });

    // «Далее» разблокирован (onSaved вызван)
    const nextBtn2 = page.getByRole("button", { name: /Далее/ });
    await expect(nextBtn2).not.toBeDisabled({ timeout: 10000 });
    await nextBtn2.click();

    // Шаг 3: экран «Готово»
    await expect(page.getByText("Готово!")).toBeVisible();

    // Завершаем onboarding
    await page.getByRole("button", { name: "Начать работу" }).click();

    // Модалка закрылась — заголовок шага 1 исчез
    await expect(page.getByText("Подключите вашу базу 1С")).not.toBeVisible({ timeout: 10000 });

    const elapsed = (Date.now() - start) / 1000;
    expect(elapsed).toBeLessThan(90);
  });

  test("«Пропустить» закрывает модалку и ставит флаг в localStorage", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Шаг 1 виден
    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible({ timeout: 10000 });

    // Кликаем «Пропустить» (кнопка Ghost в OnboardingDialog)
    await page.getByRole("button", { name: "Пропустить" }).click();

    // Модалка исчезла — заголовок h2 из диалога шага 1 пропал
    await expect(
      page.getByRole("heading", { name: "Подключите вашу базу 1С" })
    ).not.toBeVisible({ timeout: 10000 });

    // localStorage содержит флаг завершения
    const flag = await page.evaluate(() =>
      localStorage.getItem("analyst.onboarding_completed"),
    );
    expect(flag).toBe("true");
  });

  test("legacy: backend уже имеет данные → onboarding не показывается", async ({ page }) => {
    // Mock с данными (legacy user — уже настроено)
    await setupOnboardingMocks(page, {
      initialConnections: [
        {
          id: "c1",
          name: "Legacy 1C",
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

    // Нет флага onboarding_completed, но данные есть
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Модалка НЕ показывается — legacy guard определил что данные уже есть
    await expect(page.getByText("Подключите вашу базу 1С")).not.toBeVisible({ timeout: 10000 });
  });

  test("повторный refresh → onboarding не открывается когда флаг установлен", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });

    // Флаг уже установлен — должны сразу попасть на empty state (без onboarding)
    await page.addInitScript(() => {
      localStorage.setItem("analyst.onboarding_completed", "true");
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Модалка onboarding не открывается — конкретная фраза из DialogContent шага 1
    // (не путать с текстом empty state "Начните работу" и "Подключите вашу базу 1С через MCP")
    await expect(
      page.getByRole("heading", { name: "Подключите вашу базу 1С" })
    ).not.toBeVisible({ timeout: 10000 });
  });

  test("шаг 1: «Далее» заблокирован до успешного пинга", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible({ timeout: 10000 });

    // «Далее» изначально disabled (пинг не прошёл)
    const nextBtn = page.getByRole("button", { name: /Далее/ });
    await expect(nextBtn).toBeDisabled();
  });

  test("шаг 2: «Далее» заблокирован до сохранения LLM", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Проходим шаг 1
    await page.getByPlaceholder("Транзит").fill("Test Connection");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6010/mcp");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("MCP подключён")).toBeVisible({ timeout: 10000 });

    const nextBtn = page.getByRole("button", { name: /Далее/ });
    await expect(nextBtn).not.toBeDisabled({ timeout: 10000 });
    await nextBtn.click();

    // Шаг 2: «Далее» изначально disabled (LLM не сохранён)
    await expect(page.getByText("Настройте LLM")).toBeVisible();
    const nextBtn2 = page.getByRole("button", { name: /Далее/ });
    await expect(nextBtn2).toBeDisabled();
  });

  test("кнопка «← Назад» на шаге 2 возвращает на шаг 1", async ({ page }) => {
    await setupOnboardingMocks(page, { initialConnections: [], initialLLM: null });
    await page.addInitScript(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Шаг 1 → переходим на шаг 2
    await page.getByPlaceholder("Транзит").fill("Test");
    await page.getByPlaceholder("http://localhost:6010/mcp").fill("http://localhost:6010/mcp");
    await page.getByRole("button", { name: "Сохранить" }).click();
    await expect(page.getByText("MCP подключён")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: /Далее/ }).click();
    await expect(page.getByText("Настройте LLM")).toBeVisible();

    // Нажимаем «← Назад»
    await page.getByRole("button", { name: /Назад/ }).click();

    // Вернулись на шаг 1
    await expect(page.getByText("Подключите вашу базу 1С")).toBeVisible();
  });
});
