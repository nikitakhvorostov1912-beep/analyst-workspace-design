"""BSL Query Language модели — regex-извлечение table refs.

`BSLQuery` — один запрос с физическими таблицами, виртуальными
таблицами, параметрами и временными таблицами. Используется Phase 4
graph builder для построения READS_FROM / WRITES_TO edges.

## Зачем не AST

Полноценный AST для BSL Query Language — отдельный grammar
(~3-4 недели работы). Для нужд графа достаточно знать **какие таблицы
читаются**, **какие пишутся через ПОМЕСТИТЬ**, **какие виртуальные
таблицы используются** и **какие параметры запроса**. Это закрывает 95%
use cases для Phase 4 (граф движений) и Phase 5 (карточки).

Если в будущем потребуется (например для query optimizer'а из M-K3),
можно перейти на полноценный AST через отдельный grammar — тогда эти
модели расширятся, API останется обратно-совместимым.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VirtualTableKind(str, Enum):
    """Виртуальные таблицы регистров.

    Конкретные имена ВТ варьируются по типу регистра:
    - РегистрНакопления: Остатки / Обороты / ОстаткиИОбороты
    - РегистрСведений: СрезПоследних / СрезПервых
    - РегистрБухгалтерии: Остатки / Обороты / ОборотыДтКт / ДвиженияССубконто
    - РегистрРасчета: ДанныеГрафика / ФактическийПериодДействия / БазаЗначений
    """

    REMAINS = "Остатки"
    TURNOVERS = "Обороты"
    REMAINS_AND_TURNOVERS = "ОстаткиИОбороты"
    SLICE_LAST = "СрезПоследних"
    SLICE_FIRST = "СрезПервых"
    TURNOVERS_DT_KT = "ОборотыДтКт"
    MOVEMENTS_WITH_SUBCONTO = "ДвиженияССубконто"
    SCHEDULE_DATA = "ДанныеГрафика"
    ACTUAL_ACTION_PERIOD = "ФактическийПериодДействия"
    BASE_VALUES = "БазаЗначений"
    UNKNOWN = "Unknown"


# Типы регистров с виртуальными таблицами
_REGISTER_TYPES = frozenset(
    [
        "РегистрНакопления",
        "РегистрСведений",
        "РегистрБухгалтерии",
        "РегистрРасчета",
        "AccumulationRegister",  # английские варианты на случай EDT
        "InformationRegister",
        "AccountingRegister",
        "CalculationRegister",
    ]
)


def _normalize_virtual_kind(raw: str) -> str:
    """Парсит сырое имя ВТ в VirtualTableKind value (или UNKNOWN)."""
    try:
        return VirtualTableKind(raw).value
    except ValueError:
        return VirtualTableKind.UNKNOWN.value


@dataclass(frozen=True, slots=True)
class TableReference:
    """Ссылка на таблицу в запросе.

    `name` — полное имя как в исходнике: `Документ.РеализацияТоваровУслуг`,
    `Справочник.Контрагенты`, `Документ.РеализацияТоваровУслуг.Товары`,
    `РегистрНакопления.ТоварыНаСкладах`, `ВТ_МойБлок`.

    `is_temp_table` — True для имён начинающихся на `ВТ_` (соглашение
    проекта из rules/1c/1c-architecture-standards.md).
    """

    name: str
    alias: str | None = None
    is_temp_table: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "alias": self.alias,
            "is_temp_table": self.is_temp_table,
        }


@dataclass(frozen=True, slots=True)
class VirtualTableReference:
    """Виртуальная таблица регистра.

    Пример: `РегистрНакопления.ТоварыНаСкладах.Остатки(&Период, Условие)`
    → register_type="РегистрНакопления", register_name="ТоварыНаСкладах",
       virtual_kind="Остатки", parameters_raw="&Период, Условие".

    `parameters_raw` — сырая строка из скобок виртуальной таблицы.
    Разбор содержимого (Период, Условие) — Phase 4 graph builder
    если потребуется.
    """

    register_type: str
    register_name: str
    virtual_kind: str  # VirtualTableKind.value
    parameters_raw: str = ""
    alias: str | None = None

    @property
    def qualified_name(self) -> str:
        """`РегистрНакопления.ТоварыНаСкладах`."""
        return f"{self.register_type}.{self.register_name}"

    @property
    def full_call(self) -> str:
        """`РегистрНакопления.ТоварыНаСкладах.Остатки`."""
        return f"{self.register_type}.{self.register_name}.{self.virtual_kind}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "register_type": self.register_type,
            "register_name": self.register_name,
            "virtual_kind": self.virtual_kind,
            "parameters_raw": self.parameters_raw,
            "alias": self.alias,
            "qualified_name": self.qualified_name,
            "full_call": self.full_call,
        }


@dataclass(frozen=True, slots=True)
class BSLQuery:
    """Один разобранный запрос BSL.

    Поля:
    - `text` — нормализованный текст запроса (склеенные `"..."` + `"..."`).
    - `tables` — физические таблицы из `ИЗ` / `СОЕДИНЕНИЕ`.
    - `virtual_tables` — виртуальные таблицы регистров.
    - `parameters` — `&Параметр` (только имена без `&`).
    - `temp_tables_created` — имена ВТ из `ПОМЕСТИТЬ ВТ_X`.
    - `temp_tables_read` — имена ВТ упомянутые в `ИЗ` (без указания типа).
    - `is_select` / `is_destroy_temp` — тип запроса (SELECT vs УНИЧТОЖИТЬ).
    - `source_method` — имя метода в котором найден запрос (для трассировки).
    - `source_line` — строка в модуле где встретился литерал.
    """

    text: str
    tables: tuple[TableReference, ...] = field(default_factory=tuple)
    virtual_tables: tuple[VirtualTableReference, ...] = field(default_factory=tuple)
    parameters: tuple[str, ...] = field(default_factory=tuple)
    temp_tables_created: tuple[str, ...] = field(default_factory=tuple)
    temp_tables_read: tuple[str, ...] = field(default_factory=tuple)
    is_select: bool = True
    is_destroy_temp: bool = False
    source_method: str | None = None
    source_line: int | None = None

    @property
    def all_table_names(self) -> tuple[str, ...]:
        """Все уникальные имена таблиц (физических + виртуальных qualified)."""
        names: set[str] = set()
        for t in self.tables:
            if not t.is_temp_table:
                names.add(t.name)
        for vt in self.virtual_tables:
            names.add(vt.qualified_name)
        return tuple(sorted(names))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "tables": [t.to_dict() for t in self.tables],
            "virtual_tables": [vt.to_dict() for vt in self.virtual_tables],
            "parameters": list(self.parameters),
            "temp_tables_created": list(self.temp_tables_created),
            "temp_tables_read": list(self.temp_tables_read),
            "is_select": self.is_select,
            "is_destroy_temp": self.is_destroy_temp,
            "source_method": self.source_method,
            "source_line": self.source_line,
            "all_table_names": list(self.all_table_names),
        }


def is_register_type_name(name: str) -> bool:
    """True если строка — это тип регистра 1С (русский или EDT-английский)."""
    return name in _REGISTER_TYPES
