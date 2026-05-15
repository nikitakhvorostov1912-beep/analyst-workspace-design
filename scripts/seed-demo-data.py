"""Скрипт для наполнения SQLite демо-данными.

Использование:
    python scripts/seed-demo-data.py [--db backend/data.db] [--clean]

--clean: Очищает sessions/messages/card_states перед вставкой.
         НЕ трогает mcp_connections и llm_settings.

Создаёт 6 сессий (5 основных + 1 с анонимизацией) с примерами всех 6 типов карточек.
Все данные — выдуманные (ООО Ромашка, ИНН 0000000000).

Примечание: эти данные — статичные mock'и. Для реального демо на живой 1С seed не нужен.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import aiosqlite

from app.storage.migrations import apply_migrations

# ---------------------------------------------------------------------------
# Демо-данные: 5 основных сессий + 1 с анонимизацией
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=timezone.utc)


def _dt(minutes_ago: int) -> str:
    return (_NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M:%S")


# Сессия 1: Обзор базы — TableCard (список документов)
_SESS1_ID = str(uuid4())
_SESS1_MSG1_ID = str(uuid4())
_SESS1_MSG2_ID = str(uuid4())
_SESS1_CARD1_ID = str(uuid4())

_TABLE_CARD_PAYLOAD = {
    "columns": [
        {"name": "Подсистема", "type": "String"},
        {"name": "Документ", "type": "String"},
        {"name": "Описание", "type": "String"},
    ],
    "rows": [
        ["Закупки", "ЗаказПоставщику", "Заказ товаров у поставщика"],
        ["Продажи", "РеализацияТоваровУслуг", "Реализация товаров и услуг"],
        ["Склад", "ПеремещениеТоваров", "Перемещение между складами"],
        ["Транзит", "ОПП", "Оформление поручения покупателя"],
        ["Финансы", "ПлатёжноеПоручение", "Платёжное поручение банк"],
    ],
    "total": 5,
    "meta": {"query": None, "duration_ms": 312},
    "card_id": _SESS1_CARD1_ID,
}

# Сессия 2: Журнал за час — LogCard
_SESS2_ID = str(uuid4())
_SESS2_MSG1_ID = str(uuid4())
_SESS2_MSG2_ID = str(uuid4())
_SESS2_CARD1_ID = str(uuid4())

_LOG_ENTRIES = [
    {"time": _dt(55), "level": "Error", "user": "Иванов", "event": "Проведение документа", "comment": "Недостаточно товаров на складе"},
    {"time": _dt(50), "level": "Warning", "user": "Петрова", "event": "Синхронизация данных", "comment": "Превышен лимит ожидания 30с"},
    {"time": _dt(45), "level": "Info", "user": "Системный", "event": "Запуск регламента", "comment": None},
    {"time": _dt(40), "level": "Error", "user": "Сидоров", "event": "Ошибка в модуле", "comment": "НДС не найден для контрагента"},
    {"time": _dt(35), "level": "Warning", "user": "Иванов", "event": "Запись объекта", "comment": "Реквизит ИНН не заполнен"},
    {"time": _dt(30), "level": "Info", "user": "Системный", "event": "Обмен с банком", "comment": "Загружено 3 выписки"},
    {"time": _dt(25), "level": "Error", "user": "Администратор", "event": "Ошибка HTTP", "comment": "Connection refused 6010"},
    {"time": _dt(20), "level": "Info", "user": "Петрова", "event": "Печать документа", "comment": None},
    {"time": _dt(15), "level": "Warning", "user": "Системный", "event": "Очистка кеша", "comment": "Кеш сессий устарел"},
    {"time": _dt(5), "level": "Info", "user": "Иванов", "event": "Вход в систему", "comment": None},
]
_LOG_CARD_PAYLOAD = {
    "entries": _LOG_ENTRIES,
    "next_cursor": "2026-05-15T09:00:00Z",
    "card_id": _SESS2_CARD1_ID,
}

# Сессия 3: Где используется Контрагент — ReferencesCard
_SESS3_ID = str(uuid4())
_SESS3_MSG1_ID = str(uuid4())
_SESS3_MSG2_ID = str(uuid4())
_SESS3_CARD1_ID = str(uuid4())

_REFERENCES_CARD_PAYLOAD = {
    "groups": [
        {
            "kind": "Реквизит",
            "items": [
                {
                    "object_type": "Документ",
                    "name": "ОПП",
                    "navigation_link": "e1cib/data/Документ.ОПП",
                    "full_path": "Документ.ОПП.Реквизит.Контрагент",
                },
                {
                    "object_type": "Документ",
                    "name": "РеализацияТоваровУслуг",
                    "navigation_link": None,
                    "full_path": "Документ.РеализацияТоваровУслуг.Реквизит.Контрагент",
                },
            ],
        },
        {
            "kind": "Подчинённый",
            "items": [
                {
                    "object_type": "Справочник",
                    "name": "ДоговорыКонтрагентов",
                    "navigation_link": None,
                    "full_path": "Справочник.ДоговорыКонтрагентов.Владелец",
                },
            ],
        },
        {
            "kind": "Шаблон",
            "items": [
                {
                    "object_type": "Документ",
                    "name": "СчётФактура",
                    "navigation_link": None,
                    "full_path": "Документ.СчётФактура.Шаблон.КонтрагентМакет",
                },
            ],
        },
        {
            "kind": "Право",
            "items": [
                {
                    "object_type": "Роль",
                    "name": "РольАналитик",
                    "navigation_link": None,
                    "full_path": "Роль.РольАналитик.Справочник.Контрагенты.Просмотр",
                },
            ],
        },
    ],
    "total": 5,
    "card_id": _SESS3_CARD1_ID,
}

# Сессия 4: Метрика прихода за месяц — MetricCard со sparkline
_SESS4_ID = str(uuid4())
_SESS4_MSG1_ID = str(uuid4())
_SESS4_MSG2_ID = str(uuid4())
_SESS4_CARD1_ID = str(uuid4())

_METRIC_CARD_PAYLOAD = {
    "value": 5_420_000.0,
    "label": "Сумма прихода",
    "unit": "₽",
    "sparkline": [
        {"label": f"2026-{m:02d}", "value": v}
        for m, v in [
            (1, 3_100_000), (2, 3_450_000), (3, 2_900_000), (4, 4_100_000),
            (5, 4_800_000), (6, 5_100_000), (7, 4_600_000), (8, 5_000_000),
            (9, 4_900_000), (10, 5_200_000), (11, 5_300_000), (12, 5_420_000),
        ]
    ],
    "delta": {"value": 2_320_000, "direction": "up", "percent": False, "percent_value": 74.8},
    "card_id": _SESS4_CARD1_ID,
}

# Сессия 5: BSL-код — CodeCard
_SESS5_ID = str(uuid4())
_SESS5_MSG1_ID = str(uuid4())
_SESS5_MSG2_ID = str(uuid4())
_SESS5_CARD1_ID = str(uuid4())

_BSL_CODE = """\
// Процедура проверки заполненности контрагента перед записью
Процедура ПередЗаписью(Отказ)
    Если НЕ ЗначениеЗаполнено(Контрагент) Тогда
        ОбщегоНазначения.СообщитьПользователю(
            НСтр("ru='Контрагент не заполнен'"),
            ЭтотОбъект,
            "Контрагент"
        );
        Отказ = Истина;
    КонецЕсли;
    // Проверка ИНН
    Если СтрДлина(СокрЛП(Контрагент.ИНН)) < 10 Тогда
        ОбщегоНазначения.СообщитьПользователю(
            НСтр("ru='ИНН должен содержать не менее 10 символов'"),
            ЭтотОбъект,
            "Контрагент.ИНН"
        );
        Отказ = Истина;
    КонецЕсли;
КонецПроцедуры
"""

_CODE_CARD_PAYLOAD = {
    "language": "bsl",
    "code": _BSL_CODE,
    "executable": False,
    "result": None,
    "card_id": _SESS5_CARD1_ID,
}

# Сессия 6: Анонимизация — TableCard с токенами [ORG-xxx] [INN-xxx]
_SESS6_ID = str(uuid4())
_SESS6_MSG1_ID = str(uuid4())
_SESS6_MSG2_ID = str(uuid4())
_SESS6_CARD1_ID = str(uuid4())

_ANON_TOKENS = {
    "[ORG-001]": "ООО Ромашка",
    "[INN-001]": "0000000001",
    "[ORG-002]": "АО Василёк",
    "[INN-002]": "0000000002",
}

_ANON_TABLE_CARD_PAYLOAD = {
    "columns": [
        {"name": "Контрагент", "type": "String"},
        {"name": "ИНН", "type": "String"},
        {"name": "Задолженность, ₽", "type": "Number"},
    ],
    "rows": [
        ["[ORG-001]", "[INN-001]", 145_000],
        ["[ORG-002]", "[INN-002]", 320_000],
    ],
    "total": 2,
    "meta": {"query": None, "duration_ms": 450},
    "card_id": _SESS6_CARD1_ID,
}

# ---------------------------------------------------------------------------
# Структура данных сессий
# ---------------------------------------------------------------------------

DEMO_SESSIONS = [
    {
        "id": _SESS1_ID,
        "title": "Обзор базы РТ",
        "channel_id": "rt",
        "created_at": _dt(60),
        "messages": [
            {
                "id": _SESS1_MSG1_ID,
                "role": "user",
                "content": "Обзор базы — перечисли подсистемы, основные документы",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS1_MSG2_ID,
                "role": "assistant",
                "content": "База содержит 5 ключевых подсистем. Основные документы — в таблице ниже.",
                "tool_calls": json.dumps([
                    {
                        "id": "call_001",
                        "name": "get_metadata",
                        "args": {"mode": "subsystems"},
                        "result": {"status": "ok"},
                        "duration_ms": 312,
                    }
                ]),
                "cards": json.dumps([{"type": "table", "payload": _TABLE_CARD_PAYLOAD}]),
                "duration_ms": 8200,
            },
        ],
        "card_states": [],
    },
    {
        "id": _SESS2_ID,
        "title": "Журнал за час",
        "channel_id": "rt",
        "created_at": _dt(55),
        "messages": [
            {
                "id": _SESS2_MSG1_ID,
                "role": "user",
                "content": "/journal Период=Час, Уровень=Error+Warning",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS2_MSG2_ID,
                "role": "assistant",
                "content": "Найдено 10 записей за последний час (3 Error, 3 Warning, 4 Info).",
                "tool_calls": json.dumps([
                    {
                        "id": "call_002",
                        "name": "get_event_log",
                        "args": {"period": "hour", "levels": ["Error", "Warning", "Info"]},
                        "result": {"entries_count": 10},
                        "duration_ms": 1450,
                    }
                ]),
                "cards": json.dumps([{"type": "log", "payload": _LOG_CARD_PAYLOAD}]),
                "duration_ms": 12300,
            },
        ],
        "card_states": [
            {
                "card_id": _SESS2_CARD1_ID,
                "session_id": _SESS2_ID,
                "message_id": _SESS2_MSG2_ID,
                "tool_name": "get_event_log",
                "original_args": json.dumps({"period": "hour", "levels": ["Error", "Warning", "Info"]}),
                "channel_id": "rt",
                "anon_tokens": None,
            }
        ],
    },
    {
        "id": _SESS3_ID,
        "title": "Где используется Контрагент",
        "channel_id": "uso",
        "created_at": _dt(50),
        "messages": [
            {
                "id": _SESS3_MSG1_ID,
                "role": "user",
                "content": "/find Контрагент",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS3_MSG2_ID,
                "role": "assistant",
                "content": "Справочник «Контрагенты» используется в 5 местах по 4 категориям.",
                "tool_calls": json.dumps([
                    {
                        "id": "call_003",
                        "name": "find_references_to_object",
                        "args": {"object_path": "Справочник.Контрагенты"},
                        "result": {"total": 5},
                        "duration_ms": 890,
                    }
                ]),
                "cards": json.dumps([{"type": "references", "payload": _REFERENCES_CARD_PAYLOAD}]),
                "duration_ms": 9800,
            },
        ],
        "card_states": [],
    },
    {
        "id": _SESS4_ID,
        "title": "Метрика прихода за месяц",
        "channel_id": "rt",
        "created_at": _dt(45),
        "messages": [
            {
                "id": _SESS4_MSG1_ID,
                "role": "user",
                "content": "Покажи метрику прихода денег за год помесячно",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS4_MSG2_ID,
                "role": "assistant",
                "content": "Приход за год составил 5 420 000 ₽ (+74.8% к началу года).",
                "tool_calls": json.dumps([
                    {
                        "id": "call_004",
                        "name": "execute_query",
                        "args": {"query": "ВЫБРАТЬ Месяц, Сумма ИЗ РегистрНакопления.Приход"},
                        "result": {"rows_count": 12},
                        "duration_ms": 2100,
                    }
                ]),
                "cards": json.dumps([{"type": "metric", "payload": _METRIC_CARD_PAYLOAD}]),
                "duration_ms": 15600,
            },
        ],
        "card_states": [],
    },
    {
        "id": _SESS5_ID,
        "title": "Процедура ПередЗаписью",
        "channel_id": "uso",
        "created_at": _dt(40),
        "messages": [
            {
                "id": _SESS5_MSG1_ID,
                "role": "user",
                "content": "Покажи процедуру ПередЗаписью в документе ОПП",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS5_MSG2_ID,
                "role": "assistant",
                "content": "Процедура ПередЗаписью документа ОПП выполняет проверку контрагента и ИНН.",
                "tool_calls": json.dumps([
                    {
                        "id": "call_005",
                        "name": "get_bsl_syntax_help",
                        "args": {"object": "Документ.ОПП", "method": "ПередЗаписью"},
                        "result": {"found": True},
                        "duration_ms": 560,
                    }
                ]),
                "cards": json.dumps([{"type": "code", "payload": _CODE_CARD_PAYLOAD}]),
                "duration_ms": 7300,
            },
        ],
        "card_states": [],
    },
    {
        "id": _SESS6_ID,
        "title": "Задолженность контрагентов (anon)",
        "channel_id": "rt",
        "created_at": _dt(30),
        "messages": [
            {
                "id": _SESS6_MSG1_ID,
                "role": "user",
                "content": "Найди контрагентов с задолженностью более 100к",
                "tool_calls": None,
                "cards": None,
                "duration_ms": None,
            },
            {
                "id": _SESS6_MSG2_ID,
                "role": "assistant",
                "content": "Найдено 2 контрагента с задолженностью более 100 000 ₽ (анонимизировано).",
                "tool_calls": json.dumps([
                    {
                        "id": "call_006",
                        "name": "execute_query",
                        "args": {
                            "query": "ВЫБРАТЬ Контрагент, ИНН, Задолженность ГДЕ Задолженность > 100000",
                            "anon_enabled": True,
                        },
                        "result": {"rows_count": 2, "anon_applied": True},
                        "duration_ms": 1800,
                    }
                ]),
                "cards": json.dumps([{"type": "table", "payload": _ANON_TABLE_CARD_PAYLOAD}]),
                "duration_ms": 11200,
            },
        ],
        "card_states": [
            {
                "card_id": _SESS6_CARD1_ID,
                "session_id": _SESS6_ID,
                "message_id": _SESS6_MSG2_ID,
                "tool_name": "execute_query",
                "original_args": json.dumps({"query": "ВЫБРАТЬ Контрагент...", "anon_enabled": True}),
                "channel_id": "rt",
                "anon_tokens": json.dumps(_ANON_TOKENS),
            }
        ],
    },
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------


async def seed(db_path: str, clean: bool) -> None:
    """Наполняет БД демо-сессиями."""
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)

        if clean:
            await db.execute("DELETE FROM messages")
            await db.execute("DELETE FROM card_states")
            await db.execute("DELETE FROM sessions")
            await db.commit()
            print("Очищены sessions/messages/card_states (mcp_connections и llm_settings сохранены).")

        for sess in DEMO_SESSIONS:
            # INSERT OR IGNORE — идемпотентность (повторный запуск без --clean не дублирует)
            await db.execute(
                "INSERT OR IGNORE INTO sessions (id, title, channel_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sess["id"], sess["title"], sess["channel_id"], sess["created_at"], sess["created_at"]),
            )
            for msg in sess["messages"]:
                await db.execute(
                    "INSERT OR IGNORE INTO messages "
                    "(id, session_id, role, content, tool_calls, cards, duration_ms, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        msg["id"],
                        sess["id"],
                        msg["role"],
                        msg["content"],
                        msg["tool_calls"],
                        msg["cards"],
                        msg["duration_ms"],
                        sess["created_at"],
                    ),
                )
            for cs in sess.get("card_states", []):
                await db.execute(
                    "INSERT OR IGNORE INTO card_states "
                    "(card_id, session_id, message_id, tool_name, original_args, channel_id, anon_tokens) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        cs["card_id"],
                        cs["session_id"],
                        cs["message_id"],
                        cs["tool_name"],
                        cs["original_args"],
                        cs["channel_id"],
                        cs["anon_tokens"],
                    ),
                )

        await db.commit()

    print(f"Seeded {len(DEMO_SESSIONS)} sessions into {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Наполнить SQLite демо-сессиями для 1С Аналитик preview."
    )
    parser.add_argument("--db", default="backend/data.db", help="Путь к SQLite файлу")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Очистить sessions/messages/card_states перед вставкой",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.db, args.clean))
