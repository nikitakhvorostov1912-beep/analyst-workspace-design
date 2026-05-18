import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { Inbox } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";

describe("EmptyState", () => {
  it("renders only the title when nothing else is provided", () => {
    render(<EmptyState title="Нет сообщений" />);
    expect(screen.getByText("Нет сообщений")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders icon + description block", () => {
    const { container } = render(
      <EmptyState
        icon={Inbox}
        title="Пусто"
        description="Здесь появятся данные после первого запроса."
      />,
    );
    expect(screen.getByText("Пусто")).toBeInTheDocument();
    expect(screen.getByText(/Здесь появятся данные/)).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders CTA button and triggers onClick callback", () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        title="Начните"
        cta={{ label: "Создать сессию", onClick }}
      />,
    );
    const btn = screen.getByRole("button", { name: "Создать сессию" });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders CTA as anchor when href is provided", () => {
    render(
      <EmptyState
        title="Документация"
        cta={{ label: "Открыть", href: "/docs" }}
      />,
    );
    const link = screen.getByRole("link", { name: /Открыть/ });
    expect(link).toHaveAttribute("href", "/docs");
  });
});
