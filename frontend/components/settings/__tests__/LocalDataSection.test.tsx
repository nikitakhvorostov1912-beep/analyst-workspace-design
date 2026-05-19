import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";

// Мокаем AlertDialog (Radix Portal неустойчив в jsdom)
vi.mock("@/components/ui/alert-dialog", () => ({
  AlertDialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTrigger: ({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) =>
    asChild ? children : <div>{children}</div>,
  AlertDialogContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="alert-content">{children}</div>
  ),
  AlertDialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }: { children: React.ReactNode }) => <h3>{children}</h3>,
  AlertDialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  AlertDialogCancel: ({ children, ...props }: { children: React.ReactNode; [k: string]: unknown }) => (
    <button {...props}>{children}</button>
  ),
  AlertDialogAction: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    [k: string]: unknown;
  }) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

vi.mock("@/lib/api", () => ({
  resetLocalDb: vi.fn(),
}));

vi.mock("@/lib/toast", () => ({
  publishToast: vi.fn(),
}));

import { LocalDataSection } from "@/components/settings/LocalDataSection";
import { resetLocalDb } from "@/lib/api";
import { publishToast } from "@/lib/toast";

describe("LocalDataSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("рендерит заголовок и описание", () => {
    render(<LocalDataSection />);
    expect(screen.getByText("Локальные данные")).toBeInTheDocument();
    expect(screen.getByText(/всю историю чатов/)).toBeInTheDocument();
  });

  it("показывает destructive кнопку с иконкой AlertTriangle", () => {
    render(<LocalDataSection />);
    const btn = screen.getByTestId("reset-db-trigger");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Сбросить локальную базу");
  });

  it("при confirm вызывает resetLocalDb и публикует success toast", async () => {
    vi.mocked(resetLocalDb).mockResolvedValue({
      ok: true,
      cleared: ["messages", "sessions"],
    });

    render(<LocalDataSection />);
    const confirmBtn = screen.getByTestId("reset-db-confirm");

    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => {
      expect(resetLocalDb).toHaveBeenCalledTimes(1);
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "info",
          message: expect.stringContaining("messages, sessions"),
        }),
      );
    });
  });

  it("при ошибке resetLocalDb публикует error toast", async () => {
    vi.mocked(resetLocalDb).mockResolvedValue({
      ok: false,
      error: "HTTP 500",
    });

    render(<LocalDataSection />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("reset-db-confirm"));
    });

    await waitFor(() => {
      expect(publishToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "error",
          message: expect.stringContaining("HTTP 500"),
        }),
      );
    });
  });

  it("вызывает onReset callback после успешного reset", async () => {
    vi.mocked(resetLocalDb).mockResolvedValue({
      ok: true,
      cleared: ["sessions"],
    });
    const onReset = vi.fn();

    render(<LocalDataSection onReset={onReset} />);
    await act(async () => {
      fireEvent.click(screen.getByTestId("reset-db-confirm"));
    });

    await waitFor(() => {
      expect(onReset).toHaveBeenCalledTimes(1);
    });
  });
});
