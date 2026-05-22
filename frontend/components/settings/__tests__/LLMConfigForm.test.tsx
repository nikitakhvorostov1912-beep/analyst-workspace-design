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

// Radix Select мок → нативный <select>, чтобы fireEvent.change мог сменить значение
// без поднятия portal и keyboard nav. SelectGroup/Label/Separator выпадают, чтобы
// option-элементы оказались плоско внутри <select> (HTML не любит вложенность).
vi.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (v: string) => void;
    children: React.ReactNode;
  }) => (
    <select
      data-testid="model-preset-select"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectGroup: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectLabel: () => null,
  SelectSeparator: () => null,
  SelectItem: ({ value, children }: { value: string; children: React.ReactNode }) => (
    <option value={value}>{children}</option>
  ),
}));

import { LLMConfigForm } from "../LLMConfigForm";
import {
  saveLLMConfig,
  testLLMConfig,
  deleteLLMConfig,
  updateLLMConfig,
} from "@/lib/api";
import { publishToast } from "@/lib/toast";
import { clearLLMApiKey, getLLMApiKey, setLLMApiKey } from "@/lib/api-keys";
import type { LLMConfigResponse } from "@/lib/types";

const makeLLMConfig = (): LLMConfigResponse => ({
  id: "default",
  endpoint: "https://api.xiaomimimo.com/v1",
  model: "mimo-v2.5-pro",
  temperature: 0.3,
});

const makeLLMConfigWithEnvKey = (): LLMConfigResponse => ({
  ...makeLLMConfig(),
  has_env_api_key: true,
});

describe("LLMConfigForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLLMApiKey).mockReturnValue(null);
  });

  it("рендерит дефолтный preset mimo-v2.5-pro и поле API ключа", () => {
    render(<LLMConfigForm initial={null} />);

    const select = screen.getByTestId("model-preset-select") as HTMLSelectElement;
    expect(select.value).toBe("mimo-v2.5-pro");
    expect(screen.getByPlaceholderText("sk-...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /сохранить/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /тест/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /удалить/i })).not.toBeInTheDocument();
  });

  it("показывает ошибку если api_key слишком короткий", async () => {
    render(<LLMConfigForm initial={null} />);

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

    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /тест/i }));
    });

    await waitFor(() => {
      expect(testLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://api.xiaomimimo.com/v1",
          model: "mimo-v2.5-pro",
        }),
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

    expect(screen.queryByPlaceholderText("sk-...")).not.toBeInTheDocument();
    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.getByText("Изменить ключ")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /удалить/i })).toBeInTheDocument();
  });

  it("нажатие Удалить + confirm вызывает deleteLLMConfig + clearLLMApiKey", async () => {
    vi.mocked(getLLMApiKey).mockReturnValue("sk-existing-key-abc");
    vi.mocked(deleteLLMConfig).mockResolvedValue();
    const onSaved = vi.fn();
    const config = makeLLMConfig();

    render(<LLMConfigForm initial={config} onSaved={onSaved} />);

    fireEvent.click(screen.getByRole("button", { name: /удалить/i }));

    await waitFor(() => {
      expect(screen.getByTestId("alert-dialog")).toHaveAttribute("data-open", "true");
    });

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

    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://api.xiaomimimo.com/v1",
          model: "mimo-v2.5-pro",
        }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("смена preset на MiMo Mini сохраняет с тем же endpoint MiMo", async () => {
    const saved = { ...makeLLMConfig(), model: "mimo-v2.5-mini" };
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "mimo-v2.5-mini" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://api.xiaomimimo.com/v1",
          model: "mimo-v2.5-mini",
        }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("смена preset на gpt-4o переключает endpoint на OpenAI", async () => {
    const saved = {
      ...makeLLMConfig(),
      endpoint: "https://api.openai.com/v1",
      model: "gpt-4o",
    };
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "gpt-4o" },
    });
    // Для OpenAI хинт ключа другой — sk-proj-...
    fireEvent.change(screen.getByPlaceholderText("sk-proj-..."), {
      target: { value: "sk-proj-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://api.openai.com/v1",
          model: "gpt-4o",
        }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("смена preset на claude-sonnet-4.5 переключает endpoint на OpenRouter", async () => {
    const saved = {
      ...makeLLMConfig(),
      endpoint: "https://openrouter.ai/api/v1",
      model: "anthropic/claude-sonnet-4.5",
    };
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "anthropic/claude-sonnet-4.5" },
    });
    fireEvent.change(screen.getByPlaceholderText("sk-or-v1-..."), {
      target: { value: "sk-or-v1-test123456" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://openrouter.ai/api/v1",
          model: "anthropic/claude-sonnet-4.5",
        }),
      );
    });
  });

  it("при выборе 'Произвольная модель' раскрывается advanced с полями custom", async () => {
    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "__custom__" },
    });

    // Появляется поле для произвольного идентификатора модели
    expect(
      screen.getByPlaceholderText(/gpt-4o, claude-3-5-sonnet/),
    ).toBeInTheDocument();
    // И поле для адреса сервера (placeholder — openai как типичный)
    expect(
      screen.getByPlaceholderText("https://api.openai.com/v1"),
    ).toBeInTheDocument();
  });

  it("при env-key + смене провайдера на OpenAI плашка ENV пропадает и появляется поле ввода ключа", () => {
    vi.mocked(getLLMApiKey).mockReturnValue(null);

    render(<LLMConfigForm initial={makeLLMConfigWithEnvKey()} onSaved={vi.fn()} />);

    // Дефолт — MiMo Pro, env-плашка видна
    expect(
      screen.getByText(/Ключ задан в окружении сервера/i),
    ).toBeInTheDocument();

    // Переключаемся на GPT-4o
    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "gpt-4o" },
    });

    // Плашки больше нет — нужно ввести свой ключ
    expect(
      screen.queryByText(/Ключ задан в окружении сервера/i),
    ).not.toBeInTheDocument();
    // Появилось поле ввода с openai-хинтом
    expect(screen.getByPlaceholderText("sk-proj-...")).toBeInTheDocument();
  });

  it("когда has_env_api_key=true и localStorage пуст — поле ключа не показывается, форма сохраняется без ввода ключа", async () => {
    vi.mocked(getLLMApiKey).mockReturnValue(null);
    vi.mocked(updateLLMConfig).mockResolvedValue(makeLLMConfigWithEnvKey());
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={makeLLMConfigWithEnvKey()} onSaved={onSaved} />);

    expect(screen.queryByPlaceholderText(/sk-/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Ключ задан в окружении сервера/i),
    ).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(updateLLMConfig).toHaveBeenCalled();
      expect(setLLMApiKey).not.toHaveBeenCalled();
      expect(onSaved).toHaveBeenCalled();
    });
  });
});
