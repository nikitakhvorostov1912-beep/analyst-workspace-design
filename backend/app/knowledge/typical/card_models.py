"""Object Card models — Pydantic BaseModel(frozen=True) для LLM-генерируемых описаний.

Карточка описывает один объект метаданных типовой конфигурации на
русском языке: что это, зачем нужно, как ведёт себя при проведении,
какие связанные объекты. Хранится в `typical_object_cards` (migration v18).

## Миграция dataclass → Pydantic (M-K2.5.9.1, 2026-05-27)

Карточки переведены с `@dataclass(frozen=True, slots=True)` на
`BaseModel(model_config=ConfigDict(frozen=True))`. Причины:
- Хард-валидация полей по типу (отлавливаем кривой LLM output на парсинге).
- Field-level constraints (max_length) — основа step-3.
- Discriminated unions / Literal types — основа step-4.
- Backward compat: `extra='ignore'` — старые поля в БД не валят парсинг.

Публичный API сохранён: `to_dict()`, `to_payload_json()`,
`from_payload_json()`, property `embedding_text`.

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
import re
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Hard limits (M-K2.5.9.3) ──────────────────────────────────────────
#
# Pydantic Field max_length применяется к новым карточкам (LLM-output
# обязан укладываться). Backward compat: from_payload_json делает
# defensive truncation перед валидацией для legacy 63k карточек.
#
# Лимиты — публичные константы, источник истины для промпта
# `typical_card_generator.md` и тестов.

# Строковые лимиты (длина в символах)
MAX_OBJECT_QNAME_LEN = 300
MAX_OBJECT_KIND_LEN = 60
MAX_CHANNEL_ID_LEN = 120
MAX_SUMMARY_LEN = 400
MAX_PURPOSE_LEN = 600
MAX_ATTR_NAME_LEN = 200
MAX_ATTR_ROLE_LEN = 120
MAX_REGISTER_NAME_LEN = 200
MAX_DIRECTION_LEN = 80
MAX_MOVEMENT_CONDITION_LEN = 200
MAX_POSTING_STEP_LEN = 200
MAX_SCENARIO_LEN = 200
MAX_PRECONDITION_LEN = 200
MAX_RELATED_NAME_LEN = 200
MAX_ITS_LINK_LEN = 200

# Лимиты на количество элементов в tuple-полях
MAX_KEY_ATTRIBUTES = 10
MAX_MOVEMENTS = 15
MAX_POSTING_FLOW = 8
MAX_TYPICAL_SCENARIOS = 5
MAX_PRECONDITIONS = 6
MAX_RELATED_OBJECTS = 10
MAX_ITS_LINKS = 5


# Annotated типы для tuple-элементов с per-element string limits.
# Pydantic v2 поддерживает Annotated[str, Field(max_length=N)] внутри tuple.
PostingStep = Annotated[str, Field(max_length=MAX_POSTING_STEP_LEN)]
Scenario = Annotated[str, Field(max_length=MAX_SCENARIO_LEN)]
Precondition = Annotated[str, Field(max_length=MAX_PRECONDITION_LEN)]
RelatedName = Annotated[str, Field(max_length=MAX_RELATED_NAME_LEN)]
ITSLink = Annotated[str, Field(max_length=MAX_ITS_LINK_LEN)]


# ── Closed vocabulary (M-K2.5.9.4) ────────────────────────────────────
#
# Защита от fragmentation графа: LLM может изобрести «отгрузка» / «expense»
# / «outgoing» вместо canonical «расход». Literal types — единственный
# источник истины для direction. Pydantic отклонит произвольное значение.

#: Допустимые значения для CardMovement.direction.
#: - "приход" — увеличение остатка (получение товара, начисление взаиморасчётов)
#: - "расход" — уменьшение остатка (списание товара, погашение взаиморасчётов)
#: - "приход/расход" — сторно или зависит от условия
#: - "запись" — для информационных регистров (не аккумуляции)
#: - "" — direction неизвестен (mock-карточки) или не применимо
MovementDirection = Literal["приход", "расход", "приход/расход", "запись", ""]

#: Префиксы канонических имён регистров. Регистр должен быть в формате
#: `<Prefix>.<Имя>`. Поддерживается 4 типа из платформы 1С.
ALLOWED_REGISTER_KINDS: frozenset[str] = frozenset({
    "AccumulationRegister",
    "InformationRegister",
    "AccountingRegister",
    "CalculationRegister",
})

#: Mapping legacy / синонимы → canonical direction.
#: Применяется в from_payload_json при загрузке старых карточек.
_DIRECTION_NORMALIZE: dict[str, MovementDirection] = {
    "": "",
    "приход": "приход",
    "расход": "расход",
    "приход/расход": "приход/расход",
    "запись": "запись",
    # Synonyms / legacy:
    "expense": "расход",
    "income": "приход",
    "spending": "расход",
    "receipt": "приход",
    "in": "приход",
    "out": "расход",
    "+": "приход",
    "-": "расход",
    "write": "запись",
}

# regex: <Kind>.<Name> где Kind — один из ALLOWED_REGISTER_KINDS.
# Точка обязательна, имя после неё — non-empty.
_REGISTER_NAME_RE = re.compile(
    r"^(?:" + "|".join(re.escape(k) for k in ALLOWED_REGISTER_KINDS) + r")\.\S.*$"
)


def normalize_direction(value: Any) -> MovementDirection:
    """Усекает / нормализует direction до canonical допустимого значения.

    Используется для backward compat и для defensive обработки LLM-output.
    Неизвестные значения → "" (вместо ValidationError).
    """
    if value is None:
        return ""
    key = str(value).strip().lower()
    return _DIRECTION_NORMALIZE.get(key, "")


class CardStatus(str, Enum):
    """Lifecycle карточки."""

    PENDING = "pending"
    GENERATED = "generated"
    EMBEDDED = "embedded"
    FAILED = "failed"


class CardAttribute(BaseModel):
    """Один ключевой реквизит в карточке."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(max_length=MAX_ATTR_NAME_LEN)
    role: str = Field(default="", max_length=MAX_ATTR_ROLE_LEN)

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "role": self.role}


class CardMovement(BaseModel):
    """Один тип движений (для документов).

    M-K2.5.9.4: direction — closed vocabulary (`Literal`), register —
    must match `<Kind>.<Name>` format где Kind ∈ ALLOWED_REGISTER_KINDS.
    Защита графа от fragmentation: разные синонимы в одно ведро.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    register: str = Field(max_length=MAX_REGISTER_NAME_LEN)
    direction: MovementDirection = ""
    condition: str = Field(default="", max_length=MAX_MOVEMENT_CONDITION_LEN)

    @field_validator("register", mode="after")
    @classmethod
    def _validate_register_format(cls, value: str) -> str:
        """Проверяет что register имеет формат `<Kind>.<Имя>`.

        Допустимые Kind: см. ALLOWED_REGISTER_KINDS. Без точки или с
        unknown prefix — отклонить (защита от LLM-фантазий вроде
        "РегистрНакопления.X" русскими буквами или "Регистр.X").
        """
        if not value:
            raise ValueError("register не может быть пустым")
        if not _REGISTER_NAME_RE.match(value):
            raise ValueError(
                f"register должен начинаться с одного из "
                f"{sorted(ALLOWED_REGISTER_KINDS)} и содержать точку + имя, "
                f"получено: {value!r}"
            )
        return value

    def to_dict(self) -> dict[str, str]:
        return {
            "register": self.register,
            "direction": self.direction,
            "condition": self.condition,
        }


class TypicalObjectCard(BaseModel):
    """Полная карточка объекта типовой.

    Содержит описательные поля (русский) + структурированные списки.
    Сериализуется в JSON для хранения в `typical_object_cards.card_payload`.

    frozen=True — попытка mutation поднимет ValidationError.
    extra='ignore' — backward compat: старые поля в БД (legacy) не валят парсинг.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    # Метаданные
    object_qualified_name: str = Field(max_length=MAX_OBJECT_QNAME_LEN)
    object_kind: str = Field(max_length=MAX_OBJECT_KIND_LEN)
    channel_id: str = Field(max_length=MAX_CHANNEL_ID_LEN)

    # Описательная часть (LLM генерирует) — hard limits защищают от
    # overshoot (LLM любит писать «развёрнутые объяснения») и от
    # accidental DoS через context window overflow.
    summary: str = Field(default="", max_length=MAX_SUMMARY_LEN)
    purpose: str = Field(default="", max_length=MAX_PURPOSE_LEN)
    key_attributes: tuple[CardAttribute, ...] = Field(default=(), max_length=MAX_KEY_ATTRIBUTES)
    movements: tuple[CardMovement, ...] = Field(default=(), max_length=MAX_MOVEMENTS)
    posting_flow: tuple[PostingStep, ...] = Field(default=(), max_length=MAX_POSTING_FLOW)
    typical_scenarios: tuple[Scenario, ...] = Field(default=(), max_length=MAX_TYPICAL_SCENARIOS)
    preconditions: tuple[Precondition, ...] = Field(default=(), max_length=MAX_PRECONDITIONS)
    related_objects: tuple[RelatedName, ...] = Field(default=(), max_length=MAX_RELATED_OBJECTS)
    its_links: tuple[ITSLink, ...] = Field(default=(), max_length=MAX_ITS_LINKS)

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
        """JSON-friendly dict (tuple → list).

        Сохраняем поведение dataclass-версии один-в-один: ключи и порядок
        полей те же, list вместо tuple, вложенные модели через to_dict().
        """
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
        """Сериализованный JSON для card_payload колонки в БД.

        Используем json.dumps + sort_keys=True (а не model_dump_json),
        чтобы сохранить детерминированный порядок ключей и совместимость
        с уже сохранёнными 63 197 карточками.
        """
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
        """Загружает карточку из JSON-payload.

        Backward compat: payload может содержать поля старого формата
        (например, неизвестный extra-ключ). `extra='ignore'` в config
        проигнорирует их без ошибки.
        """
        raw = json.loads(payload_json) if payload_json else {}
        # Defensive truncation (M-K2.5.9.3) — обрезаем legacy payload до
        # новых лимитов ПЕРЕД валидацией. Это даёт идемпотентность
        # для 63 197 существующих карточек: даже если в БД случайно
        # окажется overshoot, мы загрузим без падения, обрезанный.
        def _trunc_str(value: Any, max_len: int) -> str:
            s = str(value) if value is not None else ""
            return s[:max_len]

        def _trunc_list(value: Any, max_items: int) -> list[Any]:
            if not isinstance(value, list):
                return []
            return value[:max_items]

        def _trunc_str_list(value: Any, max_items: int, max_len: int) -> list[str]:
            return [_trunc_str(v, max_len) for v in _trunc_list(value, max_items)]

        def _normalize_movements(value: Any) -> list[dict[str, str]]:
            """Backward compat для legacy / non-canonical movements.

            - direction: маппится через normalize_direction (синонимы → canonical)
            - register: невалидный формат skip-аем (защита от ValidationError)
            """
            result: list[dict[str, str]] = []
            for m in _trunc_list(value, MAX_MOVEMENTS):
                if not isinstance(m, dict):
                    continue
                register = _trunc_str(m.get("register"), MAX_REGISTER_NAME_LEN)
                if not register or not _REGISTER_NAME_RE.match(register):
                    # Drop невалидный movement — лучше пустой массив,
                    # чем падение валидации.
                    continue
                result.append({
                    "register": register,
                    "direction": normalize_direction(m.get("direction")),
                    "condition": _trunc_str(m.get("condition"), MAX_MOVEMENT_CONDITION_LEN),
                })
            return result

        # Метаданные канала / qname берём из аргументов (источник истины — БД row),
        # а не из payload (там они могут отсутствовать или быть устаревшими).
        data: dict[str, Any] = {
            "object_qualified_name": _trunc_str(object_qualified_name, MAX_OBJECT_QNAME_LEN),
            "object_kind": _trunc_str(object_kind, MAX_OBJECT_KIND_LEN),
            "channel_id": _trunc_str(channel_id, MAX_CHANNEL_ID_LEN),
            "summary": _trunc_str(raw.get("summary", ""), MAX_SUMMARY_LEN),
            "purpose": _trunc_str(raw.get("purpose", ""), MAX_PURPOSE_LEN),
            "key_attributes": _trunc_list(raw.get("key_attributes"), MAX_KEY_ATTRIBUTES),
            "movements": _normalize_movements(raw.get("movements")),
            "posting_flow": _trunc_str_list(
                raw.get("posting_flow"), MAX_POSTING_FLOW, MAX_POSTING_STEP_LEN,
            ),
            "typical_scenarios": _trunc_str_list(
                raw.get("typical_scenarios"), MAX_TYPICAL_SCENARIOS, MAX_SCENARIO_LEN,
            ),
            "preconditions": _trunc_str_list(
                raw.get("preconditions"), MAX_PRECONDITIONS, MAX_PRECONDITION_LEN,
            ),
            "related_objects": _trunc_str_list(
                raw.get("related_objects"), MAX_RELATED_OBJECTS, MAX_RELATED_NAME_LEN,
            ),
            "its_links": _trunc_str_list(
                raw.get("its_links"), MAX_ITS_LINKS, MAX_ITS_LINK_LEN,
            ),
        }
        return cls.model_validate(data)


@dataclass(frozen=True, slots=True)
class TypicalObjectCardRecord:
    """Запись карточки в БД с метаданными (status / hash / token_usage).

    Остаётся frozen dataclass — это контейнер DB-row, не объект LLM-output.
    Pydantic-валидация полей не нужна (значения уже валидированы при чтении
    из SQLite).
    """

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
    # v19 (M-K2.5.9.2) — mock isolation:
    # True если карточка сгенерирована MockLLMCaller (`llm_model='mock-generator-v1'`).
    # UI показывает бейдж «Mock data — не верифицировано экспертом».
    is_mock: bool = False
    # v20 (M-K2.5.9.5) — graph validation:
    # validation_status — 'valid' | 'issues_found' | 'object_not_in_graph' | None
    # validation_issues — JSON-сериализованный list[CardValidationIssue]
    # validated_at — ISO timestamp последней валидации (None = не валидировалась)
    validation_status: str | None = None
    validation_issues: str | None = None
    validated_at: str | None = None
    # v21 (M-K2.5.9.6) — embedding versioning:
    # семантическая версия embedding-пайплайна, например "v1.0" / "v2.0".
    # Отличается от `embedding_model` (имя провайдера) тем, что фиксирует
    # правила text-extraction / postprocessing.
    embedding_model_version: str | None = None

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
            "is_mock": self.is_mock,
            "validation_status": self.validation_status,
            "validation_issues": (
                json.loads(self.validation_issues) if self.validation_issues else None
            ),
            "validated_at": self.validated_at,
            "embedding_model_version": self.embedding_model_version,
        }
