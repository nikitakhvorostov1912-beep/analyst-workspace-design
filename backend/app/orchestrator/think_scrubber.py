"""Think scrubber — stateful filter для reasoning блоков в streamed assistant text.

Sprint 4 (Hermes G7): защита от утечки `<think>`, `<thinking>`, `<reasoning>` тегов
из reasoning-model output во view пользователя.

Контекст:
- Xiaomi MiMo / DeepSeek R1 / Claude Sonnet 4.5 thinking mode возвращают reasoning
  через отдельное поле `delta.reasoning_content` — но иногда (баги стриминга)
  reasoning tag-блоки попадают в delta.content.
- Скраббер ловит открывающий tag, прячет всё до закрывающего, выводит только
  безопасный текст. Stateful — сохраняет «inside_think» между chunk'ами.

API:
    scrubber = ThinkScrubber()
    for chunk in stream:
        safe = scrubber.feed(chunk)
        if safe:
            yield safe
    final = scrubber.flush()  # на случай если поток оборвался внутри тега
"""

from __future__ import annotations

import re


# Регекспы — case-insensitive. Поддерживаем 3 распространённых тега.
_OPEN_RE = re.compile(r"<\s*(think|thinking|reasoning)\s*>", re.IGNORECASE)
_CLOSE_RE = re.compile(r"<\s*/\s*(think|thinking|reasoning)\s*>", re.IGNORECASE)

# Тег может прийти разорван на несколько chunks (например "<th", "ink>").
# Сохраняем "хвост" если он похож на начало незакрытого тега.
_PARTIAL_OPEN_RE = re.compile(r"<\s*(t(?:h(?:i(?:n(?:k(?:ing)?)?)?)?)?|r(?:e(?:a(?:s(?:o(?:n(?:i(?:n(?:g)?)?)?)?)?)?)?)?)?$", re.IGNORECASE)
_PARTIAL_CLOSE_RE = re.compile(r"<\s*/\s*(t(?:h(?:i(?:n(?:k(?:ing)?)?)?)?)?|r(?:e(?:a(?:s(?:o(?:n(?:i(?:n(?:g)?)?)?)?)?)?)?)?)?$", re.IGNORECASE)


class ThinkScrubber:
    """Stateful streaming scrubber для думающих моделей."""

    def __init__(self) -> None:
        self._inside_think = False
        self._pending = ""  # хвост текущего chunk на случай разорванного тега

    @property
    def inside_think(self) -> bool:
        """Сейчас внутри thinking-блока?"""
        return self._inside_think

    def feed(self, chunk: str) -> str:
        """Принимает кусок stream content. Возвращает безопасную часть.

        Args:
            chunk: сырой текст из delta.content.

        Returns:
            Очищенный текст. Может быть пустой строкой если весь chunk внутри
            <think>...</think>.
        """
        if not chunk:
            return ""

        buffer = self._pending + chunk
        self._pending = ""
        out_parts: list[str] = []
        i = 0
        n = len(buffer)

        while i < n:
            if self._inside_think:
                # Ищем закрывающий тег
                m = _CLOSE_RE.search(buffer, i)
                if m is None:
                    # Закрывающего нет в текущем буфере. Возможно он разорван —
                    # ищем частичный хвост.
                    tail = buffer[i:]
                    partial = _PARTIAL_CLOSE_RE.search(tail)
                    if partial:
                        self._pending = tail[partial.start():]
                    # Всё внутри think — выкидываем.
                    return "".join(out_parts)
                # Закрывающий найден — пропускаем до конца его
                self._inside_think = False
                i = m.end()
                continue
            # Не внутри think — ищем открывающий
            m = _OPEN_RE.search(buffer, i)
            if m is None:
                # Открывающего нет — возможно частичный.
                tail = buffer[i:]
                partial = _PARTIAL_OPEN_RE.search(tail)
                if partial:
                    out_parts.append(tail[: partial.start()])
                    self._pending = tail[partial.start():]
                else:
                    out_parts.append(tail)
                return "".join(out_parts)
            # Открывающий найден — выводим всё до него, входим в think.
            out_parts.append(buffer[i: m.start()])
            self._inside_think = True
            i = m.end()

        return "".join(out_parts)

    def flush(self) -> str:
        """Финализация: если что-то осталось в pending — возвращаем как есть.

        Если стрим оборвался внутри <think>, мы НЕ возвращаем содержимое —
        даже частичное, пользователь не должен видеть незавершённое reasoning.
        """
        if self._inside_think:
            self._pending = ""
            return ""
        out = self._pending
        self._pending = ""
        return out
