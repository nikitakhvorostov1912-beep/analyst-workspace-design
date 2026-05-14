import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ConfirmExecuteDialog } from "../ConfirmExecuteDialog";
import type { ConfirmRequiredPayload } from "@/lib/types";

// Mock @radix-ui/react-dialog Portal — в jsdom нет document.body для portals
vi.mock("@radix-ui/react-dialog", async () => {
  const actual = await vi.importActual<typeof import("@radix-ui/react-dialog")>("@radix-ui/react-dialog");
  return {
    ...actual,
    Portal: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

const payload: ConfirmRequiredPayload = {
  tool_call_id: "call-test-1",
  name: "execute_code",
  args: { code: "Контрагент.Удалить()" },
  reason: "keyword: Удалить",
};

describe("ConfirmExecuteDialog", () => {
  it("renders args and reason when open=true", () => {
    render(
      <ConfirmExecuteDialog
        open={true}
        payload={payload}
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByText(/keyword: Удалить/)).toBeInTheDocument();
    expect(screen.getByText(/Выполнить/)).toBeInTheDocument();
    expect(screen.getByText(/Отменить/)).toBeInTheDocument();
  });

  it("calls onResolve(true) when Выполнить clicked", () => {
    const onResolve = vi.fn();
    render(
      <ConfirmExecuteDialog
        open={true}
        payload={payload}
        onResolve={onResolve}
      />,
    );
    fireEvent.click(screen.getByText(/Выполнить/));
    expect(onResolve).toHaveBeenCalledWith(true);
    expect(onResolve).toHaveBeenCalledTimes(1);
  });

  it("calls onResolve(false) when Отменить clicked", () => {
    const onResolve = vi.fn();
    render(
      <ConfirmExecuteDialog
        open={true}
        payload={payload}
        onResolve={onResolve}
      />,
    );
    fireEvent.click(screen.getByText(/Отменить/));
    expect(onResolve).toHaveBeenCalledWith(false);
  });

  it("renders nothing meaningful when open=false", () => {
    render(
      <ConfirmExecuteDialog
        open={false}
        payload={payload}
        onResolve={vi.fn()}
      />,
    );
    // Диалог закрыт — кнопки не должны быть видимы
    expect(screen.queryByText(/Выполнить/)).not.toBeInTheDocument();
  });
});
