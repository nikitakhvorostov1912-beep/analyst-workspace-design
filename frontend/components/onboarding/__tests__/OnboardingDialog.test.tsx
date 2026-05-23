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
  DialogTitle: ({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) => <h2 className={className}>{children}</h2>,
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

const PING_OK = {
  mcp_version: "2025-03-26",
  tool_count: 10,
  session_id: "test-session",
  duration_ms: 10,
};

/**
 * Helper: progress дviz через шаги 1→2→3 (до Learn step).
 * После вызова текущий шаг = 3 (Learn opt-in).
 */
async function advanceToLearnStep() {
  vi.mocked(pingConnection).mockResolvedValue(PING_OK);

  // Шаг 1 → Шаг 2
  await act(async () => {
    fireEvent.click(screen.getByTestId("mcp-save"));
  });
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
  });
  fireEvent.click(screen.getByRole("button", { name: /далее/i }));

  // Шаг 2 → Шаг 3
  await waitFor(() => {
    expect(screen.getByTestId("llm-form")).toBeInTheDocument();
  });
  fireEvent.click(screen.getByTestId("llm-save"));
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
  });
  fireEvent.click(screen.getByRole("button", { name: /далее/i }));

  await waitFor(() => {
    expect(screen.getByTestId("onboarding-step-learn")).toBeInTheDocument();
  });
}

describe("OnboardingDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    if (typeof window !== "undefined") {
      window.localStorage?.clear?.();
    }
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
    vi.mocked(pingConnection).mockResolvedValue(PING_OK);

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
    vi.mocked(pingConnection).mockResolvedValue(PING_OK);

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });

    fireEvent.click(screen.getByRole("button", { name: /далее/i }));

    await waitFor(() => {
      expect(screen.getByText("Подключите модель ИИ")).toBeInTheDocument();
      expect(screen.getByTestId("llm-form")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 5. Назад с шага 2 на шаг 1
  // ————————————————————
  it("кнопка «Назад» на шаге 2 — возвращает на шаг 1", async () => {
    vi.mocked(pingConnection).mockResolvedValue(PING_OK);

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("mcp-save"));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByText("Подключите модель ИИ")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /←\s*назад/i }));

    await waitFor(() => {
      expect(screen.getByText("Подключите вашу базу 1С")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 6. LLM save — «Далее» на шаге 2 активна
  // ————————————————————
  it("после save LLMConfigForm — кнопка «Далее» на шаге 2 активна", async () => {
    vi.mocked(pingConnection).mockResolvedValue(PING_OK);

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

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

    expect(screen.getByRole("button", { name: /далее/i })).toBeDisabled();

    fireEvent.click(screen.getByTestId("llm-save"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /далее/i })).not.toBeDisabled();
    });
  });

  // ————————————————————
  // 7. Переход на шаг 3 (Learn opt-in) — НОВОЕ ПОВЕДЕНИЕ (Phase 11.3)
  // ————————————————————
  it("после save LLM + click «Далее» — переходит на шаг 3 «Память» (Learn opt-in)", async () => {
    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await advanceToLearnStep();

    // Sprint 04 (O-4 + O-6): heading «Обучение на ваших чатах» → «Память по этой базе».
    expect(screen.getByText(/Память по этой базе/)).toBeInTheDocument();
    expect(screen.getByRole("switch")).toBeInTheDocument();
  });

  // ————————————————————
  // 8. Switch на шаге 3 — переключает state
  // ————————————————————
  it("на шаге 3 — переключение switch меняет aria-checked + показывает info-блок", async () => {
    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await advanceToLearnStep();

    const sw = screen.getByRole("switch");
    expect(sw).toHaveAttribute("aria-checked", "false");
    // Sprint 04 (O-4): «Готовим функцию обучения» → «Опция сохранена».
    expect(
      screen.queryByText(/Опция сохранена/),
    ).not.toBeInTheDocument();

    fireEvent.click(sw);
    expect(sw).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByText(/Опция сохранена/),
    ).toBeInTheDocument();
  });

  // ————————————————————
  // 9. Переход на шаг 4 (Готово) — после Learn step
  // ————————————————————
  it("после шага 3 + click «Далее» — переходит на шаг 4 «Готово!»", async () => {
    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await advanceToLearnStep();
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-step-done")).toBeInTheDocument();
      expect(screen.getByText("Готово!")).toBeInTheDocument();
    });
  });

  // ————————————————————
  // 10. Полный путь + «Начать работу» с learnOn=false
  // ————————————————————
  it("complete с learnOn=false → setOnboardingCompleted(true) + localStorage learn=false + onComplete вызван", async () => {
    const onComplete = vi.fn();

    render(
      <OnboardingDialog open={true} onComplete={onComplete} onSkip={vi.fn()} />,
    );

    await advanceToLearnStep();
    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByText("Готово!")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /начать работу/i }));

    expect(setOnboardingCompleted).toHaveBeenCalledWith(true);
    expect(onComplete).toHaveBeenCalledWith("conn-1");
    expect(window.localStorage.getItem("analyst.learn_enabled")).toBe("false");
  });

  // ————————————————————
  // 11. Полный путь + Learn включён → localStorage записан true
  // ————————————————————
  it("complete с learnOn=true → localStorage learn=true сохранён", async () => {
    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={vi.fn()} />,
    );

    await advanceToLearnStep();

    // Включаем Learn switch
    fireEvent.click(screen.getByRole("switch"));
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");

    fireEvent.click(screen.getByRole("button", { name: /далее/i }));
    await waitFor(() => {
      expect(screen.getByText("Готово!")).toBeInTheDocument();
    });
    expect(screen.getByText(/обучение/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /начать работу/i }));

    expect(window.localStorage.getItem("analyst.learn_enabled")).toBe("true");
  });

  // ————————————————————
  // 12. «Пропустить» с шага 1
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

  // ————————————————————
  // 13. «Пропустить» с шага 3 (Learn)
  // ————————————————————
  it("click «Пропустить» на шаге 3 (Learn) — setOnboardingCompleted(true) + onSkip вызван", async () => {
    const onSkip = vi.fn();

    render(
      <OnboardingDialog open={true} onComplete={vi.fn()} onSkip={onSkip} />,
    );

    await advanceToLearnStep();
    fireEvent.click(screen.getByRole("button", { name: /пропустить/i }));

    expect(setOnboardingCompleted).toHaveBeenCalledWith(true);
    expect(onSkip).toHaveBeenCalled();
  });
});
