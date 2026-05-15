"""Расширенные тесты card-детектора: MetricCard, ReferencesCard, CodeCard (Plan 04-02)."""

import json

import pytest

from app.orchestrator.cards import (
    ColumnSchema,
    _build_code_card,
    _build_references_card,
    _dispatch_query_card,
    _find_period_column,
    _is_numeric_column,
    build_card_from_tool_result,
)

# ---------------------------------------------------------------------------
# Helpers для тестов
# ---------------------------------------------------------------------------

def _query_result(columns, rows):
    """Оборачивает columns+rows в стандартный формат."""
    return {"columns": columns, "rows": rows}


def _named_col(name: str, col_type: str = "String"):
    return {"name": name, "type": col_type}


# ---------------------------------------------------------------------------
# _is_numeric_column
# ---------------------------------------------------------------------------

def test_is_numeric_column_all_numbers():
    rows = [[1, "a"], [2, "b"], [3, "c"]]
    assert _is_numeric_column(rows, 0) is True


def test_is_numeric_column_with_bool_false():
    """bool — не числовой."""
    rows = [[True], [False]]
    assert _is_numeric_column(rows, 0) is False


def test_is_numeric_column_mixed_returns_false():
    rows = [[1], ["text"]]
    assert _is_numeric_column(rows, 0) is False


def test_is_numeric_column_empty_rows():
    assert _is_numeric_column([], 0) is False


# ---------------------------------------------------------------------------
# _find_period_column
# ---------------------------------------------------------------------------

def test_find_period_column_finds_период():
    cols = [ColumnSchema(name="Период", type="Date"), ColumnSchema(name="Сумма", type="Number")]
    assert _find_period_column(cols) == 0


def test_find_period_column_finds_date_alias():
    cols = [ColumnSchema(name="Сумма", type="Number"), ColumnSchema(name="Дата", type="Date")]
    assert _find_period_column(cols) == 1


def test_find_period_column_case_insensitive():
    cols = [ColumnSchema(name="period", type="String")]
    assert _find_period_column(cols) == 0


def test_find_period_column_not_found():
    cols = [ColumnSchema(name="Код", type="String"), ColumnSchema(name="Сумма", type="Number")]
    assert _find_period_column(cols) is None


# ---------------------------------------------------------------------------
# _dispatch_query_card — Path A: single metric
# ---------------------------------------------------------------------------

def test_dispatch_query_card_single_metric():
    """1 строка, 2 numeric cols → MetricCard, value из первой numeric col."""
    result = _query_result(
        [_named_col("Категория"), _named_col("Количество", "Number"), _named_col("Сумма, руб", "Number")],
        [["Электроника", 42, 1234567.5]],
    )
    card = _dispatch_query_card({}, result)
    assert card is not None
    assert card["type"] == "metric"
    assert card["payload"]["value"] == 42
    assert card["payload"]["label"] == "Количество"
    assert card["payload"]["sparkline"] is None
    assert card["payload"]["delta"] is None


def test_dispatch_query_card_single_metric_via_build_card():
    """execute_query → MetricCard через build_card_from_tool_result."""
    result = _query_result(
        [_named_col("Итого", "Number")],
        [[9999]],
    )
    card = build_card_from_tool_result("execute_query", {}, result)
    assert card is not None
    assert card["type"] == "metric"


# ---------------------------------------------------------------------------
# _dispatch_query_card — Path B: timeline with sparkline
# ---------------------------------------------------------------------------

def test_dispatch_query_card_timeline_with_period():
    """5 строк, колонка «Период» + «Сумма» → MetricCard со sparkline + delta."""
    rows = [
        ["2026-01-01", 100.0],
        ["2026-02-01", 120.0],
        ["2026-03-01", 110.0],
        ["2026-04-01", 130.0],
        ["2026-05-01", 150.0],
    ]
    result = _query_result(
        [_named_col("Период", "Date"), _named_col("Сумма", "Number")],
        rows,
    )
    card = _dispatch_query_card({}, result)
    assert card is not None
    assert card["type"] == "metric"
    assert card["payload"]["value"] == 150.0
    assert card["payload"]["label"] == "Сумма"
    assert card["payload"]["sparkline"] is not None
    assert len(card["payload"]["sparkline"]) == 5
    assert card["payload"]["delta"] is not None
    assert card["payload"]["delta"]["direction"] == "up"
    # delta value = 150 - 100 = 50
    assert card["payload"]["delta"]["value"] == pytest.approx(50.0)


def test_dispatch_query_card_timeline_with_date_alias():
    """«Дата» вместо «Период» → тоже MetricCard со sparkline."""
    rows = [["2026-01", 200], ["2026-02", 300], ["2026-03", 250]]
    result = _query_result(
        [_named_col("Дата"), _named_col("Объём", "Number")],
        rows,
    )
    card = _dispatch_query_card({}, result)
    assert card is not None
    assert card["type"] == "metric"
    assert card["payload"]["sparkline"] is not None


def test_dispatch_query_card_delta_negative():
    """Нисходящий тренд → direction down."""
    rows = [["Янв", 500], ["Фев", 400], ["Мар", 300]]
    result = _query_result(
        [_named_col("Месяц"), _named_col("Выручка", "Number")],
        rows,
    )
    card = _dispatch_query_card({}, result)
    assert card["payload"]["delta"]["direction"] == "down"
    assert card["payload"]["delta"]["value"] == pytest.approx(-200.0)


# ---------------------------------------------------------------------------
# _dispatch_query_card — Path C: fallback to TableCard
# ---------------------------------------------------------------------------

def test_dispatch_query_card_no_metric_falls_through_to_table():
    """multi-row без period column и без single-row → TableCard."""
    rows = [["A", "X"], ["B", "Y"]]
    result = _query_result(
        [_named_col("Код"), _named_col("Имя")],
        rows,
    )
    card = _dispatch_query_card({}, result)
    assert card is not None
    assert card["type"] == "table"


def test_dispatch_query_card_empty_rows_returns_none_or_table():
    """Пустые rows → TableCard или None, без исключения."""
    result = _query_result([_named_col("X")], [])
    card = _dispatch_query_card({}, result)
    # Пустая таблица возвращается как TableCard
    assert card is None or card["type"] == "table"


# ---------------------------------------------------------------------------
# Эвристика unit inference
# ---------------------------------------------------------------------------

def test_metric_card_unit_inference_rubles():
    """Колонка «Сумма, руб» → unit='₽'."""
    result = _query_result([_named_col("Сумма, руб", "Number")], [[42000.0]])
    card = _dispatch_query_card({}, result)
    assert card["payload"]["unit"] == "₽"


def test_metric_card_unit_inference_shtuk():
    """Колонка «Количество шт» → unit='шт.'."""
    result = _query_result([_named_col("Количество шт", "Number")], [[15]])
    card = _dispatch_query_card({}, result)
    assert card["payload"]["unit"] == "шт."


def test_metric_card_unit_none_for_plain_column():
    """Колонка «Значение» → unit=None."""
    result = _query_result([_named_col("Значение", "Number")], [[7]])
    card = _dispatch_query_card({}, result)
    assert card["payload"]["unit"] is None


# ---------------------------------------------------------------------------
# Delta zero-division safe
# ---------------------------------------------------------------------------

def test_metric_card_delta_zero_division_safe():
    """first_value = 0 → percent_value не вычисляется, нет ZeroDivisionError."""
    rows = [["2026-01", 0], ["2026-02", 100], ["2026-03", 200]]
    result = _query_result(
        [_named_col("Период"), _named_col("Сумма", "Number")],
        rows,
    )
    card = _dispatch_query_card({}, result)
    assert card is not None
    assert card["type"] == "metric"
    # percent_value отсутствует если first=0
    assert "percent_value" not in card["payload"]["delta"]


# ---------------------------------------------------------------------------
# _build_references_card
# ---------------------------------------------------------------------------

def test_references_card_groups_by_usage_kind():
    """ReferencesCard группирует items по usage_kind."""
    result = {
        "references": [
            {
                "object_type": "Документ",
                "name": "ОПП",
                "full_path": "Документ.ОПП.Реквизит.ИНН",
                "usage_kind": "Реквизит",
            },
            {
                "object_type": "Справочник",
                "name": "Контрагенты",
                "full_path": "Справочник.Контрагенты.Форма",
                "usage_kind": "Шаблон",
            },
            {
                "object_type": "Документ",
                "name": "Заказ",
                "full_path": "Документ.Заказ.Реквизит.Контрагент",
                "usage_kind": "Реквизит",
            },
        ]
    }
    card = _build_references_card({}, result)
    assert card is not None
    assert card["type"] == "references"
    assert card["payload"]["total"] == 3
    # «Реквизит» содержит 2 items, «Шаблон» — 1
    kinds = {g["kind"]: len(g["items"]) for g in card["payload"]["groups"]}
    assert kinds["Реквизит"] == 2
    assert kinds["Шаблон"] == 1


def test_references_card_orders_groups_fixed():
    """Порядок групп: Реквизит < Подчинённый < Шаблон < Подписка < Право < Прочее."""
    result = {
        "references": [
            {"object_type": "X", "name": "A", "full_path": "X.A", "usage_kind": "Прочее"},
            {"object_type": "X", "name": "B", "full_path": "X.B", "usage_kind": "Реквизит"},
            {"object_type": "X", "name": "C", "full_path": "X.C", "usage_kind": "Подписка"},
        ]
    }
    card = _build_references_card({}, result)
    assert card is not None
    order = [g["kind"] for g in card["payload"]["groups"]]
    # «Реквизит» должен быть раньше «Подписка», «Прочее» — последним
    assert order.index("Реквизит") < order.index("Подписка")
    assert order.index("Подписка") < order.index("Прочее")


def test_references_card_unknown_kind_falls_into_прочее():
    """Неизвестный usage_kind → группа «Прочее»."""
    result = {
        "references": [
            {"object_type": "X", "name": "Y", "full_path": "X.Y", "usage_kind": "НеизвестноеЗначение"},
        ]
    }
    card = _build_references_card({}, result)
    assert card is not None
    assert card["payload"]["groups"][0]["kind"] == "Прочее"


def test_references_card_empty_returns_none():
    """Пустой список references → None."""
    card = _build_references_card({}, {"references": []})
    assert card is None


def test_references_card_fallback_list_of_strings():
    """Legacy: references = list[str] → ReferencesCard с Прочее."""
    result = {
        "references": [
            "Документ.ОПП.Реквизит.Контрагент",
            "Справочник.Контрагенты.Форма",
        ]
    }
    card = _build_references_card({}, result)
    assert card is not None
    assert card["type"] == "references"
    assert card["payload"]["total"] == 2
    assert card["payload"]["groups"][0]["kind"] == "Прочее"


# ---------------------------------------------------------------------------
# _build_code_card
# ---------------------------------------------------------------------------

def test_code_card_execute_code_with_bsl():
    """execute_code с BSL кодом → CodeCard, language=bsl, executable=True."""
    code = "Процедура Тест()\n  КонецПроцедуры"
    card = _build_code_card({"code": code}, {"content": []})
    assert card is not None
    assert card["type"] == "code"
    assert card["payload"]["language"] == "bsl"
    assert card["payload"]["executable"] is True
    assert card["payload"]["code"] == code


def test_code_card_get_bsl_syntax_help_returns_snippet():
    """get_bsl_syntax_help → CodeCard со snippet, executable=False."""
    snippet = "// Синтаксис:\n// ТекущаяДатаСеанса() -> Дата"
    result_data = {"snippet": snippet}
    import json as _json
    result = {"content": [{"type": "text", "text": _json.dumps(result_data)}]}
    card = _build_code_card({}, result)
    assert card is not None
    assert card["payload"]["language"] == "bsl"
    assert card["payload"]["executable"] is False
    assert card["payload"]["code"] == snippet


def test_code_card_language_detection_sql():
    """Код начинается с ВЫБРАТЬ → language=sql."""
    code = "ВЫБРАТЬ\n  Документ.Номер\nИЗ\n  Документ.ОПП"
    card = _build_code_card({"code": code}, {})
    assert card["payload"]["language"] == "sql"


def test_code_card_language_detection_bsl_by_keywords():
    """Код содержит Функция/КонецПроцедуры → language=bsl."""
    code = "Функция ПолучитьДанные(Ссылка)\n  Возврат Неопределено;\nКонецФункции"
    card = _build_code_card({"code": code}, {})
    assert card["payload"]["language"] == "bsl"


def test_code_card_language_detection_json():
    """JSON → language=json."""
    code = '{"key": "value", "items": [1, 2, 3]}'
    card = _build_code_card({"code": code}, {})
    assert card["payload"]["language"] == "json"


def test_code_card_empty_code_returns_none():
    """Пустой код → None."""
    card = _build_code_card({"code": ""}, {})
    assert card is None


# ---------------------------------------------------------------------------
# Smoke: все 6 tools имеют builders
# ---------------------------------------------------------------------------

def test_build_card_dispatch_all_6_tools_have_builders():
    """Все 6 инструментов имеют зарегистрированные builders."""
    from app.orchestrator.cards import _CARD_BUILDERS
    expected_tools = {
        "execute_query",
        "get_object_by_link",
        "get_event_log",
        "find_references_to_object",
        "execute_code",
        "get_bsl_syntax_help",
    }
    assert expected_tools.issubset(set(_CARD_BUILDERS.keys()))


def test_execute_code_via_build_card_returns_code_card():
    """execute_code через build_card_from_tool_result → CodeCard."""
    code = "Если Истина Тогда\n  Возврат;\nКонецЕсли;"
    card = build_card_from_tool_result("execute_code", {"code": code}, {})
    assert card is not None
    assert card["type"] == "code"


def test_get_bsl_syntax_help_via_build_card():
    """get_bsl_syntax_help через build_card_from_tool_result → CodeCard."""
    data = {"snippet": "ТекущаяДатаСеанса() -> Дата"}
    result = {"content": [{"type": "text", "text": json.dumps(data)}]}
    card = build_card_from_tool_result("get_bsl_syntax_help", {}, result)
    assert card is not None
    assert card["type"] == "code"
    assert card["payload"]["executable"] is False


def test_references_card_navigation_link_preserved():
    """navigation_link сохраняется в payload."""
    result = {
        "references": [
            {
                "object_type": "Документ",
                "name": "ОПП",
                "full_path": "Документ.ОПП.Реквизит.ИНН",
                "navigation_link": "e1cib/data/Документ.ОПП",
                "usage_kind": "Реквизит",
            }
        ]
    }
    card = _build_references_card({}, result)
    assert card["payload"]["groups"][0]["items"][0]["navigation_link"] == "e1cib/data/Документ.ОПП"
