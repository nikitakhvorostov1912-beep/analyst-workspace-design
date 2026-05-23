"""Unit-тесты для pure helpers из orchestrator.loop (P1.2 phase 1).

Покрытие:
- `_build_full_system_prompt` — сборка system prompt из 3 опциональных блоков
- `_finalize_streamed_tool_calls` — парсинг streaming tool_calls
- `_compute_tool_signature` — стабильная сигнатура для duplicate detector

Helpers намеренно не используют side-effects и не зависят от глобального
state — тестируются напрямую.
"""

from __future__ import annotations

from app.orchestrator.loop import (
    SYSTEM_PROMPT,
    _build_full_system_prompt,
    _compute_tool_signature,
    _finalize_streamed_tool_calls,
)


class TestBuildFullSystemPrompt:
    """`_build_full_system_prompt(mem, skills, todos)`"""

    def test_returns_only_static_when_all_empty(self) -> None:
        """Без опциональных блоков — только статика."""
        result = _build_full_system_prompt("", "", "")
        assert result == SYSTEM_PROMPT
        assert "\n\n" not in result.replace(SYSTEM_PROMPT, "")

    def test_appends_memory_block(self) -> None:
        result = _build_full_system_prompt("MEMORY: foo", "", "")
        assert result.startswith(SYSTEM_PROMPT)
        assert result.endswith("MEMORY: foo")
        assert "\n\nMEMORY: foo" in result

    def test_order_static_memory_skills_todos(self) -> None:
        """Порядок: SYSTEM_PROMPT → memory → skills → todos."""
        result = _build_full_system_prompt("MEM", "SKILLS", "TODOS")
        idx_static = result.find(SYSTEM_PROMPT[:50])
        idx_mem = result.find("MEM")
        idx_skills = result.find("SKILLS")
        idx_todos = result.find("TODOS")
        assert idx_static < idx_mem < idx_skills < idx_todos

    def test_skip_empty_middle_block(self) -> None:
        """Если skills пустой — между memory и todos один разделитель.

        Проверяем только область после SYSTEM_PROMPT (сам SYSTEM_PROMPT
        может содержать тройные \\n внутри — это его форматирование,
        не наша конкатенация).
        """
        result = _build_full_system_prompt("MEM", "", "TODOS")
        # Контракт: между memory и todos должен быть ОДИН разделитель \n\n,
        # не двойной. Проверяем по фрагменту "MEM\n\nTODOS".
        assert "MEM\n\nTODOS" in result
        assert "MEM\n\n\nTODOS" not in result

    def test_only_skills(self) -> None:
        result = _build_full_system_prompt("", "SK", "")
        assert result == f"{SYSTEM_PROMPT}\n\nSK"

    def test_only_todos(self) -> None:
        result = _build_full_system_prompt("", "", "T")
        assert result == f"{SYSTEM_PROMPT}\n\nT"


class TestFinalizeStreamedToolCalls:
    """`_finalize_streamed_tool_calls(chunk_tool_calls: dict)`"""

    def test_empty_input(self) -> None:
        assert _finalize_streamed_tool_calls({}) == []

    def test_single_call_valid_json(self) -> None:
        result = _finalize_streamed_tool_calls({
            0: {"id": "call_1", "name": "get_metadata", "arguments": '{"meta_type": "Документ"}'},
        })
        assert result == [
            {"id": "call_1", "name": "get_metadata", "args": {"meta_type": "Документ"}},
        ]

    def test_invalid_json_falls_back_to_empty_dict(self) -> None:
        """Невалидный JSON в arguments → пустой dict (fail-safe)."""
        result = _finalize_streamed_tool_calls({
            0: {"id": "call_1", "name": "broken", "arguments": "{not-json"},
        })
        assert result == [
            {"id": "call_1", "name": "broken", "args": {}},
        ]

    def test_empty_arguments_string(self) -> None:
        """Пустая строка arguments → пустой dict."""
        result = _finalize_streamed_tool_calls({
            0: {"id": "c", "name": "x", "arguments": ""},
        })
        assert result[0]["args"] == {}

    def test_whitespace_only_arguments(self) -> None:
        """Whitespace-only arguments — обрабатывается как пустой."""
        result = _finalize_streamed_tool_calls({
            0: {"id": "c", "name": "x", "arguments": "   \n  "},
        })
        assert result[0]["args"] == {}

    def test_preserves_index_order(self) -> None:
        """Result отсортирован по index (важно для parallel tool_calls)."""
        result = _finalize_streamed_tool_calls({
            2: {"id": "c2", "name": "second", "arguments": "{}"},
            0: {"id": "c0", "name": "first", "arguments": "{}"},
            1: {"id": "c1", "name": "middle", "arguments": "{}"},
        })
        names = [tc["name"] for tc in result]
        assert names == ["first", "middle", "second"]

    def test_default_arguments_when_missing(self) -> None:
        """Если arguments отсутствует — fallback на '{}'."""
        result = _finalize_streamed_tool_calls({
            0: {"id": "c", "name": "x"},
        })
        assert result[0]["args"] == {}

    def test_multiple_calls_with_real_args(self) -> None:
        result = _finalize_streamed_tool_calls({
            0: {"id": "a", "name": "execute_query", "arguments": '{"query": "ВЫБРАТЬ * ИЗ Документы"}'},
            1: {"id": "b", "name": "get_event_log", "arguments": '{"severity": "Error"}'},
        })
        assert len(result) == 2
        assert result[0]["args"]["query"].startswith("ВЫБРАТЬ")
        assert result[1]["args"]["severity"] == "Error"


class TestComputeToolSignature:
    """`_compute_tool_signature(finalized: list)` — для duplicate detector."""

    def test_empty_list(self) -> None:
        sig = _compute_tool_signature([])
        assert sig == "[]"

    def test_single_call(self) -> None:
        sig = _compute_tool_signature([
            {"id": "x", "name": "get_metadata", "args": {"meta_type": "Документ"}},
        ])
        # id игнорируется (LLM может генерить разные id для одинаковых
        # вызовов — это не должно ломать duplicate detector)
        assert '"get_metadata"' in sig
        assert '"meta_type": "\\u0414\\u043e\\u043a\\u0443\\u043c\\u0435\\u043d\\u0442"' in sig \
            or '"meta_type": "Документ"' in sig

    def test_signature_stable_across_arg_order(self) -> None:
        """Одинаковые args в разном порядке → одинаковая сигнатура (sort_keys=True)."""
        sig1 = _compute_tool_signature([
            {"id": "x", "name": "f", "args": {"a": 1, "b": 2}},
        ])
        sig2 = _compute_tool_signature([
            {"id": "y", "name": "f", "args": {"b": 2, "a": 1}},
        ])
        assert sig1 == sig2

    def test_signature_differs_when_args_differ(self) -> None:
        sig1 = _compute_tool_signature([
            {"id": "x", "name": "f", "args": {"a": 1}},
        ])
        sig2 = _compute_tool_signature([
            {"id": "x", "name": "f", "args": {"a": 2}},
        ])
        assert sig1 != sig2

    def test_signature_differs_when_names_differ(self) -> None:
        sig1 = _compute_tool_signature([
            {"id": "x", "name": "foo", "args": {}},
        ])
        sig2 = _compute_tool_signature([
            {"id": "x", "name": "bar", "args": {}},
        ])
        assert sig1 != sig2

    def test_unicode_preserved(self) -> None:
        """ensure_ascii=False — кириллица читабельна."""
        sig = _compute_tool_signature([
            {"id": "x", "name": "f", "args": {"тип": "Документ"}},
        ])
        assert "Документ" in sig

    def test_id_does_not_affect_signature(self) -> None:
        """LLM может для каждого вызова генерить новый id — сигнатура не зависит."""
        sig1 = _compute_tool_signature([
            {"id": "call_aaa", "name": "f", "args": {"x": 1}},
        ])
        sig2 = _compute_tool_signature([
            {"id": "call_bbb", "name": "f", "args": {"x": 1}},
        ])
        assert sig1 == sig2

    def test_multiple_calls_signature_combines_all(self) -> None:
        """Несколько parallel tool_calls — все в сигнатуре."""
        sig = _compute_tool_signature([
            {"id": "a", "name": "tool_a", "args": {}},
            {"id": "b", "name": "tool_b", "args": {"x": 1}},
        ])
        assert "tool_a" in sig
        assert "tool_b" in sig
