import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import { CopyButton } from "../CopyButton";

describe("CopyButton", () => {
  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("кнопка задизейблена при пустом value", () => {
    render(<CopyButton value="" />);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
  });

  it("копирует value в буфер обмена", async () => {
    render(<CopyButton value="http://localhost:6010/mcp" />);
    const btn = screen.getByRole("button");

    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("http://localhost:6010/mcp");
    });
  });

  it("показывает галочку «скопировано» после копирования", async () => {
    render(<CopyButton value="x" label="Скопировать адрес" />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("title", "Скопировать адрес");

    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() => {
      expect(btn).toHaveAttribute("title", "Скопировано");
    });
  });
});
