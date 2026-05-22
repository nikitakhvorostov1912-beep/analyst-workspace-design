"""Тесты ResultSizeGate (P2.2, 2026-05-23).

Покрывает:
- apply_row_gate возвращает unchanged для не-row-bearing tools
- apply_row_gate возвращает unchanged для results < max_rows
- apply_row_gate cap'ит >max_rows + добавляет _result_gate metadata
- build_llm_summary_for_truncated даёт пустую строку для applied=False
- build_llm_summary_for_truncated даёт информативную строку для applied=True
- Гарантия immutability — original tool_result не мутирует
"""

from __future__ import annotations

import pytest

from app.orchestrator.result_gate import (
    MAX_ROWS_FOR_LLM,
    apply_row_gate,
    build_llm_summary_for_truncated,
)


class TestApplyRowGate:
    def test_non_row_bearing_tool_unchanged(self) -> None:
        """get_metadata не сканируется — возвращается as-is."""
        result = {"objects": ["Справочник.Контрагенты", "Документ.Реализация"]}
        capped, info = apply_row_gate("get_metadata", result)
        assert capped is result
        assert info == {"applied": False}

    def test_non_dict_result_unchanged(self) -> None:
        """Strings/lists/None возвращаются as-is."""
        for value in ["raw text", [1, 2, 3], None, 42]:
            capped, info = apply_row_gate("execute_query", value)
            assert capped is value
            assert info == {"applied": False}

    def test_dict_without_rows_unchanged(self) -> None:
        """execute_query c обёрткой MCP-content — пропускаем (gate работает с
        already-unwrapped структурой)."""
        result = {"content": [{"type": "text", "text": "..."}]}
        capped, info = apply_row_gate("execute_query", result)
        assert capped is result
        assert info == {"applied": False}

    def test_rows_below_cap_unchanged(self) -> None:
        """Если rows ≤ MAX_ROWS_FOR_LLM → no cap, но возвращается информация."""
        result = {
            "columns": [{"name": "id", "type": "Number"}],
            "rows": [[i] for i in range(100)],
        }
        capped, info = apply_row_gate("execute_query", result)
        # Same reference (no copy)
        assert capped is result
        assert info["applied"] is False
        assert info["original_rows"] == 100
        assert info["kept_rows"] == 100
        assert info["truncated"] is False

    def test_rows_above_cap_truncated(self) -> None:
        result = {
            "columns": [{"name": "id", "type": "Number"}],
            "rows": [[i] for i in range(1500)],
        }
        capped, info = apply_row_gate("execute_query", result)
        assert capped is not result  # copy
        assert len(capped["rows"]) == MAX_ROWS_FOR_LLM
        assert info["applied"] is True
        assert info["original_rows"] == 1500
        assert info["kept_rows"] == MAX_ROWS_FOR_LLM
        assert info["truncated"] is True

    def test_result_gate_metadata_added(self) -> None:
        """capped result имеет служебный `_result_gate` ключ для cards.py."""
        result = {
            "columns": [{"name": "id"}],
            "rows": [[i] for i in range(1000)],
        }
        capped, _ = apply_row_gate("execute_query", result)
        assert "_result_gate" in capped
        assert capped["_result_gate"]["truncated"] is True
        assert capped["_result_gate"]["total_rows"] == 1000

    def test_original_not_mutated(self) -> None:
        """ResultSizeGate не должен мутировать original — accumulated_tool_calls
        получает полный набор для persist'а."""
        rows_original = [[i] for i in range(2000)]
        result = {"columns": [{"name": "id"}], "rows": rows_original}
        _, _ = apply_row_gate("execute_query", result)
        assert len(result["rows"]) == 2000  # original не тронут
        assert "_result_gate" not in result

    def test_custom_max_rows(self) -> None:
        """max_rows можно переопределить для тестов / специфических use case."""
        result = {"columns": [{"name": "id"}], "rows": [[i] for i in range(20)]}
        capped, info = apply_row_gate("execute_query", result, max_rows=10)
        assert len(capped["rows"]) == 10
        assert info["original_rows"] == 20
        assert info["kept_rows"] == 10


class TestBuildLlmSummaryForTruncated:
    def test_no_summary_when_not_applied(self) -> None:
        assert build_llm_summary_for_truncated("execute_query", {"applied": False}) == ""

    def test_summary_mentions_numbers(self) -> None:
        info = {
            "applied": True,
            "original_rows": 5000,
            "kept_rows": 500,
            "truncated": True,
        }
        summary = build_llm_summary_for_truncated("execute_query", info)
        assert "5000" in summary
        assert "500" in summary
        # LLM нужно подсказать как помочь пользователю
        assert "CSV" in summary or "WHERE" in summary or "LIMIT" in summary

    def test_summary_starts_with_double_newline(self) -> None:
        """Format должен быть конкатенируемым с JSON-payload без слипания."""
        info = {"applied": True, "original_rows": 100, "kept_rows": 50}
        summary = build_llm_summary_for_truncated("execute_query", info)
        assert summary.startswith("\n\n[")


class TestEdgeCases:
    @pytest.mark.parametrize("size", [0, 1, MAX_ROWS_FOR_LLM, MAX_ROWS_FOR_LLM + 1])
    def test_boundary_sizes(self, size: int) -> None:
        result = {"columns": [{"name": "x"}], "rows": [[i] for i in range(size)]}
        capped, info = apply_row_gate("execute_query", result)
        if size <= MAX_ROWS_FOR_LLM:
            assert info["applied"] is False
            assert len(capped["rows"]) == size
        else:
            assert info["applied"] is True
            assert len(capped["rows"]) == MAX_ROWS_FOR_LLM

    def test_zero_rows_handled(self) -> None:
        """Пустой rows — pass-through без cap."""
        result = {"columns": [], "rows": []}
        capped, info = apply_row_gate("execute_query", result)
        assert capped is result
        assert info["truncated"] is False
