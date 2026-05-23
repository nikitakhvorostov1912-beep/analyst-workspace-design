import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

vi.mock("@/lib/api", () => ({
  createConnection: vi.fn(),
  updateConnection: vi.fn(),
  pingConnection: vi.fn(),
}));

vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

import { MCPConnectionForm } from "../MCPConnectionForm";
import { createConnection, updateConnection, pingConnection } from "@/lib/api";
import { publishToast } from "@/lib/toast";
import type { MCPConnection } from "@/lib/types";

const makeConn = (id = "c1"): MCPConnection => ({
  id,
  name: "Моя база",
  endpoint: "http://localhost:6010/mcp",
  channel: null,
  anon_enabled: false,
  kind: "embedded",
});

const makeProxyConn = (id = "c2"): MCPConnection => ({
  id,
  name: "Прод сервер",
  endpoint: "https://nikoiuy12-mcp-proxy.hf.space/mcp?channel=tranzit-prod",
  channel: "tranzit-prod",
  anon_enabled: false,
  kind: "proxy",
});

/** «Тип подключения» (embedded/proxy) теперь за «Расширенные настройки». */
function openAdvanced() {
  fireEvent.click(screen.getByRole("button", { name: /Расширенные настройки/i }));
}

describe("MCPConnectionForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("рендерит дефолтную форму с портом 6010 и embedded по умолчанию", () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    // Поле имени и порт — видимые верхнего уровня
    expect(screen.getByPlaceholderText("Моя база")).toBeInTheDocument();
    const portInput = screen.getByTestId("port-input") as HTMLInputElement;
    expect(portInput.value).toBe("6010");

    // Тип подключения скрыт за advanced — раскрываем чтобы проверить
    openAdvanced();
    expect(screen.getByTestId("kind-embedded")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByTestId("kind-proxy")).toHaveAttribute(
      "aria-checked",
      "false",
    );
    // Превью URL содержит порт (тоже в advanced)
    expect(screen.getByText(/http:\/\/localhost:6010\/mcp/)).toBeInTheDocument();
  });

  it("показывает ошибку 'Для прокси-подключения укажите профиль' если канал пустой", async () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    openAdvanced();
    fireEvent.click(screen.getByTestId("kind-proxy"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(
        screen.getByText("Для прокси-подключения укажите профиль"),
      ).toBeInTheDocument();
    });
  });

  it("вызывает createConnection с embedded payload при valid submit", async () => {
    const saved = makeConn();
    vi.mocked(createConnection).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<MCPConnectionForm onSaved={onSaved} />);

    fireEvent.change(screen.getByPlaceholderText("Моя база"), {
      target: { value: "Тест" },
    });
    fireEvent.change(screen.getByTestId("port-input"), {
      target: { value: "6020" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(createConnection).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Тест",
          endpoint: "http://localhost:6020/mcp",
          kind: "embedded",
        }),
      );
      expect(onSaved).toHaveBeenCalledWith(saved);
    });
  });

  it("вызывает createConnection с proxy payload + channel", async () => {
    const saved = makeProxyConn();
    vi.mocked(createConnection).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<MCPConnectionForm onSaved={onSaved} />);

    fireEvent.change(screen.getByPlaceholderText("Моя база"), {
      target: { value: "Прод сервер" },
    });
    openAdvanced();
    fireEvent.click(screen.getByTestId("kind-proxy"));
    fireEvent.change(screen.getByTestId("channel-input"), {
      target: { value: "tranzit-prod" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(createConnection).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Прод сервер",
          kind: "proxy",
          channel: "tranzit-prod",
          endpoint: expect.stringContaining("?channel=tranzit-prod"),
        }),
      );
      expect(onSaved).toHaveBeenCalledWith(saved);
    });
  });

  it("при редактировании embedded подключения подставляет порт из endpoint", () => {
    const conn = { ...makeConn(), endpoint: "http://localhost:6033/mcp" };

    render(<MCPConnectionForm initial={conn} onSaved={vi.fn()} />);

    const portInput = screen.getByTestId("port-input") as HTMLInputElement;
    expect(portInput.value).toBe("6033");

    openAdvanced();
    expect(screen.getByTestId("kind-embedded")).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("при редактировании proxy подключения автораскрывает advanced и подставляет канал", () => {
    const conn = makeProxyConn();

    render(<MCPConnectionForm initial={conn} onSaved={vi.fn()} />);

    // proxy → advanced раскрыт автоматически (parsed.kind === "proxy")
    expect(screen.getByTestId("kind-proxy")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    const channelInput = screen.getByTestId("channel-input") as HTMLInputElement;
    expect(channelInput.value).toBe("tranzit-prod");
  });

  it("вызывает updateConnection когда initial задан", async () => {
    const conn = makeConn();
    const updated = { ...conn, name: "Изменённое" };
    vi.mocked(updateConnection).mockResolvedValue(updated);
    const onSaved = vi.fn();

    render(<MCPConnectionForm initial={conn} onSaved={onSaved} />);

    const nameInput = screen.getByPlaceholderText("Моя база") as HTMLInputElement;
    expect(nameInput.value).toBe("Моя база");

    fireEvent.change(nameInput, { target: { value: "Изменённое" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(updateConnection).toHaveBeenCalledWith(
        "c1",
        expect.objectContaining({ name: "Изменённое", kind: "embedded" }),
      );
      expect(onSaved).toHaveBeenCalledWith(updated);
    });
  });

  it("кнопка Тест отключена без сохранённого id (new form)", () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    const testBtn = screen.getByRole("button", { name: /тест/i });
    expect(testBtn).toBeDisabled();
  });

  it("кнопка Тест вызывает pingConnection если initial существует", async () => {
    const conn = makeConn();
    vi.mocked(pingConnection).mockResolvedValue({
      mcp_version: "2025-03-26",
      tool_count: 5,
      session_id: "s1",
      duration_ms: 42,
    });

    render(<MCPConnectionForm initial={conn} onSaved={vi.fn()} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /тест/i }));
    });

    await waitFor(() => {
      expect(pingConnection).toHaveBeenCalledWith("c1");
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });
  });
});
