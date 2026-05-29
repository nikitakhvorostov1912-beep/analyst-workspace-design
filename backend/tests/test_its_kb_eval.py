"""Тесты ИТС-KB eval (D1 анти-галлюцинация) на golden dataset.

Сидит bsp_chunks РЕАЛЬНЫМИ методами БСП (как в исходниках ssl_3_2), прогоняет
golden.jsonl через phantom-детектор и проверяет идеальную точность: все 9
фантомов (6 phantom + 3 mixed) пойманы, ни один реальный метод не флагнут.
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.its_kb_eval import (
    evaluate_phantom_detection,
    load_golden,
)
from app.storage.migrations import apply_migrations

# Реальные методы БСП 3.2 (module, method) — верифицированы в ssl_3_2/src.
# Покрывают все модули и реальные методы, упомянутые в golden (valid + mixed).
_REAL_METHODS = [
    ("ОбщегоНазначения", "ЗначениеРеквизитаОбъекта"),
    ("ОбщегоНазначения", "ЗначенияРеквизитовОбъекта"),
    ("ОбщегоНазначения", "ЗначенияРеквизитовОбъектов"),
    ("ОбщегоНазначения", "ЗначениеРеквизитаОбъектов"),
    ("ОбщегоНазначения", "ПодсистемаСуществует"),
    ("ОбщегоНазначения", "ОбщийМодуль"),
    ("ОбщегоНазначения", "ЗаписатьДанныеВБезопасноеХранилище"),
    ("ОбщегоНазначения", "УдалитьДанныеИзБезопасногоХранилища"),
    ("ОбщегоНазначения", "ЕстьСсылкиНаОбъект"),
    ("ОбщегоНазначенияКлиентСервер", "УточнениеИсключения"),
    ("ОбщегоНазначенияКлиентСервер", "ДополнитьМассив"),
    ("ОбщегоНазначенияКлиентСервер", "СравнитьВерсии"),
    ("ДлительныеОперации", "ВыполнитьВФоне"),
    ("ДлительныеОперации", "ПараметрыВыполненияВФоне"),
    ("ДлительныеОперации", "СообщитьПрогресс"),
    ("ДлительныеОперации", "ЗаданиеВыполнено"),
    ("Пользователи", "АвторизованныйПользователь"),
    ("Пользователи", "ТекущийПользователь"),
    ("Пользователи", "СвойстваПользователяИБ"),
    ("ПользователиКлиентСервер", "АвторизованныйПользователь"),
    ("РаботаСФайлами", "ДвоичныеДанныеФайла"),
    ("РаботаСФайлами", "НоваяСсылкаНаФайл"),
    ("РаботаСФайламиКлиент", "ОткрытьФайл"),
]


async def _seed_real_bsp(conn: aiosqlite.Connection) -> None:
    for i, (mod, meth) in enumerate(_REAL_METHODS):
        object_path = f"bsp:3.2:{mod}.{meth}"
        await conn.execute(
            "INSERT INTO bsp_chunks(object_path,module_name,method_name,method_kind,signature,"
            "doc_comment,content,version,source_path,char_count,chunk_hash) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (object_path, mod, meth, "Функция", f"Функция {meth}() Экспорт",
             "doc", "content", "3.2", "x", 10, f"h{i}"),
        )
    await conn.commit()


def test_golden_loads_20_cases():
    golden = load_golden()
    assert len(golden) == 20
    # все записи имеют обязательные поля
    for entry in golden:
        assert "id" in entry and "answer" in entry
        assert isinstance(entry.get("expected_phantom", []), list)


@pytest.mark.asyncio
async def test_phantom_eval_perfect_on_golden():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed_real_bsp(conn)

        golden = load_golden()
        result = await evaluate_phantom_detection(conn, golden)

        assert result.failures == [], f"расхождения: {result.failures}"
        assert result.fp == 0, "реальный метод не должен флагаться как phantom"
        assert result.fn == 0, "ни один фантом не должен быть пропущен"
        assert result.tp == 9, "6 phantom + 3 mixed = 9 ожидаемых фантомов"
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_eval_without_corpus_no_false_positives():
    """Пустой корпус БСП → детектор не флагает ничего (precision не падает)."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)  # bsp_chunks пуст
        golden = load_golden()
        result = await evaluate_phantom_detection(conn, golden)
        # без корпуса модули неизвестны → ничего не проверяется/флагается
        assert result.fp == 0
        assert result.tp == 0
    finally:
        await conn.close()
