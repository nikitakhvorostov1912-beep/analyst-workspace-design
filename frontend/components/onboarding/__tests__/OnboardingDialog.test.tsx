import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

// Мокируем shadcn Dialog (Radix Portal не работает в jsdom)
vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
  }: {
    children: React.ReactNode;
    open?: boolean;
  }) => (open ? <div data-testid="dialog">{children}</div> : null),
  DialogContent: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="dialog-content">{children}</div>,
}));

// Мокируем MCPConnectionForm — упрощённая версия: поле name + кнопка Сохранить
vi.mock("@/components/settings/MCPConnectionForm", () => ({
  MCPConnectionForm: ({
    onSaved,
  }: {
    initial: null;
    onSaved: (conn: { id: string; name: string; endpoint: string; channel: null; anon_enabled: boolean }) => void;
  }) => (
    <div data-testid="mcp-form">
      <button
        data-testid="mcp-save"
        onClick={() =>
          onSaved({
            id: "conn-1",
            name: "Local",
            endpoint: "http://localhost:6010/mcp",
            channel: null,
            anon_enabled: false,
          })
        }
      >
        Сохранить MCP
      </button>
    </div>
  ),
}));

// Мокируем LLMConfigForm — кнопка Сохранить вызывает onSaved
vi.mock("@/components/settings/LLMConfigForm", () => ({
  LLMConfigForm: ({
    onSaved,
  }: {
    initial: null;
    onSaved?: () => void;
  }) => (
    <div data-testid="llm-form">
      <button
        data-testid="llm-save"
        onClick={() => onSaved?.()}
      >
        Сохранить LLM
      </button>
    </div>
  ),
}));

vi.mock("@/lib/api", () => ({
  pingConnection: vi.fn(),
}));

vi.mock("@/lib/onboarding-flag", () => ({
  getOnboardingCompleted: vi.fn().mockReturnValue(false),
  setOnboardingCompleted: vi.fn(),
}));

vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

import { OnboardingDialog } from "../OnboardingDialog";
import { pingConnection } from "@/lib/api";
import { setOnboardingCompleted } from "@/lib/onboarding-flag";
import { publishToast } from "@/lib/toast";

describe("OnboardingDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ————————————————————
  // 1. Начальный рендер
  // ————————————————————
  it("рендерит шаг 1 с MCP-формой и кнопкой «Далее» в disabled состоянии", () => {
    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    expect(screen.getByText("Подключите вашу базу 1С")).toBeInTheDocument();
    expect(screen.getByTestId("mcp-form")).toBeInTheDocument();
    const nextBtn = screen.getByRole("button", { name: /далее/i });
    expect(nextBtn).toBeDisabled();
  });

  // ————————————————————
  // 2. Успешный ping — кнопка «Далее» становится активной
  // ————————————————————
  it("после успешного save MCPConnectionForm + ping — кнопка «Далее» активна, toast success", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s1",
      duration_ms: 20,
    });

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });

    await waitFor(() => {
      expect(pingConnection).toHaveBeenCalledWith("conn-1");
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    const nextBtn = screen.getByRole("button", { name: /далее/i });
    expect(nextBtn).not.toBeDisabled();
  });

  // ————————————————————
  // 3. Провальный ping — «Далее» остаётся disabled
  // ————————————————————
  it("при ошибке ping — «Далее» остаётся disabled, toast с ошибкой", async () => {
    vi.mocked(pingConnection).mockRejectedValue(new Error("connection refused"));

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });

    await waitFor(() => {
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    const nextBtn = screen.getByRole("button", { name: /далее/i });
    expect(nextBtn).toBeDisabled();
  });

  // ————————————————————
  // 4. Переход на шаг 2
  // ————————————————————
  it("после успешного ping + click «Далее» — переходит на шаг 2 с LLM-формой", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s2",
      duration_ms: 15,
    });

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    // Сохраняем MCP — ping проходит
    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });

    // Переходим на шаг 2
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));

    await waitFor(() => {
      expect(screen.getByText("Настройте LLM")).toBeInTheDocument();
      expect(screen.getByTestId("llm-form")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 5. Назад с шага 2 на шаг 1
  // ————————————————————
  it("кнопка «Назад» на шаге 2 — возвращает на шаг 1", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s3",
      duration_ms: 10,
    });

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    // Переходим на шаг 2
    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByText("Настройте LLM")).toBeInTheDocument();
    });

    // Возврат назад
    fireEvent.click(screen.getByRole("button", { name: /←\s*назад/i }));

    await waitFor(() => {
      expect(screen.getByText("Подключите вашу базу 1С")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 6. LLM save — «Далее» на шаге 2 активна
  // ————————————————————
  it("после save LLMConfigForm — кнопка «Далее» на шаге 2 активна", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s4",
      duration_ms: 5,
    });

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    // Переходим на шаг 2
    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByTestId("llm-form")).toBeInTheDocument();
    });

    // «Далее» на шаге 2 должна быть disabled до сохранения
    expect(screen.getByRole("button", { name: /далее/i })).toBeDisabled();

    // Сохраняем LLM
    fireEvent.click(screen.getByTestId("llm-save"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
  });

  // ————————————————————
  // 7. Переход на шаг 3
  // ————————————————————
  it("после save LLM + click «Далее» — шаг 3 «Готово!» виден", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s5",
      duration_ms: 5,
    });

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    // Шаг 1 → 2
    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByTestId("llm-form")).toBeInTheDocument();
    });

    // Шаг 2: сохраняем LLM и переходим на 3
    fireEvent.click(screen.getByTestId("llm-save"));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));

    await waitFor(() => {
      expect(screen.getByText("Готово!")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 8. «Начать работу» на шаге 3
  // ————————————————————
  it("click «Начать работу» на шаге 3 — setOnboardingCompleted(true) + onComplete вызван", async () => {
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 10,
      session_id: "s6",
      duration_ms: 5,
    });
    const onComplete = vi.fn();

    render(
      <OnboardingDialog open={true} onComplete={onComplete} onSkip={vi.fn()} />,
    );

    // Прохождение всех шагов
    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByTestId("llm-form")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("llm-save"));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByText("Готово!")).toBeInTheDocument();
    });

    // Финальная кнопка
    fireEvent.click(screen.getByRole("button", { name: /начать работу/i }));

    expect(setOnboardingCompleted).toHaveBeenCalledWith(true);
    expect(onComplete).toHaveBeenCalledWith("conn-1");
  });

  // ————————————————————
  // 9. «Пропустить» с любого шага
  // ————————————————————
  it("click «Пропустить» на шаге 1 — setOnboardingCompleted(true) + onSkip вызван", () => {
    const onSkip = vi.fn();

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={onSkip} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /пропустить/i }));

    expect(setOnboardingCompleted).toHaveBeenCalledWith(true);
    expect(onSkip).toHaveBeenCalled();
  });
});
