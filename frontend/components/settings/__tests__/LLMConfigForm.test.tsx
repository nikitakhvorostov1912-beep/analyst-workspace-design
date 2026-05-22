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

// P3.1 rev2 (2026-05-23): default — NVIDIA NIM Llama Nemotron Super 49B.
// NVIDIA выбран как база (вшитый ключ в installer, широкий каталог моделей).
// Cloud.ru — 152-ФЗ compliance альтернатива в каталоге.
const makeLLMConfig = (): LLMConfigResponse => ({
  id: "default",
  endpoint: "https://integrate.api.nvidia.com/v1",
  model: "nvidia/llama-3.3-nemotron-super-49b-v1.5",
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

  it("рендерит дефолтный preset Nemotron Super 49B и поле API ключа", () => {
    render(<LLMConfigForm initial={null} />);

    const select = screen.getByTestId("model-preset-select") as HTMLSelectElement;
    expect(select.value).toBe("nvidia/llama-3.3-nemotron-super-49b-v1.5");
    // NVIDIA keyHint содержит "nvapi-..." как substring.
    expect(screen.getByPlaceholderText(/nvapi-\.\.\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /сохранить/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /тест/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /удалить/i })).not.toBeInTheDocument();
  });

  it("показывает ошибку если api_key слишком короткий", async () => {
    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByPlaceholderText(/nvapi-\.\.\./), {
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

    fireEvent.change(screen.getByPlaceholderText(/nvapi-\.\.\./), {
      target: { value: "nvapi-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /тест/i }));
    });

    await waitFor(() => {
      expect(testLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://integrate.api.nvidia.com/v1",
          model: "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        }),
        "nvapi-test12345678",
      );
    });
  });

  it("показывает toast destructive при error_code=invalid_key", async () => {
    vi.mocked(testLLMConfig).mockResolvedValue({
      ok: false,
      error_code: "invalid_key",
    });

    render(<LLMConfigForm initial={null} />);

    fireEvent.change(screen.getByPlaceholderText(/nvapi-\.\.\./), {
      target: { value: "nvapi-test12345678" },
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

    expect(screen.queryByPlaceholderText(/nvapi-\.\.\./)).not.toBeInTheDocument();
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

  it("вызывает saveLLMConfig при valid submit без initial (default = NVIDIA Nemotron)", async () => {
    // P3.1 rev2 (2026-05-23): default preset изменён с Cloud.ru Qwen3 на
    // NVIDIA Llama Nemotron Super 49B (база с вшитым ключом).
    const saved = makeLLMConfig();
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByPlaceholderText(/nvapi-\.\.\./), {
      target: { value: "nvapi-test12345678" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://integrate.api.nvidia.com/v1",
          model: "nvidia/llama-3.3-nemotron-super-49b-v1.5",
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
    // После смены на MiMo placeholder ключа должен стать "sk-..." (P3.1 rev2: NVIDIA по дефолту, MiMo требует свой sk-... ключ)
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

  it("смена preset на deepseek-chat переключает endpoint на DeepSeek", async () => {
    // P3.1 rev2 (2026-05-23): OpenAI / Anthropic убраны из дефолтного UI.
    // Тестируем переключение на DeepSeek прямой API (дешёвый китайский).
    const saved = {
      ...makeLLMConfig(),
      endpoint: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
    };
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "deepseek-chat" },
    });
    // Для DeepSeek хинт sk-...
    fireEvent.change(screen.getByPlaceholderText("sk-..."), {
      target: { value: "sk-deepseektest12345" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://api.deepseek.com/v1",
          model: "deepseek-chat",
        }),
      );
      expect(onSaved).toHaveBeenCalled();
    });
  });

  it("смена preset на Cloud.ru Qwen3 переключает endpoint на cloud.ru (РФ-ДЦ)", async () => {
    // P3.1 rev2: Cloud.ru — 152-ФЗ compliance альтернатива в каталоге.
    const saved = {
      ...makeLLMConfig(),
      endpoint: "https://foundation-models.api.cloud.ru/v1",
      model: "Qwen/Qwen3-Coder-480B-A35B-Instruct",
    };
    vi.mocked(saveLLMConfig).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<LLMConfigForm initial={null} onSaved={onSaved} />);

    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "Qwen/Qwen3-Coder-480B-A35B-Instruct" },
    });
    fireEvent.change(screen.getByPlaceholderText(/sk-\.\.\..*Cloud\.ru/), {
      target: { value: "sk-cloudruTest1234" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(saveLLMConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          endpoint: "https://foundation-models.api.cloud.ru/v1",
          model: "Qwen/Qwen3-Coder-480B-A35B-Instruct",
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

  it("при env-key + смене провайдера на DeepSeek плашка ENV пропадает и появляется поле ввода ключа", () => {
    // P3.1 rev2: NVIDIA имеет встроенный env-ключ. При переключении на DeepSeek
    // (нет embedded key) плашка должна пропасть, появиться поле sk-... ввода.
    vi.mocked(getLLMApiKey).mockReturnValue(null);

    render(<LLMConfigForm initial={makeLLMConfigWithEnvKey()} onSaved={vi.fn()} />);

    // Дефолт — NVIDIA Nemotron Super (env-плашка видна т.к. NVIDIA вшит)
    expect(
      screen.getByText(/Ключ задан в окружении сервера/i),
    ).toBeInTheDocument();

    // Переключаемся на DeepSeek прямой API
    fireEvent.change(screen.getByTestId("model-preset-select"), {
      target: { value: "deepseek-chat" },
    });

    // Плашки больше нет — нужно ввести свой ключ
    expect(
      screen.queryByText(/Ключ задан в окружении сервера/i),
    ).not.toBeInTheDocument();
    // Появилось поле ввода с DeepSeek-хинтом
    expect(screen.getByPlaceholderText("sk-...")).toBeInTheDocument();
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
