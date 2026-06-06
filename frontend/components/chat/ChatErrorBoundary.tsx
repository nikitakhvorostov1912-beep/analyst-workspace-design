"use client";

import { Component, type ReactNode } from "react";
import { Alert } from "@/components/ui/Alert";

/**
 * ChatErrorBoundary — изолирует render-сбой в области чата.
 *
 * Зачем: один «битый» рендер (например, бесконечный цикл setState →
 * «Maximum update depth») не должен валить весь чат. Boundary показывает
 * аккуратный fallback с кнопкой повтора и — главное — логирует
 * `componentStack` в console.error, чтобы точно знать компонент-виновник
 * при следующем срабатывании (текущая ошибка интермиттентная, стек нужен).
 *
 * Error boundary обязан быть классовым компонентом — у хуков нет аналога
 * componentDidCatch / getDerivedStateFromError.
 */

interface Props {
  children: ReactNode;
  /** Колбэк диагностики: (error, componentStack). */
  onError?: (error: Error, componentStack: string) => void;
}

interface State {
  error: Error | null;
}

export class ChatErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }): void {
    // Диагностика: точный компонент-виновник — в componentStack.
    console.error(
      "[ChatErrorBoundary] ошибка рендера в области чата:",
      error,
      info.componentStack,
    );
    this.props.onError?.(error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="p-4 max-w-3xl mx-auto" data-testid="chat-error-boundary">
          <Alert
            tone="error"
            title="Не удалось отобразить часть чата."
            description="Обновите страницу. Если повторяется — сообщите разработчику."
            actions={
              <button
                type="button"
                onClick={() => this.setState({ error: null })}
                className="inline-flex items-center h-7 px-2 rounded-md border border-[var(--error-40)] text-[12px] text-[var(--error)] hover:bg-[var(--error-12)] transition-colors"
              >
                Попробовать снова
              </button>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}
