"""BSL AST models — frozen dataclasses для разобранного модуля.

Парсер из `bsl_ast.py` возвращает структуру верхнего уровня (BSLModule)
с методами / регионами / директивами компиляции. Тела методов хранятся
как сырой текст (для эмбеддинга / re-parse'инга на следующих фазах).

## Что моделируем

| Концепт BSL | Класс |
|---|---|
| Модуль целиком | `BSLModule` |
| Процедура / Функция | `BSLMethod` (с `kind` enum) |
| Параметр метода | `BSLParameter` |
| `#Область X` / `#КонецОбласти` | `BSLRegion` |
| `&НаСервере` / `&НаКлиенте` / ... | `compile_directive` поле метода |
| Doc-комментарий перед методом | `doc_comment` поле метода |
| `// Доработка START / END` маркеры | `customization_marker` поле метода |

## Что НЕ моделируем (намеренно отложено)

- Глобальные переменные модуля (`Перем X` на верхнем уровне) — M-K2.5.4
- Тела методов как AST (только raw text) — M-K2.5.2 query parser возьмёт
  тела и разберёт запросы внутри
- `#Если ... #Тогда ... #КонецЕсли` препроцессорные ветки — пометка есть
  через `has_preprocessor_branches`, разбор отложен
- Стало-непустые шаблоны (`Шаблон("...")`) — Phase 2 query parser
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BSLMethodKind(str, Enum):
    """Тип определения — Процедура или Функция."""

    PROCEDURE = "Procedure"
    FUNCTION = "Function"


@dataclass(frozen=True, slots=True)
class BSLParameter:
    """Параметр метода BSL.

    `by_value=True` если параметр объявлен с `Знач Параметр` —
    передаётся по значению (копия), иначе по ссылке (1С default).

    `default` хранит сырой текст значения по умолчанию (если есть):
    `Параметр = Неопределено` → `default = "Неопределено"`,
    `Параметр = 0` → `default = "0"`,
    `Параметр = ОбщегоНазначения.Метод()` → `default = "ОбщегоНазначения.Метод()"`.
    """

    name: str
    by_value: bool = False
    default: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "by_value": self.by_value, "default": self.default}


@dataclass(frozen=True, slots=True)
class BSLRegion:
    """Регион `#Область X ... #КонецОбласти`.

    `parent` — имя внешнего региона (для вложенных). None если top-level.
    `line_start` / `line_end` — 1-based номера строк (как в IDE 1С).
    """

    name: str
    parent: str | None
    line_start: int
    line_end: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parent": self.parent,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


@dataclass(frozen=True, slots=True)
class BSLMethod:
    """Определение Процедуры / Функции верхнего уровня модуля.

    Поля:
    - `name` — имя метода (без кавычек, как написано).
    - `kind` — BSLMethodKind.PROCEDURE / FUNCTION.
    - `parameters` — кортеж BSLParameter в порядке объявления.
    - `is_exported` — True если есть ключевое слово `Экспорт`.
    - `doc_comment` — собранный doc-блок `//` строк перед методом
      (БСП-стиль). None если нет.
    - `compile_directive` — `&НаСервере`, `&НаКлиенте`,
      `&НаСервереБезКонтекста`, `&ИзменениеИКонтроль("X")`, etc.
      None если нет.
    - `region` — имя ближайшего родительского `#Область`. None если
      метод вне регионов.
    - `line_start` / `line_end` — 1-based номера строк.
    - `body_source` — сырой текст метода целиком (включая сигнатуру и
      `КонецФункции`/`КонецПроцедуры`).
    - `customization_marker` — извлечённый маркер `// Доработка <X>` из
      doc_comment или из первой строки тела, если узнаваем. None
      если нет. Используется CFE-аналитикой для compare_with_typical.
    """

    name: str
    kind: str  # BSLMethodKind.value
    parameters: tuple[BSLParameter, ...]
    is_exported: bool
    doc_comment: str | None
    compile_directive: str | None
    region: str | None
    line_start: int
    line_end: int
    body_source: str
    customization_marker: str | None = None

    @property
    def signature(self) -> str:
        """Воспроизводит сигнатуру метода: `Функция X(А, Б = 0) Экспорт`."""
        keyword = (
            "Функция" if self.kind == BSLMethodKind.FUNCTION.value else "Процедура"
        )
        params = ", ".join(
            (("Знач " if p.by_value else "") + p.name)
            + (f" = {p.default}" if p.default is not None else "")
            for p in self.parameters
        )
        export = " Экспорт" if self.is_exported else ""
        return f"{keyword} {self.name}({params}){export}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "parameters": [p.to_dict() for p in self.parameters],
            "is_exported": self.is_exported,
            "doc_comment": self.doc_comment,
            "compile_directive": self.compile_directive,
            "region": self.region,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "body_source": self.body_source,
            "customization_marker": self.customization_marker,
            "signature": self.signature,
        }


@dataclass(frozen=True, slots=True)
class BSLModule:
    """Разобранный модуль BSL целиком.

    Поля:
    - `module_path` — путь к файлу (для трассировки). None если парсили
      строку.
    - `methods` — список методов в порядке появления в файле.
    - `regions` — список `#Область` (top-level и вложенные).
    - `has_errors` — True если tree-sitter обнаружил syntax errors.
      Методы извлечь обычно можно даже с ошибкой (graceful degradation).
    - `parse_errors` — текстовые описания ошибок парсинга (если есть).
    - `has_preprocessor_branches` — True если в модуле встречаются
      `#Если ... #Тогда`. Помечает что часть кода может быть условной
      (по платформе / клиенту). Полноценный разбор веток — Phase 4.
    - `total_lines` — общее количество строк в исходнике.
    """

    module_path: str | None
    methods: tuple[BSLMethod, ...]
    regions: tuple[BSLRegion, ...]
    has_errors: bool
    parse_errors: tuple[str, ...] = field(default_factory=tuple)
    has_preprocessor_branches: bool = False
    total_lines: int = 0

    @property
    def exported_methods(self) -> tuple[BSLMethod, ...]:
        """Только методы с ключевым словом `Экспорт`."""
        return tuple(m for m in self.methods if m.is_exported)

    @property
    def methods_by_name(self) -> dict[str, BSLMethod]:
        """Маппинг name → method. При коллизиях побеждает последний."""
        return {m.name: m for m in self.methods}

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": self.module_path,
            "methods": [m.to_dict() for m in self.methods],
            "regions": [r.to_dict() for r in self.regions],
            "has_errors": self.has_errors,
            "parse_errors": list(self.parse_errors),
            "has_preprocessor_branches": self.has_preprocessor_branches,
            "total_lines": self.total_lines,
        }
