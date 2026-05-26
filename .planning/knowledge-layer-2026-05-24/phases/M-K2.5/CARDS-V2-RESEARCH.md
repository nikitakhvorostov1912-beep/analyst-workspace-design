---
research: "Object Cards v2 — production практики и аналоги"
date: "2026-05-27"
researcher: "deep-researcher (60+ источников, 22 detailed)"
status: "applied to CARDS-V2-PLAN.md"
---

# Research findings — Object Cards v2

> Глубокое исследование production-практик для knowledge cards о коде /
> метаданных 1С. Источники: 60+, проанализировано детально 22.
> На основе результатов **существенно скорректирован** CARDS-V2-PLAN.md.

## 1. Реальные аналоги нашей системы

### Прямые аналоги — карточки знаний о коде

| Проект | Что делает | Применимость к нам |
|---|---|---|
| **DeepWiki** (Cognition/Devin) | Индексирует 50k+ GitHub репо. **Не хранит карточки в фиксированной схеме — генерирует on-demand из кеша**. RAG поверх Markdown | Подход «on-demand vs pre-computed» — стоит рассмотреть для редко-запрашиваемых объектов |
| **Microsoft GraphRAG** (33.2k ⭐) | Entity + relationship extraction, community summaries. **Прямое предупреждение**: без нормализации entity_types граф фрагментируется на тысячи логически эквивалентных но текстово разных типов рёбер | **Прямая угроза** нашему графу: 6 типов рёбер нормализованы, но LLM-карточки могут использовать другие термины для тех же связей |
| **Sourcegraph Code Graph** | Entity types: definitions, references, symbols, doc-comments. **Разделяет граф от LLM-описаний** — граф для навигации, LLM для ответов | Подтверждает нашу архитектуру: graph_nodes + typical_object_cards разделены |
| **FalkorDB Code Graph** | Готовая схема: Module / Class / Function / File / Variable + CONTAINS / CALLS / INHERITS_FROM | Близкий пример успешной schema для code graph |

### Retrieval паттерны

| Проект | Паттерн | Применимость |
|---|---|---|
| **Mem0 v3** (23k ⭐) | **Параллельный скоринг**: semantic + BM25 + entity matching → fusion. v2→v3 миграция сломала все hard-coded thresholds | КРИТИЧНО для нас: substring сейчас → нужен hybrid BM25 + dense |
| **RAGFlow 2025** | Hybrid retrieval = standard production | Подтверждение Mem0 паттерна |

### 1С-специфичные системы

| Проект | Что делает | Звёзды | Применимость |
|---|---|---:|---|
| **bsl-atlas** (Arman Kudaibergenov) | MCP-сервер: vector + BM25 + call graph для 1С/BSL. **structural and semantic code search across enterprise codebases** | 55 ⭐ | Ближайший аналог. Но **не генерирует LLM-описания** — только search-индекс. Подтверждает паттерн «hybrid retrieval» |
| **bsl-graph** (alkoleft) | Kotlin + Spring + NebulaGraph + bsl-mdclasses. Граф конфигурации 1С с визуализацией Sigma.js | 43 ⭐ | Только граф, без LLM-карточек. Подтверждает архитектуру graph separately from cards |
| **comol/ai_rules_1c** | 13 субагентов + правила для AI по типам объектов 1С | — | Reference data для discriminated schemas — там описано что важно для каждого типа объекта |
| **1С:Напарник** | Закрытый, нет публичных деталей по архитектуре | — | Известно только: EDT-интегрирован, бесплатно до окт 2026 для партнёров |

**Важный вывод**: ни один из найденных 1С-проектов **не делает LLM-карточек** уровня нашей системы. Мы строим новое production-направление. Это значит мы должны быть особенно осторожны с подводными камнями.

## 2. LLM-judge и валидация — best practices

### Frameworks

| Tool | Тип | Когда применять |
|---|---|---|
| **DeepEval** | open source, PyTest-native | CI/CD gates. Production targets: faithfulness > 0.8, context_precision > 0.8 |
| **RAGAS** | open source | Exploration, не CI |
| **GraphEval** (arxiv 2407.10793) | подход через KG validation | **Идеально для нас** — у нас уже есть граф 2.2M узлов, можно валидировать карточки против него |
| **Cleanlab TLM** | платный + free tier | Benchmarked best recall на hallucination в 2025 |

### Knowledge Card paper (arxiv 2305.09955)

Академический подход: специализированные LM как параметрические хранилища для отдельных доменов + **три content selectors**: relevance, brevity, factuality. Архитектурно близко к нашей идее.

## 3. Discriminated Unions — production code patterns

### Pydantic v2 + Instructor (рекомендованный паттерн)

```python
from typing import Literal, Union, Annotated
from pydantic import BaseModel, Field

class DocumentCard(BaseModel):
    object_type: Literal["Document"] = "Document"
    posting_flow: list[PostingStep]
    accumulation_registers: list[str]

class CatalogCard(BaseModel):
    object_type: Literal["Catalog"] = "Catalog"
    hierarchy_type: str
    owner_type: str | None

class InformationRegisterCard(BaseModel):
    object_type: Literal["InformationRegister"] = "InformationRegister"
    periodicity: str
    slice_types: list[str]

ObjectCard = Annotated[
    Union[DocumentCard, CatalogCard, InformationRegisterCard, ...],
    Field(discriminator='object_type')
]
```

Преимущества:
- LLM получает чёткий discriminator сигнал через JSON Schema
- Автоматические retry при validation failures (Instructor)
- Pydantic v2 валидирует структуру до сохранения

## 4. Mapping гэпов → ранжированные решения

### Гэп 1: Generic schema → Discriminated Union
**Ранг A** (РЕКОМЕНДОВАНО): Discriminated Union (см. выше)
Альтернативы: Inheritance, ad-hoc routing, JSON Schema anyOf, ничего.

### Гэп 2: Conditional posting_flow
**Ранг A**: Nested step schema с condition field + branches
```python
class PostingStep(BaseModel):
    step_number: int
    description: str
    register: str
    move_type: Literal["debit", "credit", "set", "delete"]
    condition: str | None = None
    branches: list["PostingStep"] = []

class PostingFlow(BaseModel):
    steps: list[PostingStep]
    has_conditional_logic: bool
    main_happy_path: list[int]
```
Альтернативы: DAG, BPMN, псевдокод, LangGraph state machine.

### Гэп 3: ITS mention extraction
**Ранг B (рекомендовано)**: Pre-built ontology + entity linking через zeegin/v8std (317 стандартов уже эмбедятся в нашем M-K2.7).
**Ранг A**: Regex + LLM hybrid (быстрее для старта).

### Гэп 4: Cross-config diff
**Ранг C (старт)**: Хранить все конфиги в одной таблице с config_id, diff = SQL JOIN. **3 строки кода**, работает.
**Ранг A (после)**: Schema-level diff + LLM-объяснение различий.

### Гэп 5: Версионирование
**Ранг A**: `schema_version` поле + Alembic migrations. Дополнительно: `PRAGMA user_version` в SQLite. **Без этого ручная миграция 63k карточек.**

### Гэп 6: Нормативка hooks
**Ранг A**: Промпт с инъекцией релевантных стандартов (RAG из zeegin/v8std).
**Ранг D**: zeegin/v8std эмбедированы → при генерации найти top-k.

### Гэп 7: Hallucination (КРИТИЧНО)
**Ранг A (наш уникальный path)**: **GraphEval-стиль — валидация против существующего графа**
```python
def validate_card_against_graph(card: DocumentCard, graph) -> ValidationResult:
    errors = []
    for step in card.posting_flow:
        if not graph.edge_exists(card.name, step.register, "WRITES_TO"):
            errors.append(f"Hallucinated register: {step.register}")
    for ref in card.related_objects:
        if not graph.node_exists(ref):
            errors.append(f"Non-existent reference: {ref}")
    return ValidationResult(errors=errors)
```
**У нас уже есть граф 2.2M узлов / 4.3M рёбер — это идеальный ground truth!**

### Гэп 8: Роли и RLS
**Ранг A**: RolesSection как nested model в карточке
**Ранг B**: RBAC before retrieval (arxiv 2507.23465) — filter chunks по роли пользователя на retrieval

### Гэп 9: embedding_text (КРИТИЧНО)
**Ранг E (РЕКОМЕНДОВАНО НЕМЕДЛЕННО)**: **Hybrid BM25 + dense** (как Mem0 v3). Имена объектов 1С — proper nouns, для них BM25 работает лучше dense.
**Ранг A (после)**: Multi-representation — отдельный embedding per use-case (search / Q&A / scenarios / code).

### Гэп 10: Form-handlers
**Ранг C**: **Игнорировать — низкий приоритет для аналитика**. Аналитику важны реквизиты и бизнес-логика, не обработчики форм. Откладывай.

### Гэп 11: Hard limits
**Ранг A**: Pydantic field validators. **2 строки на поле**:
```python
class DocumentCard(BaseModel):
    summary: str = Field(max_length=500)
    posting_flow: list[PostingStep] = Field(max_length=20)
    key_attributes: list[str] = Field(max_length=30)
```

## 5. Подводные камни — П1-П8 (отсутствовали в нашем плане v1)

### П1. `frozen=True` dataclass несовместим с эволюцией схемы

**Наша ошибка**: используем `@dataclass(frozen=True, slots=True)` для TypicalObjectCard. При первом добавлении поля → KeyError при десериализации старых записей.

**Решение**: переход на `Pydantic BaseModel` с `model_config = ConfigDict(frozen=True)` — миграция безопаснее через `model_validate(data, strict=False)`.

**Срочность**: MUST до первого изменения схемы (а оно неизбежно).

### П2. SQLite + vec0 не масштабируется на 4+ конфигурации

vec0 (sqlite-vec) на 250k+ векторов начинает деградировать при concurrent reads. Production-порог: **~100k нормально, 500k — нужен отдельный vector store**.

**Наш кейс**: 4 конфига × 63к карточек = **252k векторов** — близко к лимиту. Если добавим ЗУП + УСО + Документооборот = ~400k.

**Решение при росте**:
- pgvector (postgres extension) — если переходим на Postgres
- Qdrant / Milvus как vector store + SQLite как metadata
- ColPali / late chunking для уменьшения количества векторов

**Срочность**: SHOULD при подключении 5+ конфигов или жалобах на performance.

### П3. GraphRAG canonicalization problem

Microsoft GraphRAG прямо документирует: **«open-domain extraction creates hundreds of unique relationship types»**.

**Наша проблема**: 6 типов рёбер нормализованы в графе, **но при LLM-генерации карточек модель может использовать другие слова** для описания связей. Например `"использует"` / `"вызывает"` / `"обращается к"` — для одного USES edge.

**Решение**: canonicalization при generation — принудительно использовать те же термины что в графе. Передавать в промпт **closed vocabulary**: «используй только эти 6 типов связей: CONTAINS, CALLS, USES, WRITES_TO, READS_FROM, REFERENCES».

**Срочность**: MUST при переходе на real LLM.

### П4. Провенанс (source_evidence) отсутствует

**Наша проблема**: если карточка говорит "регистр ТоварыНаСкладах", откуда это — из BSL-кода, из XML метаданных, или придумал LLM?

**Решение**: GraphRAG паттерн — каждый факт хранит `source_id`. Минимальный вариант для нас:
```python
class FactWithEvidence(BaseModel):
    value: str
    evidence_source: Literal["metadata_xml", "bsl_code", "llm_inferred"]
    confidence: float = 1.0
```

Без этого:
- Невозможно debug галлюцинаций
- Невозможно обновить при изменении конфигурации (не знаем какой источник изменился)

**Срочность**: SHOULD при переходе на real LLM.

### П5. Обновление карточек при релизе конфигурации не определено

УТ 11.5.17 → 11.5.18 вышел патч. Какие карточки stale?

**Решение**: хранить `source_config_version` + `metadata_hashes_per_object` (SHA256 от XML+BSL). При обновлении конфы → diff hashes → пометить изменённые как `needs_refresh=True`.

Базовая инфраструктура: поле `source_config_version` уже есть в TypicalObjectCardRecord (через `created_at` + `typical_configurations.config_version`).

**Срочность**: SHOULD до production deployment.

### П6. Mock-карточки в production — катастрофа (КРИТИЧНО, МОЖЕТ СЛОМАТЬСЯ СЕЙЧАС)

**Наша ситуация**: 63k mock-карточек в БД. Если они попадут в production retrieval, LLM будет генерировать ответы на фейковых данных.

**Решение**:
1. Добавить колонку `is_mock` в `typical_object_cards`
2. Все существующие 63k записей пометить `is_mock=True`
3. Любой retrieval фильтрует по `is_mock=False`
4. После real LLM rebuild — флаг переключается на False

**Срочность**: MUST **сегодня** — пока не выкатили chat-интеграцию.

### П7. Embedding model dependency не зафиксирована

Если сейчас text-embedding-3-small, завтра NVIDIA → пересчёт 63k. Решение:
- Колонка `embedding_model` + `embedding_model_version` в индексе
- При изменении модели — explicit full reindex
- Версия в качестве части источника правды

**Срочность**: MUST до первого embedding (мы ещё не эмбедили).

### П8. Cold start при запросе к несуществующему объекту

Аналитик: *«как работает Документ.УстановкаЦен в УТ 11.5?»* — карточки нет (генерировалась только часть). LLM ответит из параметрической памяти = **галлюцинация конкретного конфига**.

**Решение**: explicit fallback:
1. Если карточка не найдена → tool возвращает `"card_status": "not_generated"`
2. LLM-orchestrator получает этот сигнал → говорит пользователю **«я не знаю об этом объекте в данной конфигурации»**
3. Опционально: триггер on-demand generation для часто-спрашиваемых

**Срочность**: MUST до production. **Текущий explain_typical_object уже возвращает card=None для несуществующих** — но frontend / system prompt не обрабатывает этот сигнал явно.

## 6. Уточнённые приоритеты после research

### MUST — сломается в первые часы / дни

| Приоритет | Гэп | Решение | Затраты |
|---|---|---|---|
| 1 | **П6 — Mock isolation** | Колонка `is_mock` + retrieval filter | 30 минут |
| 2 | **Гэп 7 — Graph validation** | `validate_card_against_graph()` (regex check существования объектов) | 2 часа |
| 3 | **Гэп 11 — Pydantic field validators** | `Field(max_length=...)` | 1 час |
| 4 | **Гэп 1 — Discriminated Union** | Минимум 4 специализации (Document / Catalog / Register / Generic) | 4-6 часов |
| 5 | **Гэп 9 — Hybrid BM25 + dense** | До embedding! Имена объектов 1С работают на BM25 лучше | 3-4 часа |
| 6 | **П1 — Pydantic BaseModel(frozen=True)** | Замена @dataclass(frozen) → BaseModel | 2 часа |
| 7 | **П7 — Embedding model versioning** | Колонка в индексе | 30 минут |
| 8 | **П3 — Closed vocabulary при generation** | Список из 6 EdgeKind в промпте | 1 час |
| 9 | **П8 — Cold start fallback** | Explicit message от LLM при card=None | 1 час |

### SHOULD — сломается через недели

| Приоритет | Гэп | Решение | Затраты |
|---|---|---|---|
| 10 | **Гэп 5 — schema_version + Alembic** | Без этого ручная миграция | 3-4 часа |
| 11 | **Гэп 4 — Cross-config diff** | config_id в таблице (уже есть!) + SQL JOIN | 2 часа |
| 12 | **Гэп 6 — ITS hooks** | RAG из zeegin/v8std при генерации | 4 часа |
| 13 | **П2 — vector store масштабирование** | Только при росте до 5+ конфигов | по необходимости |
| 14 | **П4 — Provenance evidence_source** | Минимальный variant | 2 часа |
| 15 | **П5 — Update механизм** | hashes + needs_refresh | 4 часа |

### COULD — nice to have

| Приоритет | Гэп | Решение |
|---|---|---|
| 16 | Гэп 2 — Conditional posting_flow | LLM может галлюцинировать условия |
| 17 | Гэп 3 — ITS mention auto-extraction | Дублирует Гэп 6 |
| 18 | Гэп 8 — Roles / RLS | Сложно, лучше в M-K3 |
| 19 | Гэп 10 — Form-handlers | Аналитику не нужно |

## 7. Что мы можем УПУСТИТЬ

Из research чётко следует: **карточки `frozen dataclass` без validation = техдолг 2-го уровня сложности**. Если выкатим в production сейчас:

- **Мгновенный риск**: пользователи будут видеть ответы с выдуманными именами регистров (mock-карточки)
- **Через 2-3 дня**: первый запрос к несуществующей карточке → LLM выдаст галлюцинацию из параметрической памяти, не из RAG
- **Через 1-2 недели**: первое изменение схемы → ручная миграция 63k записей или потеря данных
- **Через 1 месяц**: запросы по именам регистров (substring match) дают плохой recall, пользователи уходят

## 8. Применение к плану

Этот research **существенно меняет приоритеты** в CARDS-V2-PLAN.md:
- v2.A (специализации) остаётся **первой фазой**, но дополняется П1 (Pydantic BaseModel)
- **Новая v2.0 (CRITICAL preventive)** перед всем остальным:
  - П6 mock isolation
  - Гэп 7 graph validation
  - Гэп 11 hard limits
  - П3 closed vocabulary
  - П8 cold start
- v2.B (conditional posting_flow) — **понижается в приоритете** (LLM может галлюцинировать условия)
- v2.D (cross-config) — **повышается** (3 строки SQL даёт уже большую ценность)

CARDS-V2-PLAN.md обновлён в этом же коммите.

## 9. Источники (топ-15 из 60+)

- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — 33.2k ⭐
- [BSL Atlas MCP](https://www.pulsemcp.com/servers/arman-kudaibergenov-bsl-atlas) — 55 ⭐
- [BSL Graph (alkoleft)](https://github.com/alkoleft/bsl-graph) — 43 ⭐
- [Cognition DeepWiki](https://cognition.ai/blog/deepwiki)
- [Sourcegraph Code Graph](https://sourcegraph.com/docs/cody/core-concepts/code-graph)
- [Mem0](https://github.com/mem0ai/mem0) — 23k+ ⭐
- [Instructor Union Types](https://python.useinstructor.com/concepts/unions/)
- [Pydantic v2 Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/)
- [DeepEval RAG metrics](https://www.confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more)
- [GraphEval (arxiv 2407.10793)](https://arxiv.org/pdf/2407.10793)
- [Knowledge Card paper (arxiv 2305.09955)](https://arxiv.org/pdf/2305.09955)
- [Cleanlab TLM hallucination benchmarking](https://cleanlab.ai/blog/rag-tlm-hallucination-benchmarking/)
- [FalkorDB Code Graph](https://www.falkordb.com/blog/code-graph/)
- [comol/ai_rules_1c](https://github.com/comol/ai_rules_1c)
- [Role-Aware LLMs (arxiv 2507.23465)](https://arxiv.org/abs/2507.23465)
