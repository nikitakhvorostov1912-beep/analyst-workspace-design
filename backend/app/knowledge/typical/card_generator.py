"""LLM-driven Object Card generator (M-K2.5.5).

Принимает CardContext + LLMCaller → возвращает TypicalObjectCard.

## Архитектура

```
build_card_context(db, channel) → CardContext
        ↓
generate_card(context, llm_caller) → TypicalObjectCard
        ↓
upsert_card(db, card, source_hash=context.compute_source_hash())
```

`LLMCaller` — Protocol, разрешающий подключить любого провайдера
(OpenAI / xAI / Anthropic / mock). Сам генератор не зависит от
конкретного HTTP-клиента.

## Mock-режим

`MockLLMCaller` возвращает детерминированный stub. Используется в:
- тестах (без расхода токенов)
- pilot скриптах когда пользователь хочет smoke без LLM-ключа
- разработке

## Идемпотентность

Генерация **не идемпотентна** сама по себе (LLM может вернуть разные
тексты при temperature > 0). Идемпотентность — на уровне `upsert_card`:
если `source_hash` контекста не изменился, новая карточка просто
перезатрёт предыдущую. Для skip-если-неизменился — вызывающий код
должен сравнить hash через `get_existing_source_hash` ДО вызова LLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.knowledge.typical.card_context import CardContext
from app.knowledge.typical.card_models import (
    CardAttribute,
    CardMovement,
    TypicalObjectCard,
)

logger = logging.getLogger(__name__)


# ── Prompt template ──────────────────────────────────────────────────


_PROMPT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts" / "typical_card_generator.md"
)

PROMPT_VERSION = "v1"


def load_prompt_template() -> str:
    """Возвращает текст промпта (markdown с system + user разделами).

    Кешируется на module-level через @lru_cache в impl — пока без
    кеша для простоты, читается каждый вызов (быстро, ~0.1ms).
    """
    if not _PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"prompt template не найден: {_PROMPT_TEMPLATE_PATH}"
        )
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_messages(context: CardContext) -> list[dict[str, str]]:
    """Формирует messages для OpenAI-compatible chat completion API.

    Парсит prompt template на System / User блоки + подставляет
    context_json.
    """
    template = load_prompt_template()
    system_part, user_part = _split_system_user(template)
    user_filled = user_part.replace("{context_json}", context.to_compact_json())
    return [
        {"role": "system", "content": system_part.strip()},
        {"role": "user", "content": user_filled.strip()},
    ]


def _split_system_user(template: str) -> tuple[str, str]:
    """Извлекает блоки `## System` и `## User` из markdown-шаблона."""
    parts = re.split(r"^##\s+", template, flags=re.MULTILINE)
    system_block = ""
    user_block = ""
    for part in parts:
        lower = part.lstrip().lower()
        if lower.startswith("system"):
            system_block = _strip_section_header(part)
        elif lower.startswith("user"):
            user_block = _strip_section_header(part)
    if not system_block or not user_block:
        raise ValueError(
            "prompt template должен содержать '## System' и '## User' блоки"
        )
    return system_block, user_block


def _strip_section_header(part: str) -> str:
    """Убирает первую строку (заголовок секции) из markdown-блока."""
    lines = part.split("\n", 1)
    return lines[1] if len(lines) > 1 else ""


# ── LLMCaller Protocol ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Результат вызова LLM: текст + token usage."""

    content: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None


class LLMCaller(Protocol):
    """Provider-agnostic LLM-call интерфейс."""

    async def complete(self, messages: list[dict[str, str]]) -> LLMResponse: ...


# ── Mock LLMCaller для тестов и pilot smoke ──────────────────────────


@dataclass(frozen=True, slots=True)
class MockLLMCaller:
    """Возвращает stub JSON-карточку на основе контекста.

    НЕ делает реальный HTTP-call. Полезно для:
    - юнит-тестов (детерминированно)
    - pilot smoke без LLM-ключа (проверить pipeline end-to-end)
    """

    model_name: str = "mock-generator-v1"

    async def complete(self, messages: list[dict[str, str]]) -> LLMResponse:
        # Извлекаем context_json из последнего user-сообщения
        user_content = messages[-1]["content"] if messages else ""
        context_json = _extract_context_json(user_content)
        context_dict = json.loads(context_json) if context_json else {}

        stub = _build_mock_card_payload(context_dict)
        return LLMResponse(
            content=json.dumps(stub, ensure_ascii=False),
            tokens_in=len(user_content) // 4,  # rough estimate
            tokens_out=len(json.dumps(stub)) // 4,
            model=self.model_name,
        )


def _extract_context_json(user_content: str) -> str:
    """Извлекает JSON-контекст из тела user-сообщения.

    Промпт-шаблон обёрнут как ```\nКонтекст объекта:\n{json}\n```.
    """
    # Ищем `Контекст объекта:` затем JSON object.
    marker = "Контекст объекта:"
    idx = user_content.find(marker)
    if idx < 0:
        return "{}"
    rest = user_content[idx + len(marker):]
    # Берём от первой `{` до последней соответствующей `}`
    start = rest.find("{")
    end = rest.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return "{}"
    return rest[start:end + 1]


def _build_mock_card_payload(context: dict[str, Any]) -> dict[str, Any]:
    """Строит stub-карточку из context для mock-LLM.

    Имитирует реальный output: summary, purpose, attributes, movements,
    posting_flow.
    """
    name = context.get("object_name", "Объект")
    kind = context.get("object_kind", "")
    kind_ru = _RU_KIND_LABELS.get(kind, kind)

    writes_to = context.get("writes_to", []) or []
    reads_from = context.get("reads_from", []) or []
    referenced_by = context.get("referenced_by", []) or []
    attributes = context.get("attributes", []) or []
    methods = context.get("methods", []) or []

    summary = f"{kind_ru} «{name}»."
    if context.get("object_comment"):
        summary += " " + context["object_comment"]

    purpose = f"Структурный элемент конфигурации, тип {kind_ru}."
    if writes_to:
        purpose += f" Записывает движения в {len(writes_to)} регистр(ов)."

    key_attributes = [
        {"name": a.get("name", ""), "role": ""}
        for a in attributes[:5]
    ]

    movements = [
        {"register": w, "direction": "", "condition": ""} for w in writes_to[:5]
    ]

    posting_flow: list[str] = []
    handler_methods = [m for m in methods if m.get("is_handler")]
    for m in handler_methods[:4]:
        posting_flow.append(f"Срабатывает {m.get('name', 'handler')}")

    return {
        "summary": summary,
        "purpose": purpose,
        "key_attributes": key_attributes,
        "movements": movements,
        "posting_flow": posting_flow,
        "typical_scenarios": [],
        "preconditions": [],
        "related_objects": [r for r in referenced_by[:5]],
        "its_links": [],
    }


_RU_KIND_LABELS: dict[str, str] = {
    "Document": "Документ",
    "Catalog": "Справочник",
    "Enum": "Перечисление",
    "AccumulationRegister": "Регистр накопления",
    "InformationRegister": "Регистр сведений",
    "AccountingRegister": "Регистр бухгалтерии",
    "CalculationRegister": "Регистр расчёта",
    "ChartOfAccounts": "План счетов",
    "ChartOfCharacteristicTypes": "План видов характеристик",
    "ChartOfCalculationTypes": "План видов расчёта",
    "CommonModule": "Общий модуль",
    "Report": "Отчёт",
    "DataProcessor": "Обработка",
    "Constant": "Константа",
    "BusinessProcess": "Бизнес-процесс",
    "Task": "Задача",
    "DocumentJournal": "Журнал документов",
    "EventSubscription": "Подписка на событие",
    "ScheduledJob": "Регламентное задание",
}


# ── generate_card ────────────────────────────────────────────────────


class CardGenerationError(Exception):
    """LLM-ответ не парсится или провалил валидацию."""


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Результат одной генерации."""

    card: TypicalObjectCard
    tokens_in: int | None
    tokens_out: int | None
    model: str | None


async def generate_card(
    *,
    context: CardContext,
    llm: LLMCaller,
) -> GenerationResult:
    """Генерирует TypicalObjectCard через LLMCaller.

    Raises:
        CardGenerationError: если ответ LLM не парсится в JSON или
            не содержит ожидаемых полей.
    """
    messages = build_messages(context)
    response = await llm.complete(messages)

    payload = _parse_llm_response(response.content)
    card = _payload_to_card(context=context, payload=payload)
    return GenerationResult(
        card=card,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        model=response.model,
    )


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Парсит JSON из LLM-ответа, толерантно к окружающему markdown."""
    text = content.strip()
    # Срезаем код-fence ```json ... ``` если есть
    fenced = re.match(r"^```(?:json)?\s*(.*)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CardGenerationError(
            f"LLM вернул не-JSON: {exc}. Первые 200 chars: {content[:200]!r}"
        ) from exc
    if not isinstance(result, dict):
        raise CardGenerationError(
            f"LLM вернул не объект (а {type(result).__name__})"
        )
    return result


def _payload_to_card(
    *, context: CardContext, payload: dict[str, Any],
) -> TypicalObjectCard:
    """Маппит распарсенный payload + контекст → TypicalObjectCard."""
    key_attrs_raw = payload.get("key_attributes") or []
    movements_raw = payload.get("movements") or []

    key_attributes = tuple(
        CardAttribute(
            name=str(a.get("name", "")).strip(),
            role=str(a.get("role", "")).strip(),
        )
        for a in key_attrs_raw
        if isinstance(a, dict) and a.get("name")
    )
    movements = tuple(
        CardMovement(
            register=str(m.get("register", "")).strip(),
            direction=str(m.get("direction", "")).strip(),
            condition=str(m.get("condition", "")).strip(),
        )
        for m in movements_raw
        if isinstance(m, dict) and m.get("register")
    )

    return TypicalObjectCard(
        object_qualified_name=context.object_qualified_name,
        object_kind=context.object_kind,
        channel_id=_extract_channel_id_from_context(context),
        summary=_clean_str(payload.get("summary")),
        purpose=_clean_str(payload.get("purpose")),
        key_attributes=key_attributes,
        movements=movements,
        posting_flow=_str_tuple(payload.get("posting_flow")),
        typical_scenarios=_str_tuple(payload.get("typical_scenarios")),
        preconditions=_str_tuple(payload.get("preconditions")),
        related_objects=_str_tuple(payload.get("related_objects")),
        its_links=_str_tuple(payload.get("its_links")),
    )


def _extract_channel_id_from_context(context: CardContext) -> str:
    """CardContext не несёт channel_id напрямую (он передаётся отдельно
    в call'е), но мы извлекаем его из to_dict если он там есть.

    Для card_generator вызывающий код должен сам передать channel_id
    через wrapping. См. pilot скрипт.
    """
    # Защитный fallback — пустая строка приведёт к ошибке при upsert,
    # что нам и нужно (явно укажет на баг wiring'а).
    return ""


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(v).strip() for v in value if v is not None and str(v).strip())


# ── Wrapper для генерации с правильным channel_id ────────────────────


async def generate_card_for_channel(
    *,
    context: CardContext,
    channel_id: str,
    llm: LLMCaller,
) -> GenerationResult:
    """Удобная обёртка: генерация + установка channel_id в карточку.

    Используется в pilot скриптах вместо прямого generate_card,
    т.к. CardContext не несёт channel_id (он избыточен в контексте,
    но обязателен в TypicalObjectCard для FK на типовую).
    """
    result = await generate_card(context=context, llm=llm)
    # Пересоздаём card с правильным channel_id (frozen dataclass)
    card_with_channel = TypicalObjectCard(
        object_qualified_name=result.card.object_qualified_name,
        object_kind=result.card.object_kind,
        channel_id=channel_id,
        summary=result.card.summary,
        purpose=result.card.purpose,
        key_attributes=result.card.key_attributes,
        movements=result.card.movements,
        posting_flow=result.card.posting_flow,
        typical_scenarios=result.card.typical_scenarios,
        preconditions=result.card.preconditions,
        related_objects=result.card.related_objects,
        its_links=result.card.its_links,
    )
    return GenerationResult(
        card=card_with_channel,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        model=result.model,
    )
