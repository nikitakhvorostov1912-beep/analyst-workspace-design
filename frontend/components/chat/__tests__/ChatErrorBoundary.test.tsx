import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatErrorBoundary } from "@/components/chat/ChatErrorBoundary";

function Boom(): never {
  throw new Error("Maximum update depth exceeded");
}

let errorSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  // React логирует пойманную ошибку в console.error — глушим шум теста.
  errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  errorSpy.mockRestore();
});

describe("ChatErrorBoundary", () => {
  it("рендерит детей, когда нет ошибки", () => {
    render(
      <ChatErrorBoundary>
        <div data-testid="ok-child">всё ок</div>
      </ChatErrorBoundary>,
    );
    expect(screen.getByTestId("ok-child")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-error-boundary")).not.toBeInTheDocument();
  });

  it("ловит render-ошибку ребёнка → показывает fallback + зовёт onError с componentStack", () => {
    const onError = vi.fn();
    render(
      <ChatErrorBoundary onError={onError}>
        <Boom />
      </ChatErrorBoundary>,
    );
    expect(screen.getByTestId("chat-error-boundary")).toBeInTheDocument();
    expect(onError).toHaveBeenCalledTimes(1);
    const [err, stack] = onError.mock.calls[0]!;
    expect((err as Error).message).toContain("Maximum update depth");
    expect(typeof stack).toBe("string");
    expect((stack as string).length).toBeGreaterThan(0);
  });
});
