"""Тесты для backend/app/knowledge/typical/bsl_ast.py (M-K2.5.1).

Покрытие:
- parse_module: empty / function / procedure / multiple
- Параметры: имя / default / `Знач` / комбинации
- Регионы: top-level / nested / методы внутри
- Doc-комментарии: накопление / привязка к методу / очистка
- Compile directives: &НаСервере / &НаКлиенте / &НаСервереБезКонтекста
- has_preprocessor_branches: True для #Если
- Customization marker: `// Доработка START` извлекается
- Graceful degradation: syntax error → has_errors но методы есть
- parse_file: чтение с диска, UTF-8 / cp1251 fallback
- Properties: signature / exported_methods / methods_by_name
- Кириллица: имена / строки / комментарии
"""

from __future__ import annotations

import pytest

from app.knowledge.typical.bsl_ast import (
    parse_file,
    parse_module,
    parse_string,
)
from app.knowledge.typical.bsl_models import (
    BSLMethod,
    BSLMethodKind,
    BSLModule,
    BSLParameter,
    BSLRegion,
)


# ── Empty / smoke ─────────────────────────────────────────────────────


def test_parse_empty_module():
    mod = parse_module("")
    assert isinstance(mod, BSLModule)
    assert mod.methods == ()
    assert mod.regions == ()
    assert mod.has_errors is False
    assert mod.module_path is None


def test_parse_whitespace_only():
    mod = parse_module("\n\n\n   \n")
    assert mod.methods == ()
    assert mod.has_errors is False


def test_parse_only_comment():
    mod = parse_module("// Это комментарий модуля\n// Без методов")
    assert mod.methods == ()
    assert mod.has_errors is False


# ── Один метод ────────────────────────────────────────────────────────


def test_parse_simple_function():
    source = """
Функция Сумма(А, Б)
    Возврат А + Б;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert len(mod.methods) == 1
    m = mod.methods[0]
    assert m.name == "Сумма"
    assert m.kind == BSLMethodKind.FUNCTION.value
    assert m.is_exported is False
    assert m.doc_comment is None
    assert len(m.parameters) == 2
    assert m.parameters[0].name == "А"
    assert m.parameters[0].by_value is False
    assert m.parameters[0].default is None
    assert m.parameters[1].name == "Б"


def test_parse_simple_procedure():
    source = """
Процедура Действие()
    ВыполнитьЧтоТо();
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    assert len(mod.methods) == 1
    m = mod.methods[0]
    assert m.name == "Действие"
    assert m.kind == BSLMethodKind.PROCEDURE.value
    assert m.is_exported is False
    assert m.parameters == ()


def test_parse_exported_function():
    source = """
Функция ПолучитьЗначение() Экспорт
    Возврат 42;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].is_exported is True


# ── Параметры ────────────────────────────────────────────────────────


def test_parse_parameter_with_default():
    source = """
Функция Тест(Параметр = Неопределено)
    Возврат Параметр;
КонецФункции
""".strip()
    mod = parse_module(source)
    p = mod.methods[0].parameters[0]
    assert p.name == "Параметр"
    assert p.default is not None
    assert "Неопределено" in p.default


def test_parse_parameter_by_value():
    source = """
Процедура Тест(Знач Параметр)
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    p = mod.methods[0].parameters[0]
    assert p.by_value is True
    assert p.name == "Параметр"


def test_parse_parameter_by_value_with_default():
    source = """
Процедура Тест(Знач Параметр = 0)
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    p = mod.methods[0].parameters[0]
    assert p.by_value is True
    assert p.name == "Параметр"
    assert p.default is not None and "0" in p.default


def test_parse_multiple_parameters_mixed():
    source = """
Функция Сложный(Знач А, Б, В = Истина, Знач Г = "значение")
    Возврат А;
КонецФункции
""".strip()
    mod = parse_module(source)
    params = mod.methods[0].parameters
    assert len(params) == 4
    assert params[0].name == "А" and params[0].by_value is True and params[0].default is None
    assert params[1].name == "Б" and params[1].by_value is False
    assert params[2].name == "В" and params[2].default is not None and "Истина" in params[2].default
    assert params[3].name == "Г" and params[3].by_value is True and "значение" in params[3].default


# ── Несколько методов ────────────────────────────────────────────────


def test_parse_multiple_methods():
    source = """
Процедура Первая()
КонецПроцедуры

Функция Вторая() Экспорт
    Возврат 1;
КонецФункции

Процедура Третья(Параметр)
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    assert len(mod.methods) == 3
    assert [m.name for m in mod.methods] == ["Первая", "Вторая", "Третья"]
    assert mod.methods[0].kind == BSLMethodKind.PROCEDURE.value
    assert mod.methods[1].kind == BSLMethodKind.FUNCTION.value
    assert mod.methods[1].is_exported is True


def test_exported_methods_property():
    source = """
Функция Открытая() Экспорт
    Возврат 1;
КонецФункции

Функция Внутренняя()
    Возврат 2;
КонецФункции

Процедура ОткрытаяПроцедура() Экспорт
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    exported = mod.exported_methods
    assert len(exported) == 2
    assert [m.name for m in exported] == ["Открытая", "ОткрытаяПроцедура"]


def test_methods_by_name_mapping():
    source = """
Функция А()
    Возврат 1;
КонецФункции

Функция Б()
    Возврат 2;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert set(mod.methods_by_name.keys()) == {"А", "Б"}
    assert mod.methods_by_name["А"].name == "А"


# ── Регионы ──────────────────────────────────────────────────────────


def test_parse_method_inside_region():
    source = """
#Область ПрограммныйИнтерфейс

Функция ПубличнаяАПИ() Экспорт
    Возврат "ok";
КонецФункции

#КонецОбласти
""".strip()
    mod = parse_module(source)
    assert len(mod.regions) == 1
    assert mod.regions[0].name == "ПрограммныйИнтерфейс"
    assert mod.regions[0].parent is None
    assert mod.methods[0].region == "ПрограммныйИнтерфейс"


def test_parse_nested_regions():
    source = """
#Область Внешняя

#Область Внутренняя

Функция Метод() Экспорт
КонецФункции

#КонецОбласти

#КонецОбласти
""".strip()
    mod = parse_module(source)
    assert len(mod.regions) == 2
    inner = next(r for r in mod.regions if r.name == "Внутренняя")
    outer = next(r for r in mod.regions if r.name == "Внешняя")
    assert inner.parent == "Внешняя"
    assert outer.parent is None
    # Метод связан с ближайшим регионом
    assert mod.methods[0].region == "Внутренняя"


def test_method_outside_region_has_no_region():
    source = """
Функция БезРегиона()
    Возврат 1;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].region is None


def test_region_lines_recorded():
    source = """
#Область ПрограммныйИнтерфейс

Функция X() Экспорт
КонецФункции

#КонецОбласти
""".lstrip()
    mod = parse_module(source)
    assert mod.regions[0].line_start == 1
    assert mod.regions[0].line_end >= 5


# ── Doc-комментарии ──────────────────────────────────────────────────


def test_parse_doc_comment_attached_to_method():
    source = """
// Возвращает сумму двух чисел.
//
// Параметры:
//  А - Число
//  Б - Число
//
// Возвращаемое значение:
//  Число
//
Функция Сумма(А, Б) Экспорт
    Возврат А + Б;
КонецФункции
""".strip()
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.doc_comment is not None
    assert "Возвращает сумму" in m.doc_comment
    assert "Параметры" in m.doc_comment
    assert "Возвращаемое значение" in m.doc_comment


def test_doc_comment_not_leaking_to_next_method():
    source = """
// Документация первого метода.
Функция Первая()
    Возврат 1;
КонецФункции

Функция ВтораяБезДоки()
    Возврат 2;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].doc_comment is not None
    assert "первого метода" in mod.methods[0].doc_comment
    assert mod.methods[1].doc_comment is None


# ── Customization marker (Доработка) ─────────────────────────────────


def test_customization_marker_extracted_from_doc():
    source = """
// Доработка START Тикет-12345 Иванов 2026-04-01
// Добавлен новый параметр для отчёта по поставщикам.
Функция Доработанная(Параметр) Экспорт
    Возврат Параметр;
КонецФункции
""".strip()
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.customization_marker is not None
    assert "Тикет-12345" in m.customization_marker


def test_customization_marker_without_keyword_returns_none():
    source = """
// Обычный doc-комментарий без маркеров доработки.
Функция Метод()
    Возврат 1;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].customization_marker is None


# ── Compile directives ───────────────────────────────────────────────


def test_compile_directive_na_servere():
    source = """
&НаСервере
Процедура ВыполнитьНаСервере()
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.compile_directive is not None
    assert "НаСервере" in m.compile_directive


def test_compile_directive_na_servere_bez_konteksta():
    source = """
&НаСервереБезКонтекста
Функция Расчёт(Сумма, Количество)
    Возврат Сумма * Количество;
КонецФункции
""".strip()
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.compile_directive is not None
    assert "БезКонтекста" in m.compile_directive


def test_compile_directive_na_kliente():
    source = """
&НаКлиенте
Процедура ПриОткрытии(Отказ)
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].compile_directive is not None
    assert "НаКлиенте" in mod.methods[0].compile_directive


def test_compile_directive_not_leaking_to_next_method():
    source = """
&НаСервере
Процедура НаСервере()
КонецПроцедуры

Процедура БезДирективы()
КонецПроцедуры
""".strip()
    mod = parse_module(source)
    assert mod.methods[0].compile_directive is not None
    assert "НаСервере" in mod.methods[0].compile_directive
    assert mod.methods[1].compile_directive is None


# ── Preprocessor #Если ──────────────────────────────────────────────


def test_has_preprocessor_branches_detected():
    source = """
#Если Сервер Тогда
Функция СерверныйМетод() Экспорт
    Возврат "сервер";
КонецФункции
#КонецЕсли
""".strip()
    mod = parse_module(source)
    assert mod.has_preprocessor_branches is True


def test_no_preprocessor_branches_without_if():
    source = """
Функция Простой() Экспорт
    Возврат 1;
КонецФункции
""".strip()
    mod = parse_module(source)
    assert mod.has_preprocessor_branches is False


# ── Source preservation ──────────────────────────────────────────────


def test_body_source_preserved():
    source = """
Функция Сложная(Параметр)
    Если Параметр > 0 Тогда
        Возврат Параметр * 2;
    КонецЕсли;
    Возврат 0;
КонецФункции
""".strip()
    mod = parse_module(source)
    body = mod.methods[0].body_source
    assert "Функция Сложная(Параметр)" in body
    assert "Возврат Параметр * 2" in body
    assert "КонецФункции" in body


def test_line_numbers_correct():
    source = "Функция А()\n    Возврат 1;\nКонецФункции\n"
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.line_start == 1
    assert m.line_end == 3


def test_total_lines_counted():
    source = "// строка 1\n// строка 2\n// строка 3\n"
    mod = parse_module(source)
    assert mod.total_lines >= 3


# ── Properties / dict ────────────────────────────────────────────────


def test_signature_property_reproduces_source():
    source = """
Функция Тест(Знач А, Б = 0) Экспорт
    Возврат А + Б;
КонецФункции
""".strip()
    mod = parse_module(source)
    sig = mod.methods[0].signature
    assert sig.startswith("Функция Тест(")
    assert "Знач А" in sig
    assert "Б = 0" in sig
    assert sig.endswith("Экспорт")


def test_method_to_dict_keys():
    source = "Функция X() Экспорт\nКонецФункции"
    mod = parse_module(source)
    d = mod.methods[0].to_dict()
    expected_keys = {
        "name", "kind", "parameters", "is_exported", "doc_comment",
        "compile_directive", "region", "line_start", "line_end",
        "body_source", "customization_marker", "signature",
    }
    assert expected_keys <= set(d.keys())


def test_module_to_dict_keys():
    mod = parse_module("Функция X()\nКонецФункции")
    d = mod.to_dict()
    expected = {
        "module_path", "methods", "regions", "has_errors",
        "parse_errors", "has_preprocessor_branches", "total_lines",
    }
    assert expected <= set(d.keys())


# ── Convenience wrappers ─────────────────────────────────────────────


def test_parse_string_wrapper():
    mod = parse_string("Функция X()\nКонецФункции")
    assert isinstance(mod, BSLModule)
    assert len(mod.methods) == 1
    assert mod.module_path is None


def test_parse_file_utf8(tmp_path):
    file = tmp_path / "Module.bsl"
    file.write_text(
        "Функция ИзФайла() Экспорт\n    Возврат 42;\nКонецФункции\n",
        encoding="utf-8",
    )
    mod = parse_file(file)
    assert len(mod.methods) == 1
    assert mod.methods[0].name == "ИзФайла"
    assert mod.module_path == str(file)


def test_parse_file_cp1251_fallback(tmp_path):
    """1С исторически использовала cp1251 для .bsl файлов."""
    file = tmp_path / "Module.bsl"
    file.write_bytes("Функция Кир() Экспорт\nКонецФункции\n".encode("cp1251"))
    mod = parse_file(file)
    assert mod.methods[0].name == "Кир"


# ── Graceful degradation ─────────────────────────────────────────────


def test_invalid_syntax_does_not_crash():
    """Tree-sitter графdegrad'ит на ошибках — методы извлекаются."""
    source = """
Функция ХорошоПарсится()
    Возврат 1;
КонецФункции

Это не BSL и не парсится корректно $$ @@

Функция ИВтораяТоже()
    Возврат 2;
КонецФункции
""".strip()
    mod = parse_module(source)
    # has_errors может быть True, но методы извлекаются
    assert len(mod.methods) >= 1
    names = {m.name for m in mod.methods}
    assert "ХорошоПарсится" in names


# ── Кириллица end-to-end ─────────────────────────────────────────────


def test_full_cyrillic_pipeline():
    """Кириллица в имени / параметре / строке / комментарии — UTF-8."""
    source = """
// Метод проверки контрагента по ИНН.
&НаСервереБезКонтекста
Функция ПроверитьКонтрагентаПоИНН(ИНН, ВключаяИсключения = Ложь) Экспорт
    Если СтрДлина(ИНН) = 0 Тогда
        Возврат "ИНН пустой";
    КонецЕсли;
    Возврат "ok";
КонецФункции
""".strip()
    mod = parse_module(source)
    m = mod.methods[0]
    assert m.name == "ПроверитьКонтрагентаПоИНН"
    assert m.is_exported is True
    assert m.compile_directive is not None and "БезКонтекста" in m.compile_directive
    assert m.parameters[0].name == "ИНН"
    assert m.parameters[1].name == "ВключаяИсключения"
    assert m.parameters[1].default is not None and "Ложь" in m.parameters[1].default
    assert m.doc_comment is not None and "контрагента" in m.doc_comment


def test_byte_source_input_supported():
    """parse_module принимает bytes напрямую (без decode)."""
    source_bytes = "Функция Тест()\nКонецФункции\n".encode("utf-8")
    mod = parse_module(source_bytes)
    assert mod.methods[0].name == "Тест"
