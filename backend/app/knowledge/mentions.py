"""Mention parser — извлечение @Тип.Имя ссылок из user-сообщения.

M-K1.14: первая «видимая» integration Knowledge Layer. Пользователь
пишет в чат "расскажи про @Документ.ОПП" — orchestrator парсит mention,
читает dossier из metadata_cache (M-K1.12+1.13) и emit'ит ObjectCard
ДО LLM-итерации.

UX: юзер видит карту мгновенно, LLM получает enriched system prompt с
preview объекта и формирует осмысленный ответ поверх structured data.

**Грамматика mention** (минимально совместимо с реальными именами 1С):
- `@<Тип>.<Имя>` — обязательно две части
- Тип: латиница или кириллица, начинается с буквы (e.g. `Документ`,
  `Catalog`, `Регистр_сведений`)
- Имя: латиница / кириллица / цифры / underscore (после первой буквы)
- Граница перед `@`: пробел / начало строки / знак препинания
  кроме точки/at (чтобы `email@example.com` не схватило)

**НЕ обрабатываем** в M-K1.14:
- Trailing `.Реквизит.Имя` — глубже двух уровней (M-K2)
- `@@` — escaped mentions (нет use case пока)
- Mentions внутри markdown-кода — sentence-level простой regex

Модуль чистая логика без I/O — тестируется как pure functions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

from app.knowledge.dossier import ObjectDossier

logger = logging.getLogger(__name__)

# Граница перед `@` — start-of-string или whitespace или знак препинания,
# кроме `.` (чтобы не схватить `e.@v`) и кроме `@` (чтобы `a@@b` не считалось).
# Используем lookbehind фиксированной ширины (Python re поддерживает только
# фиксированные lookbehinds) — поэтому отделяем "start of string" в alternation.
#
# Паттерн: `(?:^|(?<=[\s,;!?()[\]{}«»"\']))@(<KIND>)\.(<NAME>)`
# где KIND начинается с буквы (рус/лат), NAME — буква + [буквы/цифры/_].
#
# `re.UNICODE` стоит по умолчанию для str-pattern, кириллица в `\w` работает.
_MENTION_RE = re.compile(
    r"(?:^|(?<=[\s,;!?()\[\]{}«»\"']))"
    r"@([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_]*)"
    r"\.([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)"
)


@dataclass(frozen=True, slots=True)
class ObjectMention:
    """Распарсенный mention.

    Attrs:
        full: «Документ.ОПП» — то что попадёт в ObjectPath.parse и dossier API.
        kind: первая часть («Документ»).
        name: вторая часть («ОПП»).
        raw: оригинальный фрагмент текста («@Документ.ОПП») — для замены / подсветки.
    """

    full: str
    kind: str
    name: str
    raw: str


def parse_object_mentions(text: str) -> list[ObjectMention]:
    """Извлекает все валидные mentions из текста.

    Дубликаты (одинаковый `full`) убираются с сохранением порядка первого
    появления — это важно для UX (карты идут в том порядке как юзер их назвал).

    Returns:
        Список ObjectMention. Пустой если в тексте нет mentions.
    """
    if not text:
        return []

    seen: set[str] = set()
    result: list[ObjectMention] = []

    for match in _MENTION_RE.finditer(text):
        kind = match.group(1)
        name = match.group(2)
        full = f"{kind}.{name}"
        if full in seen:
            continue
        seen.add(full)
        result.append(
            ObjectMention(
                full=full,
                kind=kind,
                name=name,
                raw=match.group(0).lstrip(),  # без ведущего пробела из границы
            )
        )

    return result


def dossier_to_object_card(dossier: ObjectDossier) -> dict:
    """Конвертирует ObjectDossier → ObjectCard payload (dict).

    Совместимо с `app.orchestrator.cards.ObjectCardPayload` и
    frontend `ObjectCardPayload` type. ВАЖНО: backend Pydantic-модель
    карты требует `header: dict` с полями name/type/path — собираем
    их из ObjectPath + presentation.

    `card_id` НЕ ставим — для pre-emit cards deanonymize не нужен
    (там нет anon-токенов, только метаданные). Если потребуется в
    будущем для каких-то enrichment — добавится отдельным шагом.

    Args:
        dossier: результат `get_dossier()` (source='cache' / 'mcp').

    Returns:
        dict с `{type: "object", payload: {...}}` готовый к
        `CardEvent.model_validate(...)`.
    """
    # presentation может быть None — в name тогда оставляем path как fallback
    display_name = dossier.presentation or dossier.object_path.name

    payload = {
        "header": {
            "name": display_name,
            "type": dossier.kind,
            "path": dossier.object_path.full,
        },
        "attributes": list(dossier.attributes),
        "tabular_sections": list(dossier.tabular_sections),
        "forms": list(dossier.forms),
        # ObjectDossier.templates ещё не в схеме (M-K1 minimum) — пустой список.
        # Frontend ObjectCard корректно показывает «Подробности недоступны»
        # если все секции пустые.
        "templates": [],
        "card_id": None,
    }
    return {"type": "object", "payload": payload}


def render_mentions_context_block(
    mentions: Iterable[ObjectMention],
    dossiers: dict[str, ObjectDossier],
) -> str | None:
    """Готовит текстовый блок для system prompt — список найденных объектов.

    LLM получает контекст «юзер упомянул эти объекты, dossier ниже» — это
    снижает риск, что модель вызовет лишний `get_metadata` (мы уже отдали
    то что есть в кеше).

    Args:
        mentions: распарсенные mentions (в порядке появления).
        dossiers: map full_path → dossier (если dossier не нашёлся в кеше,
                  ключа просто нет).

    Returns:
        Multi-line строка или None если нет ни одного found dossier.
    """
    found_lines: list[str] = []
    not_found: list[str] = []

    for mention in mentions:
        dossier = dossiers.get(mention.full)
        if dossier is None:
            not_found.append(mention.full)
            continue
        presentation = dossier.presentation or "—"
        found_lines.append(
            f"- {mention.full} ({dossier.kind}, «{presentation}»)"
        )

    if not found_lines and not not_found:
        return None

    parts: list[str] = []
    if found_lines:
        parts.append(
            "Пользователь упомянул объекты 1С через @ — паспорта переданы карточками выше:"
        )
        parts.extend(found_lines)
    if not_found:
        parts.append(
            "Эти объекты упомянуты, но в metadata_cache их нет (можно вызвать get_metadata):"
        )
        parts.extend(f"- {p}" for p in not_found)
    return "\n".join(parts)
