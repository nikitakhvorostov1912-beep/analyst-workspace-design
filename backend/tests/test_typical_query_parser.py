"""Тесты для backend/app/knowledge/typical/query_parser.py (M-K2.5.2).

Покрытие:
- extract_query_strings: single literal / concat через `+` / non-query
- parse_query: physical tables (ИЗ / разные JOIN)
- parse_query: виртуальные таблицы регистров (5 видов + 4 типа регистров)
- parse_query: параметры &X
- parse_query: ПОМЕСТИТЬ ВТ_X / УНИЧТОЖИТЬ
- parse_query: алиасы КАК Alias / AS Alias
- parse_query: дедупликация tables / virtual_tables
- parse_query: case-insensitive (ВЫБРАТЬ vs select)
- parse_query: BSL комменты `//` игнорируются
- extract_queries_from_method: интеграция через body_source
- iter_queries_from_methods: пакет
- Edge cases: пустой текст, чистый текст без запросов
"""

from __future__ import annotations

import pytest

from app.knowledge.typical.bsl_ast import parse_module
from app.knowledge.typical.query_models import (
    BSLQuery,
    TableReference,
    VirtualTableKind,
    VirtualTableReference,
    is_register_type_name,
)
from app.knowledge.typical.query_parser import (
    extract_queries_from_method,
    extract_query_strings,
    iter_queries_from_methods,
    parse_query,
)


# ── extract_query_strings ────────────────────────────────────────────


def test_extract_empty_source():
    assert extract_query_strings("") == []


def test_extract_single_query_literal():
    bsl = '''
Процедура Х()
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты";
КонецПроцедуры
'''
    queries = extract_query_strings(bsl)
    assert len(queries) == 1
    text, line = queries[0]
    assert "ВЫБРАТЬ" in text
    assert "Справочник.Контрагенты" in text
    assert line == 3


def test_extract_concatenated_query():
    """Многострочные запросы через `+` склеиваются."""
    bsl = '''
Процедура Х()
    Запрос.Текст =
        "ВЫБРАТЬ"
        + " Поле1"
        + " ИЗ Справочник.Контрагенты";
КонецПроцедуры
'''
    queries = extract_query_strings(bsl)
    assert len(queries) == 1
    text, _ = queries[0]
    assert "ВЫБРАТЬ" in text
    assert "Поле1" in text
    assert "Справочник.Контрагенты" in text


def test_extract_ignores_non_query_strings():
    bsl = '''
Процедура Х()
    Сообщение = "Это просто строка";
КонецПроцедуры
'''
    assert extract_query_strings(bsl) == []


def test_extract_two_separate_queries():
    bsl = '''
Процедура Х()
    Запрос1.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты";
    Сообщить("разделитель");
    Запрос2.Текст = "ВЫБРАТЬ * ИЗ Документ.Реализация";
КонецПроцедуры
'''
    queries = extract_query_strings(bsl)
    assert len(queries) == 2


def test_extract_escapes_double_quotes():
    """`""` внутри строки = одна кавычка в BSL."""
    bsl = '''Запрос.Текст = "ВЫБРАТЬ ""поле"" ИЗ Справочник.Х";'''
    queries = extract_query_strings(bsl)
    assert len(queries) == 1
    text, _ = queries[0]
    assert '"поле"' in text


# ── parse_query: physical tables ─────────────────────────────────────


def test_parse_query_simple_from():
    q = parse_query("ВЫБРАТЬ * ИЗ Справочник.Контрагенты")
    assert len(q.tables) == 1
    assert q.tables[0].name == "Справочник.Контрагенты"
    assert q.tables[0].is_temp_table is False


def test_parse_query_with_alias():
    q = parse_query("ВЫБРАТЬ * ИЗ Справочник.Контрагенты КАК К")
    assert q.tables[0].name == "Справочник.Контрагенты"
    assert q.tables[0].alias == "К"


@pytest.mark.parametrize(
    "join_keyword",
    [
        "ВНУТРЕННЕЕ СОЕДИНЕНИЕ",
        "ЛЕВОЕ СОЕДИНЕНИЕ",
        "ПРАВОЕ СОЕДИНЕНИЕ",
        "ПОЛНОЕ СОЕДИНЕНИЕ",
        "КРОСС СОЕДИНЕНИЕ",
    ],
)
def test_parse_query_join_types(join_keyword):
    q = parse_query(
        f"ВЫБРАТЬ * ИЗ Справочник.Контрагенты КАК К "
        f"{join_keyword} Документ.Реализация КАК Р ПО К.Ссылка = Р.Контрагент"
    )
    table_names = {t.name for t in q.tables}
    assert "Справочник.Контрагенты" in table_names
    assert "Документ.Реализация" in table_names


def test_parse_query_temp_table_in_from():
    q = parse_query("ВЫБРАТЬ * ИЗ ВТ_Товары КАК Т")
    assert any(t.is_temp_table for t in q.tables)
    assert "ВТ_Товары" in q.temp_tables_read


def test_parse_query_put_into_temp():
    q = parse_query(
        "ВЫБРАТЬ * ПОМЕСТИТЬ ВТ_МойБлок ИЗ Документ.Реализация.Товары"
    )
    assert "ВТ_МойБлок" in q.temp_tables_created
    assert "Документ.Реализация.Товары" in {t.name for t in q.tables}


def test_parse_query_destroy_temp():
    q = parse_query("УНИЧТОЖИТЬ ВТ_МойБлок")
    assert q.is_destroy_temp is True
    # is_select=False для УНИЧТОЖИТЬ
    assert q.is_select is False


# ── parse_query: virtual tables ──────────────────────────────────────


def test_parse_query_virtual_table_remains():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период, Склад = &Склад)"
    )
    assert len(q.virtual_tables) == 1
    vt = q.virtual_tables[0]
    assert vt.register_type == "РегистрНакопления"
    assert vt.register_name == "ТоварыНаСкладах"
    assert vt.virtual_kind == VirtualTableKind.REMAINS.value
    assert "&Период" in vt.parameters_raw
    assert "Склад" in vt.parameters_raw


@pytest.mark.parametrize(
    "register_type,vt_name,expected_kind",
    [
        ("РегистрНакопления", "Остатки", "Остатки"),
        ("РегистрНакопления", "Обороты", "Обороты"),
        ("РегистрНакопления", "ОстаткиИОбороты", "ОстаткиИОбороты"),
        ("РегистрСведений", "СрезПоследних", "СрезПоследних"),
        ("РегистрСведений", "СрезПервых", "СрезПервых"),
        ("РегистрБухгалтерии", "ОборотыДтКт", "ОборотыДтКт"),
        ("РегистрБухгалтерии", "ДвиженияССубконто", "ДвиженияССубконто"),
        ("РегистрРасчета", "ДанныеГрафика", "ДанныеГрафика"),
    ],
)
def test_virtual_table_kinds(register_type, vt_name, expected_kind):
    q = parse_query(
        f"ВЫБРАТЬ * ИЗ {register_type}.МойРегистр.{vt_name}()"
    )
    assert len(q.virtual_tables) == 1
    assert q.virtual_tables[0].virtual_kind == expected_kind


def test_virtual_table_alias():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки() КАК Остатки"
    )
    vt = q.virtual_tables[0]
    assert vt.alias == "Остатки"


def test_virtual_table_qualified_name():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки()"
    )
    vt = q.virtual_tables[0]
    assert vt.qualified_name == "РегистрНакопления.ТоварыНаСкладах"
    assert vt.full_call == "РегистрНакопления.ТоварыНаСкладах.Остатки"


# ── parse_query: parameters ──────────────────────────────────────────


def test_parse_query_parameters_extracted():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ Справочник.Контрагенты "
        "ГДЕ Ссылка = &Контрагент И ИНН = &ИНН"
    )
    assert "Контрагент" in q.parameters
    assert "ИНН" in q.parameters


def test_parse_query_parameters_deduplicated():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ Х ГДЕ А = &Параметр ИЛИ Б = &Параметр"
    )
    assert q.parameters == ("Параметр",)


def test_parse_query_no_parameters():
    q = parse_query("ВЫБРАТЬ * ИЗ Справочник.Контрагенты")
    assert q.parameters == ()


# ── parse_query: edge cases ──────────────────────────────────────────


def test_parse_empty_query():
    q = parse_query("")
    assert q.text == ""
    assert q.tables == ()


def test_parse_query_case_insensitive_keywords():
    """SELECT / select / ВЫБРАТЬ должны равно опознаваться."""
    q_lower = parse_query("select * from Справочник.Контрагенты")
    q_upper = parse_query("SELECT * FROM Справочник.Контрагенты")
    assert q_lower.is_select is True
    assert q_upper.is_select is True
    assert len(q_lower.tables) == 1
    assert len(q_upper.tables) == 1


def test_parse_query_strips_bsl_comments():
    """`//` комменты в запросе игнорируются."""
    q = parse_query(
        """ВЫБРАТЬ Поле // комментарий с ИЗ Documents.Fake
        ИЗ Справочник.Контрагенты"""
    )
    assert len(q.tables) == 1
    assert q.tables[0].name == "Справочник.Контрагенты"


def test_parse_query_deduplicates_tables():
    """Дубликаты таблиц в JOIN не должны давать удвоение."""
    q = parse_query(
        "ВЫБРАТЬ * ИЗ Документ.Реализация КАК Р "
        "ЛЕВОЕ СОЕДИНЕНИЕ Документ.Реализация КАК Р2 "
        "ПО Р.Контрагент = Р2.Контрагент"
    )
    names = [t.name for t in q.tables]
    assert names.count("Документ.Реализация") == 1


def test_parse_query_deduplicates_virtual_tables():
    """Виртуальная таблица упомянутая дважды → один entry."""
    q = parse_query(
        "ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период1) "
        "ОБЪЕДИНИТЬ ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период2)"
    )
    assert len(q.virtual_tables) == 1


def test_all_table_names_combines_physical_and_virtual():
    q = parse_query(
        "ВЫБРАТЬ * ИЗ Справочник.Контрагенты "
        "ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ВзаиморасчетыСКонтрагентами.Остатки() КАК О "
        "ПО Истина"
    )
    names = q.all_table_names
    assert "Справочник.Контрагенты" in names
    assert "РегистрНакопления.ВзаиморасчетыСКонтрагентами" in names


def test_temp_tables_read_excludes_those_created():
    """ВТ_X созданная и использованная в одном запросе НЕ попадает в temp_tables_read."""
    q = parse_query(
        "ВЫБРАТЬ * ПОМЕСТИТЬ ВТ_МойБлок ИЗ Справочник.Контрагенты; "
        "ВЫБРАТЬ * ИЗ ВТ_МойБлок"
    )
    assert "ВТ_МойБлок" in q.temp_tables_created
    assert "ВТ_МойБлок" not in q.temp_tables_read


# ── extract_queries_from_method (integration) ────────────────────────


def test_extract_queries_from_method_simple():
    method_body = '''
Функция ПолучитьКонтрагентов()
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты";
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции
'''
    queries = extract_queries_from_method(method_body, source_method="ПолучитьКонтрагентов")
    assert len(queries) == 1
    q = queries[0]
    assert q.source_method == "ПолучитьКонтрагентов"
    assert len(q.tables) == 1


def test_extract_queries_from_method_with_offset():
    method_body = '"ВЫБРАТЬ * ИЗ Справочник.Х"'
    queries = extract_queries_from_method(
        method_body,
        source_method="Метод",
        method_line_offset=100,
    )
    assert queries[0].source_line == 100 + 1  # line 1 в body + offset 100


def test_extract_queries_from_method_empty_body():
    assert extract_queries_from_method("") == []


def test_iter_queries_from_methods_via_bsl_module():
    """End-to-end: BSL AST → методы → запросы."""
    bsl = '''
Функция ПолучитьОстатки(Период) Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(&Период)";
    Запрос.УстановитьПараметр("Период", Период);
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции

Функция ПолучитьКонтрагентов() Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты";
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции
'''
    mod = parse_module(bsl)
    queries = list(iter_queries_from_methods(mod.methods))
    assert len(queries) == 2
    methods_in_queries = {q.source_method for q in queries}
    assert methods_in_queries == {"ПолучитьОстатки", "ПолучитьКонтрагентов"}


def test_iter_queries_skips_methods_without_body():
    """Метод без body_source (не должно случаться в реальности) — без падения."""

    class FakeMethod:
        def __init__(self, body):
            self.body_source = body
            self.name = "Fake"
            self.line_start = 1

    methods = [FakeMethod(""), FakeMethod('"ВЫБРАТЬ ИЗ Х"')]
    queries = list(iter_queries_from_methods(methods))
    assert len(queries) == 1


# ── to_dict / register helpers ───────────────────────────────────────


def test_table_reference_to_dict():
    t = TableReference(name="Справочник.Контрагенты", alias="К", is_temp_table=False)
    d = t.to_dict()
    assert d == {
        "name": "Справочник.Контрагенты",
        "alias": "К",
        "is_temp_table": False,
    }


def test_virtual_table_to_dict():
    vt = VirtualTableReference(
        register_type="РегистрНакопления",
        register_name="ТоварыНаСкладах",
        virtual_kind="Остатки",
        parameters_raw="&Период",
    )
    d = vt.to_dict()
    assert d["qualified_name"] == "РегистрНакопления.ТоварыНаСкладах"
    assert d["full_call"] == "РегистрНакопления.ТоварыНаСкладах.Остатки"
    assert d["parameters_raw"] == "&Период"


def test_bsl_query_to_dict_shape():
    q = parse_query("ВЫБРАТЬ * ИЗ Справочник.Х")
    d = q.to_dict()
    expected = {
        "text", "tables", "virtual_tables", "parameters",
        "temp_tables_created", "temp_tables_read",
        "is_select", "is_destroy_temp",
        "source_method", "source_line", "all_table_names",
    }
    assert expected <= set(d.keys())


def test_is_register_type_name():
    assert is_register_type_name("РегистрНакопления") is True
    assert is_register_type_name("РегистрСведений") is True
    assert is_register_type_name("AccumulationRegister") is True
    assert is_register_type_name("Документ") is False
    assert is_register_type_name("") is False
