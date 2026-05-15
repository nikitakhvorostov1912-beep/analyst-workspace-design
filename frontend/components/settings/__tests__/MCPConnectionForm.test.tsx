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
  name: "Транзит",
  endpoint: "http://localhost:6010/mcp",
  channel: null,
  anon_enabled: false,
});

describe("MCPConnectionForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("рендерит поля name/endpoint/channel без initial", () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    expect(screen.getByPlaceholderText("Транзит")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("http://localhost:6010/mcp"),
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText("default")).toBeInTheDocument();
  });

  it("показывает ошибку валидации при невалидном endpoint", async () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    // Ввести name и невалидный endpoint
    fireEvent.change(screen.getByPlaceholderText("Транзит"), {
      target: { value: "Мой сервер" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("http://localhost:6010/mcp"),
      { target: { value: "не-урл" } },
    );

    fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Должен быть валидный URL"),
      ).toBeInTheDocument();
    });
  });

  it("вызывает createConnection с корректным payload при valid submit", async () => {
    const saved = makeConn();
    vi.mocked(createConnection).mockResolvedValue(saved);
    const onSaved = vi.fn();

    render(<MCPConnectionForm onSaved={onSaved} />);

    fireEvent.change(screen.getByPlaceholderText("Транзит"), {
      target: { value: "Тест" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("http://localhost:6010/mcp"),
      { target: { value: "http://localhost:6010/mcp" } },
    );

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(createConnection).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Тест",
          endpoint: "http://localhost:6010/mcp",
        }),
      );
      expect(onSaved).toHaveBeenCalledWith(saved);
    });
  });

  it("вызывает updateConnection когда initial задан", async () => {
    const conn = makeConn();
    const updated = { ...conn, name: "Изменённое" };
    vi.mocked(updateConnection).mockResolvedValue(updated);
    const onSaved = vi.fn();

    render(<MCPConnectionForm initial={conn} onSaved={onSaved} />);

    // Поля предзаполнены
    const nameInput = screen.getByPlaceholderText("Транзит") as HTMLInputElement;
    expect(nameInput.value).toBe("Транзит");

    // Изменяем и сохраняем
    fireEvent.change(nameInput, { target: { value: "Изменённое" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /сохранить/i }));
    });

    await waitFor(() => {
      expect(updateConnection).toHaveBeenCalledWith(
        "c1",
        expect.objectContaining({ name: "Изменённое" }),
      );
      expect(onSaved).toHaveBeenCalledWith(updated);
    });
  });

  it("кнопка Тест отключена без сохранённого id (new form)", () => {
    render(<MCPConnectionForm onSaved={vi.fn()} />);

    // Кнопка Тест видна
    const testBtn = screen.getByRole("button", { name: /тест/i });
    expect(testBtn).toBeDisabled();
  });

  it("кнопка Тест вызывает pingConnection если initial существует и endpoint валидный", async () => {
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
