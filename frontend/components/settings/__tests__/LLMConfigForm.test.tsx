import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

vi.mock("@/lib/api", () => ({
  saveLLMConfig: vi.fn(),
  updateLLMConfig: vi.fn(),
  deleteLLMConfig: vi.fn(),
  testLLMConfig: vi.fn(),
}));

vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

vi.mock("@/lib/api-keys", () => ({
  getLLMApiKey: vi.fn().mockReturnValue(null),
  setLLMApiKey: vi.fn(),
  clearLLMApiKey: vi.fn(),
}));

// AlertDialog — мокаем чтобы диалог всегда рендерился в DOM
vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ children, open }: { children: React.ReactNode; open?: boolean }) => (
    <div data-testid="alert-dialog" data-open={String(open)}>
      {open ? children : null}
    </div>
  ),
  AlertDialogContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-dialog-content">{children}</div>
  ),
  AlertDialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  AlertDialogFooter: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  AlertDialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  AlertDialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
  AlertDialogCancel: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button onClick={onClick} data-testid="alert-cancel">
      {children}
    </button>
  ),
  AlertDialogAction: ({
    children,
    onClick,
    className,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    className?: string;
  }) => (
    <button onClick={onClick} className={className} data-testid="alert-confirm">
      {children}
    </button>
  ),
}));

// Slider mock
vi.mock("@/components/ui/slider", () => ({
  Slider: ({ value, onValueChange }: { value: number[]; onValueChange: (v: number[]) => void }) => (
    <input
      type="range"
      data-testid="temperature-slider"
      value={value[0]}
      onChange={(e) => onValueChange([parseFloat(e.target.value)])}
      min={0}
      max={2}
      step={0.1}
    />
  ),
}));

import { LLMConfigForm } from "../LLMConfigForm";
import { saveLLMConfig, testLLMConfig, deleteLLMConfig } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import { clearLLMApiKey, getLLMApiKey } from "@/lib/api-keys";
import type { LLMConfigResponse } from "@/lib/types";

const makeLLMConfig = (): LLMConfigResponse => ({
  id: "default",
  endpoint: "http://localhost:1234/v1",
  model: "gpt-4o-mini",
  temperature: 0.3,
});

describe("LLMConfigForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLLMApiKey).mockReturnValue(null);
  });

  it("рендерит пустые поля без initial, Удалить не виден", () => {
    render(<LLMConfigForm initial={null} />);

    expect(screen.getByPlaceholderText("http://localhost:1234/v1")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /сохранить/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /тест/i })).toBeInTheDocument();
    // Нет кнопки Удалить
    expect(screen.queryByRole("button", { name: /удалить/i })).not.toBeInTheDocument();
  });

  it("показывает ошибку если api_key слишком короткий", async () => {
    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByPlaceholderText("http://localhost:1234/v1"), {
      target: { value: "http://localhost:1234/v1" },
    });
    fireEvent.change(screen.getByPlaceholderText("gpt-4o-mini"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "short" },
    });

    fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));

    await waitFor(() => {
      expect(screen.getByText("API ключ слишком короткий")).toBeInTheDocument();
    });
  });

  it("вызывает testLLMConfig с body+apiKey при valid данных", async () => {
    vi.mocked(testLLMConfig).mockResolvedValue({ ok: true, duration_ms: 100 });

    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByPlaceholderText("http://localhost:1234/v1"), {
      target: { value: "http://localhost:1234/v1" },
    });
    fireEvent.change(screen.getByPlaceholderText("gpt-4o-mini"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /тест/i }));
    });

    await waitFor(() => {
      expect(testLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({ endpoint: "http://localhost:1234/v1", model: "gpt-4o-mini" }),
        "sk-test12345678",
      );
    });
  });

  it("показывает toast destructive при error_code=invalid_key", async () => {
    vi.mocked(testLLMConfig).mockResolvedValue({
      ok: false,
      error_code: "invalid_key",
    });

    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByPlaceholderText("http://localhost:1234/v1"), {
      target: { value: "http://localhost:1234/v1" },
    });
    fireEvent.change(screen.getByPlaceholderText("gpt-4o-mini"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /тест/i }));
    });

    await waitFor(() => {
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          message: "Неверный API ключ",
        }),
      );
    });
  });

  it("рендерит •••••••• и кнопку Изменить ключ если initial + storedKey", () => {
    vi.mocked(getLLMApiKey).mockReturnValue("sk-existing-key-abc");
    const config = makeLLMConfig();

    render(<LLMConfigForm initial={config} />);

    // api_key input скрыт, показывается placeholder ••••••••
    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();
    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.getByText("Изменить ключ")).toBeInTheDocument();
    // Кнопка Удалить видна
    expect(screen.getByRole("button", { name: /удалить/i })).toBeInTheDocument();
  });

  it("нажатие Удалить + confirm вызывает deleteLLMConfig + clearLLMApiKey", async () => {
    vi.mocked(getLLMApiKey).mockReturnValue("sk-existing-key-abc");
    vi.mocked(deleteLLMConfig).mockResolvedValue();
    const onSaved = vi.fn();
    const config = makeLLMConfig();

    render(<LLMConfigForm initial={config} onSaved={onSaved} />);

    // Нажать кнопку Удалить
    fireEvent.click(screen.getByRole("button", { name: /удалить/i }));

    // Диалог открылся
    await waitFor(() => {
      expect(screen.getByTestId("alert-dialog")).toHaveAttribute("data-open", "true");
    });

    // Подтвердить
    await act(async () => {
      fireEvent.click(screen.getByTestId("alert-confirm"));
    });

    await waitFor(() => {
      expect(deleteLLMConfig).toHaveBeenCalled();
      expect(clearLLMApiKey).toHaveBeenCalled();
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("вызывает saveLLMConfig при valid submit без initial", async () => {
    const saved = makeLLMConfig();
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByPlaceholderText("http://localhost:1234/v1"), {
      target: { value: "http://localhost:1234/v1" },
    });
    fireEvent.change(screen.getByPlaceholderText("gpt-4o-mini"), {
      target: { value: "gpt-4o-mini" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({ endpoint: "http://localhost:1234/v1" }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });
});
