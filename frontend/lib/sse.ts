import type { SSEEvent } from "./types";

const KNOWN_EVENTS = new Set([
  "status",
  "delta",
  "tool_call",
  "tool_result",
  "card",
  "done",
  "error",
]);

/**
 * Парсит ReadableStream<Uint8Array> в AsyncIterable<SSEEvent>.
 * Формат: event: <name>\ndata: <json>\n\n (контракт backend Plan 01-01, IR-6)
 */
export async function* parseSSEStream(
  stream: ReadableStream<Uint8Array>,
): AsyncIterable<SSEEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();

  let buffer = "";
  let currentEvent = "";
  let dataLines: string[] = [];

  function* processBuffer(): Generator<SSEEvent> {
    // Разбиваем буфер на блоки (разделитель \n\n)
    const blocks = buffer.split("\n\n");
    // Последний элемент — незавершённый блок, оставляем в буфере
    buffer = blocks[blocks.length - 1] ?? "";

    for (let i = 0; i < blocks.length - 1; i++) {
      const block = blocks[i];
      if (!block || block.trim() === "") continue;

      currentEvent = "";
      dataLines = [];

      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataLines.push(line.slice(6));
        }
        // Игнорируем id:, retry:, комментарии (:)
      }

      if (!currentEvent || dataLines.length === 0) continue;

      const rawData = dataLines.join("\n");

      if (!KNOWN_EVENTS.has(currentEvent)) {
        yield {
          event: "error",
          data: { message: `Неизвестный тип события: ${currentEvent}`, code: "sse_parse" },
        };
        continue;
      }

      let parsed: unknown;
      try {
        parsed = JSON.parse(rawData);
      } catch {
        yield {
          event: "error",
          data: { message: "Ошибка парсинга JSON в SSE потоке", code: "sse_json" },
        };
        continue;
      }

      // Приводим к SSEEvent через промежуточный cast
      // (event проверен через KNOWN_EVENTS, data — unknown, runtime-safe)
      yield { event: currentEvent, data: parsed } as SSEEvent;
    }
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      yield* processBuffer();
    }

    // Финальный flush декодера
    buffer += decoder.decode();
    yield* processBuffer();
  } finally {
    reader.cancel().catch(() => {
      // Корректное завершение при cancel — игнорируем ошибку
    });
  }
}
