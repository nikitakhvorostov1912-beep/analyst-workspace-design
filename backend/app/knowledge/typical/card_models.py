"""Object Card models — frozen dataclasses для LLM-генерируемых описаний.

Карточка описывает один объект метаданных типовой конфигурации на
русском языке: что это, зачем нужно, как ведёт себя при проведении,
какие связанные объекты. Хранится в `typical_object_cards` (migration v18).

## Структура (из M-K2.5-PLAN.md → Phase 5)

```yaml
object: "Документ.РеализацияТоваровУслуг"
config: "_bp30_138_24"
summary: "Документ продажи товаров и услуг покупателю..."
purpose: "Регистрирует факт реализации в БУ и управленческом учёте"
key_attributes:
  - {name: "Контрагент", role: "получатель"}
  - {name: "Договор", role: "основа для расчётов"}
movements:
  - {register: "РегистрНакопления.ТоварыНаСкладах",
     direction: "расход", condition: "при списании товаров"}
posting_flow:
  - "Заполнение шапки реквизитов"
  - "Подбор товаров через ТЧ"
  - "Запись движений в 8 регистров"
typical_scenarios:
  - "Оптовая продажа со склада"
preconditions:
  - "УчётнаяПолитика.УчётНДС включён"
related_objects:
  - "Документ.ВозвратТоваровОтПокупателя"
its_links:
  - "std.proveryat_zapolnenie_polej"
```

## Идемпотентность

`source_hash` (SHA-256 от input_context) хранится в БД. При повторной
генерации:
- Если hash совпал — skip (карточка актуальна).
- Если hash другой — re-generate (объект изменился в типовой).

## Эмбеддинг

Эмбедятся **только** `summary` + `purpose` + первые ~3 элемента
`posting_flow`. Сам код тела методов не уходит в OpenAI/embedding API —
это политика из ADR-003 для legal-clean processing.

## Status lifecycle

- `pending` — карточка создана, контекст собран, ждём LLM
- `generated` — LLM вернул валидный JSON, карточка сохранена
- `embedded` — embedding записан в vec_objects
- `failed` — LLM/parse/embed ошибка (см. error)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CardStatus(str, Enum):
    """Lifecycle карточки."""

    PENDING = "pending"
    GENERATED = "generated"
    EMBEDDED = "embedded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CardAttribute:
    """Один ключевой реквизит в карточке."""

    name: str
    role: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role}


@dataclass(frozen=True, slots=True)
class CardMovement:
    """Один тип движений (для документов)."""

    register: str
    direction: str = ""  # "приход" | "расход" | "приход/расход"
    condition: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "register": self.register,
            "direction": self.direction,
            "condition": self.condition,
        }


@dataclass(frozen=True, slots=True)
class TypicalObjectCard:
    """Полная карточка объекта типовой.

    Содержит описательные поля (русский) + структурированные списки.
    Сериализуется в JSON для хранения в `typical_object_cards.card_payload`.
    """

    # Метаданные
    object_qualified_name: str          # "Document.РеализацияТоваровУслуг"
    object_kind: str                     # "Document"
    channel_id: str                      # "_bp30_138_24"

    # Описательная часть (LLM генерирует)
    summary: str = ""                    # 1-3 предложения
    purpose: str = ""                    # назначение в учёте
    key_attributes: tuple[CardAttribute, ...] = field(default_factory=tuple)
    movements: tuple[CardMovement, ...] = field(default_factory=tuple)
    posting_flow: tuple[str, ...] = field(default_factory=tuple)
    typical_scenarios: tuple[str, ...] = field(default_factory=tuple)
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    related_objects: tuple[str, ...] = field(default_factory=tuple)
    its_links: tuple[str, ...] = field(default_factory=tuple)

    # Embedding text (что уйдёт в embedding API)
    @property
    def embedding_text(self) -> str:
        """Возвращает русский текст для эмбеддинга.

        Только summary + purpose + первые 3 элемента posting_flow.
        Сам код тел методов не включается (политика ADR-003).
        """
        parts: list[str] = []
        if self.summary:
            parts.append(self.summary.strip())
        if self.purpose:
            parts.append(self.purpose.strip())
        if self.posting_flow:
            flow = " → ".join(s.strip() for s in self.posting_flow[:3] if s.strip())
            if flow:
                parts.append(flow)
        return "\n\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_qualified_name": self.object_qualified_name,
            "object_kind": self.object_kind,
            "channel_id": self.channel_id,
            "summary": self.summary,
            "purpose": self.purpose,
            "key_attributes": [a.to_dict() for a in self.key_attributes],
            "movements": [m.to_dict() for m in self.movements],
            "posting_flow": list(self.posting_flow),
            "typical_scenarios": list(self.typical_scenarios),
            "preconditions": list(self.preconditions),
            "related_objects": list(self.related_objects),
            "its_links": list(self.its_links),
        }

    def to_payload_json(self) -> str:
        """Сериализованный JSON для card_payload колонки в БД."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_payload_json(
        cls,
        *,
        channel_id: str,
        object_qualified_name: str,
        object_kind: str,
        payload_json: str,
    ) -> "TypicalObjectCard":
        """Загружает карточку из JSON-payload."""
        raw = json.loads(payload_json) if payload_json else {}
        key_attrs = tuple(
            CardAttribute(name=a.get("name", ""), role=a.get("role", ""))
            for a in raw.get("key_attributes", [])
        )
        movements = tuple(
            CardMovement(
                register=m.get("register", ""),
                direction=m.get("direction", ""),
                condition=m.get("condition", ""),
            )
            for m in raw.get("movements", [])
        )
        return cls(
            object_qualified_name=object_qualified_name,
            object_kind=object_kind,
            channel_id=channel_id,
            summary=raw.get("summary", ""),
            purpose=raw.get("purpose", ""),
            key_attributes=key_attrs,
            movements=movements,
            posting_flow=tuple(raw.get("posting_flow", [])),
            typical_scenarios=tuple(raw.get("typical_scenarios", [])),
            preconditions=tuple(raw.get("preconditions", [])),
            related_objects=tuple(raw.get("related_objects", [])),
            its_links=tuple(raw.get("its_links", [])),
        )


@dataclass(frozen=True, slots=True)
class TypicalObjectCardRecord:
    """Запись карточки в БД с метаданными (status / hash / token_usage)."""

    id: int
    channel_id: str
    object_qualified_name: str
    object_kind: str
    card: TypicalObjectCard
    source_hash: str
    prompt_version: str
    llm_model: str | None
    token_usage_in: int | None
    token_usage_out: int | None
    embedding_model: str | None
    embedding_dim: int | None
    status: str
    error: str | None
    created_at: str | None
    updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "object_qualified_name": self.object_qualified_name,
            "object_kind": self.object_kind,
            "card": self.card.to_dict(),
            "source_hash": self.source_hash,
            "prompt_version": self.prompt_version,
            "llm_model": self.llm_model,
            "token_usage_in": self.token_usage_in,
            "token_usage_out": self.token_usage_out,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
