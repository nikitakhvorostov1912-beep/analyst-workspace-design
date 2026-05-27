---
plan: "Object Cards v2 — production-готовые карточки"
status: draft (revised after research 2026-05-27)
author: "Claude Opus 4.7 + Khvorostov"
date: "2026-05-26, revised 2026-05-27"
target_phase: "M-K2.5.9 (extension after closing)"
estimated_effort: "6-8 интенсивных сессий (включая preventive v2.0)"
prerequisites: ["M-K2.5 closed (8 фаз)", "Real LLM adapter"]
research_source: "CARDS-V2-RESEARCH.md (60+ источников)"
---

# ⚠ Революция после research 2026-05-27

Глубокий research (deep-researcher, 60+ источников, см.
`CARDS-V2-RESEARCH.md`) **существенно изменил приоритеты** этого плана.
Главное:

1. **Добавлена preventive-фаза v2.0 (КРИТИЧНО)** — закрывает 9 рисков
   которые сломают production в первые дни. До неё нельзя выкатывать
   chat-интеграцию.
2. **Гэп 9 (hybrid BM25 + dense) повышен в MUST** — Mem0 v3 показал что
   substring/dense без BM25 не работает для proper nouns типа имён 1С-объектов.
3. **Найден GraphEval-подход** — наша уникальная возможность валидировать
   карточки против существующего графа 2.2M узлов как ground truth.
4. **Открыты 8 подводных камней (П1-П8)** которых не было в плане:
   frozen dataclass, vec0 scale, canonicalization, provenance, update
   mechanism, mock isolation, embedding model versioning, cold start.

Подробности — `CARDS-V2-RESEARCH.md`.

# Cards v2 — план production-карточек

> Текущая схема v1 = MVP, годная для smoke. Под реальные сложные
> запросы бизнес-аналитика **не годится** — гэпы перечислены ниже.
> Этот план описывает что нужно доделать, в каком порядке, как
> валидировать качество и какие проблемы решить заранее.

## 1. Проблемы текущей схемы v1

### 1.1 Одна схема на 30+ типов объектов
Документ ≠ Справочник ≠ Регистр ≠ ПланСчетов ≠ Регл.задание ≠ Отчёт ≠ Подсистема. Каждый имеет уникальную семантику. Сейчас одна `TypicalObjectCard` для всех — generic-шаблон не передаёт специфику.

### 1.2 Линейный posting_flow без условной логики
Документ Реализация в БП ведёт себя по-разному в зависимости от:
- Учётной политики (НДС / РСБУ / МСФО)
- Валюты договора (рубли / валюта → курсовая разница)
- Режима проведения (оперативный / неоперативный → блокировки)
- Наличия УТ-интеграции (свободные остатки + резервы)

В карточке v1 нельзя выразить «при условии X — делаем Y, иначе Z».

### 1.3 ИТС-стандарты не привязаны
`its_links: []` всегда. Бот не свяжет карточку с ИТС std396/pattern-* — отдельная фаза сопоставления не сделана.

### 1.4 Cross-config differences
`Документ.РеализацияТоваровУслуг` в УТ и ERP отличается по семантике и реквизитам. Карточка не моделирует «существует в X, нет в Y, в Z отличается так-то».

### 1.5 Версионная эволюция
УТ 11.5.17 → 11.5.18 — добавляются реквизиты, меняется логика проведения. Карточка не носит meta «introduced_in», «modified_in». Diff между версиями невозможен.

### 1.6 Нормативка (НК РФ, учётная политика)
Документ Реализация = ст.146/154/164 НК РФ. Карточка не содержит legal_basis / tax_treatment. Это M-K4 territory, но карточка к нему не готова (нет hook-полей).

### 1.7 LLM hallucination не отлавливается
Real LLM может выдать «пишет в РегистрНакопления.X», а в графе WRITES_TO к этому регистру нет. Cross-check vs реального графа = LLM-judge — не реализован.

### 1.8 Роли и RLS
Документ может быть видим только определённым ролям. Карточка не носит roles_can_read / roles_can_write. Вопрос «кто может проводить» — без ответа.

### 1.9 Подсистемы / иерархия
Документ в подсистеме «Продажи». Карточка не знает к какой подсистеме принадлежит. «Покажи все документы подсистемы Закупки» — невозможно через карточку.

### 1.10 embedding_text неполный
Эмбедится только `summary + purpose + posting_flow[:3]`. Не эмбедятся `key_attributes`, `related_objects`, `typical_scenarios`. Semantic search потеряет половину релевантности.

### 1.11 Form-handlers вне карточки
После audit-fix формовые модули попали в граф, но **карточка не упоминает форменные обработчики**. «Какие обработчики у формы ФормаДокумента» — только через `trace_calls`, не через карточку.

### 1.12 Pagination / размер не лимитированы
Real LLM может выдать posting_flow на 20 шагов, related_objects на 50 элементов. Хард-лимитов нет, в UI рендер целиком.

---

## 2. Целевая архитектура v2

### 2.1 Discriminated union карточек по типу

Базовый класс `TypicalObjectCardBase` + 9 специализаций:

| Класс | Объекты | Специфические поля |
|---|---|---|
| `DocumentCard` | Document | `posting_flow_branches`, `movement_groups`, `print_forms`, `journal_membership` |
| `CatalogCard` | Catalog | `hierarchy`, `predefined_items`, `selection_form`, `owner_catalogs` |
| `RegisterCard` | AccumulationRegister / InformationRegister / AccountingRegister / CalculationRegister | `dimensions`, `resources`, `attributes`, `virtual_tables`, `periodicity`, `aggregation_mode` |
| `ChartOfAccountsCard` | ChartOfAccounts | `account_types`, `subconto_types`, `extra_dimensions` |
| `EnumCard` | Enum | `values_with_synonyms`, `usage_locations` |
| `ReportCard` | Report | `scd_variants`, `parameters`, `field_groups`, `data_sources` |
| `DataProcessorCard` | DataProcessor | `purpose_category`, `cli_args`, `triggered_by` |
| `ScheduledJobCard` | ScheduledJob | `schedule_cron`, `triggered_handler`, `use_external_lock` |
| `SubscriptionCard` | EventSubscription | `subscribed_events`, `handler_module`, `priority` |
| `RoleCard` | Role | `rls_predicates`, `accessible_subsystems`, `restrictions_summary` |
| `SubsystemCard` | Subsystem | `subordinate_objects`, `commands`, `interface_purpose` |
| `GenericCard` | Constant, Sequence, fallback | плоская v1 |

### 2.2 Условная логика в posting_flow

```yaml
posting_flow:
  - step: "Проверка остатков"
    condition: null  # всегда
  - step: "Резервирование товаров"
    condition:
      type: "policy_check"
      param: "УчётнаяПолитика.ИспользоватьРезервы"
      value: true
  - step: "Расчёт курсовой разницы"
    condition:
      type: "field_check"
      field: "Договор.ВалютаВзаиморасчётов"
      operator: "not_equal"
      value: "Договор.Организация.ВалютаРегламентированногоУчёта"
```

### 2.3 ИТС / БСП mention extraction

Отдельная фаза после генерации карточки:
1. Для каждой карточки берём `summary + purpose + posting_flow`
2. Вызываем `search_its(query, top_k=3)` через существующий M-K2.7 RAG
3. Топ-3 ИТС-чанка с similarity ≥ 0.65 → записываем в `its_links`
4. То же для `search_bsp` (M-K2.8) → `bsp_links`

### 2.4 Cross-config map

Отдельная таблица `typical_cross_config_map`:

```sql
CREATE TABLE typical_cross_config_map (
  short_qname TEXT NOT NULL,            -- "Document.РеализацияТоваровУслуг"
  channel_id TEXT NOT NULL,
  card_id INTEGER REFERENCES typical_object_cards(id),
  attributes_count INTEGER,
  has_card BOOLEAN,
  semantic_signature TEXT,              -- hash of key_attributes + movements
  UNIQUE(short_qname, channel_id)
);
```

Позволяет за O(1) ответить «существует ли РеализацияТоваровУслуг в БП» и «отличается ли от УТ по signature».

### 2.5 Версионная meta

Поля в карточке:
- `introduced_in_version` — первая версия конфигурации где появился (определяется по diff с предыдущей)
- `last_modified_in_version`
- `breaking_changes_since` — массив `{version, change_summary}`

Заполняется отдельной фазой "Version archeology" — анализ diff между snapshot'ами разных версий типовой.

### 2.6 Нормативка hooks (M-K4 ready)

```yaml
legal_basis:
  - law: "НК РФ"
    article: "146"
    paragraph: "1"
    relevance: "облагаемые операции"
  - law: "НК РФ"
    article: "164"
tax_treatment:
  vat: "20% по умолчанию; 10% / 0% по условиям"
  income_tax: "доход признаётся в момент проведения"
accounting_method:
  bu: "Дт62 Кт90.01.1"
  un: "Не отражается"
```

Заполняется в M-K4 через сопоставление с нормативкой; здесь мы готовим `schema slot`.

### 2.7 LLM-judge cross-check

Новая фаза `validate_card` после генерации:
1. Берём `card.movements` — список регистров в которые «пишет»
2. Проверяем через граф: есть ли реальные WRITES_TO edges от method-узлов объекта к этим регистрам
3. Если есть movement без подтверждения в графе → mark `hallucinated`
4. Аналогично для `related_objects` (должны быть REFERENCES / USES edges)
5. Storage: новое поле `validation_status` (passed / partial / failed) + `validation_notes`

### 2.8 Роли и RLS интеграция

Поля карточки:
- `roles_can_read: list[str]` — извлекается из Rights.xml через ролевой граф
- `roles_can_write`, `roles_can_post`
- `rls_summary` — короткое описание RLS-условий, если есть

Требует отдельной фазы парсинга `Roles/*/Ext/Rights.xml`.

### 2.9 Подсистемы

Поле `subsystems: list[str]` — заполняется из Subsystem.xml ChildObjects.

### 2.10 embedding_text v2

```python
@property
def embedding_text(self) -> str:
    parts = [
        self.summary,
        self.purpose,
        " · ".join(a.name for a in self.key_attributes[:10]),
        " → ".join(self.posting_flow[:5]),
        " · ".join(self.typical_scenarios[:3]),
        " · ".join(self.related_objects[:5]),
    ]
    return "\n\n".join(p for p in parts if p)
```

И отдельный `embedding_text_short` для KIN-поиска по названиям.

### 2.11 Form-handlers в карточке Document/Catalog

```yaml
form_handlers:
  - form: "ФормаДокумента"
    handlers:
      - "ПриСозданииНаСервере"
      - "ПередЗаписьюНаСервере"
      - "ПриИзмененииКонтрагента (поле события)"
  - form: "ФормаСписка"
    handlers: [...]
```

Извлекается из графа (Module nodes с module_kind=FormModule + Method nodes).

### 2.12 Hard limits в схеме

| Поле | Лимит | Поведение при превышении |
|---|---|---|
| `summary` | 250 символов | LLM-instruct truncate |
| `purpose` | 400 символов | LLM-instruct truncate |
| `key_attributes` | 8 элементов | LLM выбирает top-priority |
| `movements` | 15 элементов | LLM выбирает top-priority |
| `posting_flow` | 8 шагов | LLM группирует |
| `typical_scenarios` | 5 | LLM выбирает |
| `preconditions` | 6 | LLM выбирает |
| `related_objects` | 10 | LLM выбирает по graph degree |
| `its_links` | 5 | top-k по similarity |

Лимиты в prompt + validation в parser.

---

## 3. Фазы реализации

### Phase v2.0 — CRITICAL Preventive (полный вариант B, ~6-8 часов)

**Цель:** Закрыть 9 критичных рисков ДО запуска chat-интеграции.
Без этого первые пользователи получат галлюцинации, фейковые имена
регистров, и потерянные данные при первой миграции.

**Принцип последовательности**: 9 пунктов делаются строго по порядку.
П1 (Pydantic) → П6 (mock isolation) → Гэп 11 (limits) → П3 (closed
vocab) → Гэп 7 (graph validation) → П7 (embedding versioning) → П8
(cold start) → smoke. После каждого пункта — atomic commit + узкий
регресс. Если на любом этапе ломается — STOP, не идём дальше.

---

#### 🔴 v2.0-step-1 — П1 Pydantic BaseModel (40 мин)

**Что**: миграция `TypicalObjectCard` с `@dataclass(frozen=True, slots=True)` → `BaseModel(model_config=ConfigDict(frozen=True))`.

**Файлы**:
- `backend/app/knowledge/typical/card_models.py` — изменить `TypicalObjectCard`, `CardAttribute`, `CardMovement` на Pydantic BaseModel. Сохранить тот же API (`to_dict`, `to_payload_json`, `from_payload_json`, property `embedding_text`).
- `backend/app/knowledge/typical/card_storage.py` — обновить сериализацию (если используется `dataclasses.asdict`).
- `backend/app/knowledge/typical/card_generator.py` — обновить `_payload_to_card` для возврата BaseModel.
- `backend/tests/test_typical_card_storage.py` + `test_typical_card_generator.py` — поправить тесты на `frozen` exception (Pydantic ValidationError вместо FrozenInstanceError).

**Acceptance**:
- [ ] Все 31 теста `test_typical_card_storage.py` зелёные
- [ ] Все 25 тестов `test_typical_card_generator.py` зелёные
- [ ] `roundtrip` тест: existing JSON из БД (63k карточек) парсится в новую BaseModel идентично
- [ ] frozen=True работает (попытка mutation → ValidationError)

**Риски**:
- `from_payload_json` использует `**dict` — у Pydantic нужен `model_validate(dict)` или `model_validate_json(str)`. Проверить что unknown fields игнорируются (`extra='ignore'`)
- Property `embedding_text` нужно объявить через `@computed_field` или просто `@property`

**Commit**: `refactor(M-K2.5.9.1): TypicalObjectCard → Pydantic BaseModel(frozen=True)`

---

#### 🔴 v2.0-step-2 — П6 Mock isolation (30 мин)

**Что**: пометить все 63k существующих карточек как mock, фильтровать в retrieval.

**Файлы**:
- `backend/app/storage/migrations.py` — Migration v19:
  ```sql
  ALTER TABLE typical_object_cards ADD COLUMN is_mock INTEGER NOT NULL DEFAULT 0;
  UPDATE typical_object_cards SET is_mock = 1 WHERE llm_model = 'mock-generator-v1';
  CREATE INDEX idx_typical_cards_is_mock ON typical_object_cards(is_mock);
  ```
- `backend/app/knowledge/typical/card_models.py` — добавить поле `is_mock: bool = False` в `TypicalObjectCardRecord`
- `backend/app/knowledge/typical/card_storage.py`:
  - `upsert_card` принимает `is_mock: bool = False`
  - `_row_to_record` читает is_mock
  - `list_cards_by_channel` принимает `exclude_mock: bool = False`
- `backend/app/knowledge/typical/tool.py` — `_handle_explain` + `_handle_search_objects` добавляют в payload `"is_mock": True/False` (warning сигнал для UI и LLM)
- `frontend/components/cards/TypicalObjectCard.tsx` — бейдж "Mock data — не верифицировано экспертом" когда `is_mock=True`

**Acceptance**:
- [ ] Migration v19 применяется на свежей БД и на текущей `pilot.db`
- [ ] `SELECT COUNT(*) FROM typical_object_cards WHERE is_mock=1` = 63 197
- [ ] `_handle_explain` для mock-карточки возвращает `card.is_mock=True`
- [ ] Frontend бейдж видим (vitest проверка)
- [ ] 3 новых unit-теста (mock filter / non-mock filter / mixed)

**Commit**: `feat(M-K2.5.9.2): is_mock flag + UI warning для mock-карточек`

---

#### 🔴 v2.0-step-3 — Гэп 11 Hard limits через Pydantic Field() (45 мин)

**Что**: жёсткие лимиты для всех полей карточки, чтобы LLM не раздувал.

**Файлы**:
- `backend/app/knowledge/typical/card_models.py`:
  ```python
  class TypicalObjectCard(BaseModel):
      summary: str = Field(default="", max_length=400)
      purpose: str = Field(default="", max_length=600)
      key_attributes: tuple[CardAttribute, ...] = Field(default_factory=tuple, max_length=10)
      movements: tuple[CardMovement, ...] = Field(default_factory=tuple, max_length=15)
      posting_flow: tuple[str, ...] = Field(default_factory=tuple, max_length=8)
      typical_scenarios: tuple[str, ...] = Field(default_factory=tuple, max_length=5)
      preconditions: tuple[str, ...] = Field(default_factory=tuple, max_length=6)
      related_objects: tuple[str, ...] = Field(default_factory=tuple, max_length=10)
      its_links: tuple[str, ...] = Field(default_factory=tuple, max_length=5)
  ```
- `backend/app/prompts/typical_card_generator.md` — указать лимиты в промпте явно: «summary ≤ 400 chars, max 8 шагов posting_flow, max 10 связанных объектов»
- `backend/app/knowledge/typical/card_generator.py`:
  - В `_payload_to_card` — при overlimit обрезать (defensive) и логировать warning
  - Storage: новое поле `truncation_warnings: list[str]` (опционально)

**Acceptance**:
- [ ] Pydantic отклоняет карточки с summary > 400 chars (ValidationError)
- [ ] LLM-output с лишними posting_flow steps обрезается до 8
- [ ] Тесты: 5 проверок на overlimit для каждого list-поля
- [ ] Mock LLM проходит лимиты

**Commit**: `feat(M-K2.5.9.3): hard limits через Pydantic Field max_length`

---

#### 🔴 v2.0-step-4 — П3 Closed vocabulary в LLM prompt (45 мин)

**Что**: LLM использует только зафиксированный словарь типов связей и направлений, иначе fragmentation графа.

**Файлы**:
- `backend/app/prompts/typical_card_generator.md` — расширить:
  ```
  ## Закрытый словарь

  ### `movements[].direction` — только эти значения:
  - "приход" — увеличение
  - "расход" — уменьшение
  - "приход/расход" — зависит от условия
  - "запись" — для регистров сведений без направления

  ### `movements[].register` — формат:
  Полное имя в виде `Kind.Name`, где Kind ∈
  {AccumulationRegister, InformationRegister, AccountingRegister, CalculationRegister}.

  ### `related_objects[]` — формат:
  Полное имя `Kind.Name` где Kind ∈
  {Document, Catalog, Enum, ChartOfAccounts, AccumulationRegister, ...}.

  ❌ НЕ использовать:
  - "использует" / "вызывает" / "обращается к" — это не поля карточки
  - Транслитерации латиницей русских слов
  - Сокращения (РН вместо AccumulationRegister)
  ```
- `backend/app/knowledge/typical/card_models.py`:
  ```python
  MovementDirection = Literal["приход", "расход", "приход/расход", "запись"]

  class CardMovement(BaseModel):
      register: str
      direction: MovementDirection = "запись"
      condition: str = ""
  ```
- `backend/app/knowledge/typical/card_generator.py` — `_payload_to_card` нормализует value (lowercase + trim) перед валидацией; если direction не в Literal — fallback на "запись" с warning

**Acceptance**:
- [ ] Pydantic отклоняет неизвестные direction values
- [ ] Mock LLM использует только closed vocab
- [ ] Prompt template содержит явный список значений
- [ ] 3 теста: valid direction / invalid → fallback / lowercase normalize

**Commit**: `feat(M-K2.5.9.4): closed vocabulary для movements direction + register format`

---

#### 🔴 v2.0-step-5 — Гэп 7 Graph validation (GraphEval) (2 часа)

**Что**: cross-check карточки против существующего графа 2.2M узлов.

**Файлы**:
- Новый `backend/app/knowledge/typical/card_validator.py`:
  ```python
  @dataclass(frozen=True, slots=True)
  class ValidationIssue:
      severity: Literal["error", "warning"]
      field: str
      value: str
      message: str

  @dataclass(frozen=True, slots=True)
  class ValidationResult:
      status: Literal["passed", "partial", "failed"]
      issues: tuple[ValidationIssue, ...]
      checked_at: str  # ISO

  async def validate_card_against_graph(
      db: aiosqlite.Connection,
      *,
      channel_id: str,
      card: TypicalObjectCard,
  ) -> ValidationResult:
      """Сравнивает упоминания в карточке с реальностью графа."""
      issues: list[ValidationIssue] = []

      # 1. Movements: каждый register должен существовать как MetadataObject
      for m in card.movements:
          # Нормализуем имя (русский → английский kind prefix)
          normalized = _normalize_query_table_qname(m.register)
          if normalized is None:
              issues.append(ValidationIssue("error", "movements.register",
                  m.register, f"Не распознан формат: {m.register}"))
              continue
          node = await find_node(db, channel_id=channel_id,
              qualified_name=normalized, node_kind=NodeKind.METADATA_OBJECT.value)
          if node is None:
              issues.append(ValidationIssue("error", "movements.register",
                  m.register, f"Регистр {normalized} не существует в графе"))

      # 2. Related objects: каждый должен существовать
      for ref in card.related_objects:
          normalized = _normalize_query_table_qname(ref) or ref
          node = await find_node(db, channel_id=channel_id,
              qualified_name=normalized, node_kind=NodeKind.METADATA_OBJECT.value)
          if node is None:
              issues.append(ValidationIssue("warning", "related_objects",
                  ref, f"Объект {ref} не найден в графе"))

      # 3. Key attributes: должны соответствовать Attribute-узлам объекта
      obj_qname = card.object_qualified_name
      for attr in card.key_attributes:
          attr_qname = f"{obj_qname}.Реквизит.{attr.name}"
          node = await find_node(db, channel_id=channel_id,
              qualified_name=attr_qname, node_kind=NodeKind.ATTRIBUTE.value)
          if node is None:
              # Может быть реквизит ТЧ — проверим через LIKE
              cursor = await db.execute(
                  "SELECT 1 FROM graph_nodes WHERE channel_id=? AND qualified_name LIKE ? LIMIT 1",
                  (channel_id, f"{obj_qname}.%.Реквизит.{attr.name}")
              )
              found = await cursor.fetchone()
              if not found:
                  issues.append(ValidationIssue("warning", "key_attributes",
                      attr.name, f"Реквизит {attr.name} не найден у объекта"))

      errors = [i for i in issues if i.severity == "error"]
      status = "failed" if errors else ("partial" if issues else "passed")
      return ValidationResult(
          status=status, issues=tuple(issues),
          checked_at=datetime.utcnow().isoformat(),
      )
  ```
- Migration v20:
  ```sql
  ALTER TABLE typical_object_cards ADD COLUMN validation_status TEXT;
  ALTER TABLE typical_object_cards ADD COLUMN validation_issues TEXT;  -- JSON
  ALTER TABLE typical_object_cards ADD COLUMN validated_at TIMESTAMP;
  ```
- `backend/app/knowledge/typical/card_storage.py` — `upsert_card` + `update_card_validation(card_id, result)`
- `backend/app/knowledge/typical/tool.py` — `_handle_explain` возвращает `validation_status` + первые 3 issues в payload (LLM решает показывать warning или нет)
- `backend/tests/test_typical_card_validator.py` — 15 тестов (synthetic граф + карточка с/без ошибок)

**Acceptance**:
- [ ] 95% real-generated карточек проходят validation (на synthetic данных)
- [ ] LLM-карточка с выдуманным регистром получает `validation_status=failed`
- [ ] LLM-карточка с реальным регистром → `passed`
- [ ] explain возвращает validation в payload
- [ ] 15 unit-тестов зелёные

**Commit**: `feat(M-K2.5.9.5): card validator против реального графа (GraphEval)`

---

#### 🔴 v2.0-step-6 — П7 Embedding model versioning (40 мин)

**Что**: фиксировать какой embedding model использовался для каждой карточки.

**Файлы**:
- `backend/app/knowledge/typical/card_models.py`:
  - Поле `embedding_model: str | None` (уже есть в TypicalObjectCardRecord)
  - Новое поле `embedding_model_version: str | None` (e.g. "text-embedding-3-small-v1" / "nvidia-embed-v2")
- Migration v21:
  ```sql
  ALTER TABLE typical_object_cards ADD COLUMN embedding_model_version TEXT;
  ```
- `backend/app/knowledge/typical/card_storage.py` — `update_card_status` принимает `embedding_model_version`
- Новый `backend/scripts/typical_cards_reembed.py` — explicit reindex с подтверждением:
  ```bash
  python -m scripts.typical_cards_reembed --channel _bp30_138_24 \
      --new-model text-embedding-3-large --confirm
  ```
- Unit tests: 5 проверок на embedding model tracking

**Acceptance**:
- [ ] Поле `embedding_model_version` в схеме
- [ ] Reembed script отказывается работать без `--confirm`
- [ ] Smoke: создать карточку с model A → сменить на B → старая запись не перезаписана автоматически

**Commit**: `feat(M-K2.5.9.6): embedding model versioning + explicit reembed`

---

#### 🔴 v2.0-step-7 — П8 Cold start fallback (1 час)

**Что**: при запросе к несуществующей карточке — явный сигнал LLM, без галлюцинаций.

**Файлы**:
- `backend/app/orchestrator/loop.py` — обновить system prompt раздел про typical tools:
  ```
  ВАЖНО: если explain_typical_object вернул card=null или card_status='not_generated' —
  НЕ галлюцинируй про этот объект, отвечай явно «об этом объекте в данной конфигурации
  у меня информации нет». Аналогично для search_typical_objects total=0 —
  не выдумывай объекты, скажи «ничего не нашлось по запросу X в типовой Y».
  ```
- `backend/app/knowledge/typical/tool.py` — `_handle_explain` для отсутствующего объекта возвращает структурированный ответ:
  ```python
  return True, {
      "qualified_name": qname,
      "channel_id": channel_id,
      "card_status": "not_in_graph",
      "available_objects_hint": "...",  # топ-5 похожих имён из search
      "message": "Объект не найден в графе типовой. Возможно, имя написано иначе.",
  }, None
  ```
- `frontend/components/cards/TypicalObjectCard.tsx` — новый state `not_found` с подсказкой
- 5 smoke-тестов на cold start (несуществующий object / channel / выдуманный kind)

**Acceptance**:
- [ ] LLM не галлюцинирует при card=None в smoke сценариях
- [ ] System prompt содержит явную инструкцию
- [ ] UI компонент для not_found state
- [ ] 5 cold-start тестов зелёные

**Commit**: `feat(M-K2.5.9.7): cold start fallback без LLM-галлюцинаций`

---

#### 🟡 v2.0-step-8 — Smoke + регресс + closing (1 час)

**Что**: финальная проверка что все 7 шагов вместе работают.

**Действия**:
1. Прогнать `python -m scripts.typical_smoke_questions` (55/55 должны остаться зелёными + проверить новые поля validation_status / is_mock в Q3 / Q4)
2. Расширить smoke новыми 10 проверками:
   - Mock filter работает (Q11)
   - Graph validation flags fake card (Q12)
   - Closed vocab отклоняет неизвестный direction (Q13)
   - Hard limit отклоняет overlong summary (Q14)
   - Cold start не галлюцинирует (Q15-17)
   - Embedding versioning заметен в payload (Q18-19)
   - Pydantic frozen работает (Q20)
3. Регрессия typical/*: `python -m pytest tests/test_typical_*.py --no-cov -q` — все 347+ должны быть зелёные
4. Регрессия polных backend tests: `python -m pytest tests/ --no-cov -q -k "not slow" --timeout=120` — все должны быть зелёные (или зафиксировать что было сломано)
5. Vitest frontend: `npx vitest run` — все зелёные
6. Обновить `STATE.md` и `SUMMARY.md` с пометкой «v2.0 closed»
7. Закрывающий commit + push

**Acceptance criteria v2.0 финально**:
- [ ] Все 7 шагов закоммичены атомарно
- [ ] Mock карточки помечены и фильтруются
- [ ] Graph validation работает на 95%+ карточек
- [ ] Pydantic field validators отклоняют overlimit
- [ ] TypicalObjectCard — BaseModel(frozen=True)
- [ ] Closed vocabulary применён в prompt + Literal types
- [ ] Embedding model versioning в схеме
- [ ] Cold start fallback без галлюцинаций
- [ ] Все 347+ typical/* tests зелёные
- [ ] Smoke 75+ проверок зелёные (старые 55 + 20+ новых)
- [ ] Полный backend pytest хотя бы стартовал без import errors

**Commit**: `closing(M-K2.5.9): Phase v2.0 critical preventive complete`

---

### Сводная таблица v2.0

| # | Шаг | Время | Критичность | Файлов |
|---|---|---:|---|---:|
| 1 | П1 Pydantic BaseModel | 40 мин | блокирующий | 4 |
| 2 | П6 Mock isolation | 30 мин | КРИТИЧНО | 5 |
| 3 | Гэп 11 Hard limits | 45 мин | важно | 3 |
| 4 | П3 Closed vocabulary | 45 мин | важно | 3 |
| 5 | Гэп 7 Graph validation | 2 часа | КРИТИЧНО | 5 |
| 6 | П7 Embedding versioning | 40 мин | important | 4 |
| 7 | П8 Cold start fallback | 1 час | КРИТИЧНО | 4 |
| 8 | Smoke + closing | 1 час | финал | 3 |
| **Итого** | | **~7-8 часов** | | **~30 файлов** |

### Что НЕ в v2.0 (явно отложено)

- v2.A specializations (DocumentCard / CatalogCard / RegisterCard etc.) — отдельная сессия
- v2.C ИТС/БСП mention extraction — нужен real LLM
- v2.D Cross-config diff — 3 строки SQL но требует typical_cross_config_map
- v2.E Roles / RLS / Subsystems / Form-handlers — отдельная сессия
- v2.F Version archeology — нужны 2+ snapshot'а
- v2.G LLM-judge (через 2-й LLM call) — заменён на Гэп 7 (graph validation, наш path)
- v2.H Embedding + hybrid search — нужен real LLM

### Phase v2.A — Schema specializations (одна сессия, ~4-6 часов)

**Цель:** Discriminated union для 9 типов карточек (Pydantic v2 + Instructor паттерн).

**Reference:** [Instructor Union Types](https://python.useinstructor.com/concepts/unions/), [Pydantic v2 Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/), comol/ai_rules_1c как ground truth для типо-специфичных полей.

**Артефакты:**
- `card_models_v2.py` — Pydantic v2 schemas
- Migration v19 — добавить колонку `card_schema_version` в `typical_object_cards`
- `card_storage` v2 — handle новые поля + backward compat (старые v1 карточки читаются через GenericCard)
- 50+ unit-тестов на новые модели

**Acceptance:**
- Pydantic schema валидирует каждый из 9 типов
- Backward compat: старые v1 карточки в БД продолжают читаться
- 100% покрытие тестами

**Риски:**
- Pydantic v2 + frozen dataclasses несовместимы напрямую — переход на BaseModel(frozen=True)
- Schema migration для существующих 63k карточек — нужен скрипт-конвертер

### Phase v2.B — Conditional posting_flow (~3 часа)

**Цель:** Условная логика в шагах проведения.

**Артефакты:**
- `ConditionalStep` model: `{step: str, condition: Optional[ConditionExpr]}`
- `ConditionExpr` discriminated union: `PolicyCheck` / `FieldCheck` / `OptionCheck` / `Always`
- Promt v2 (markdown шаблон с примером условной логики)
- Mock LLM возвращает примеры с условиями для документов

**Acceptance:**
- ≥10% документов имеют conditional шаги (определяется ходом проведения)
- Условия парсятся в structured form (не free-text)
- UI render с раскрытием «если X — то Y»

**Риски:**
- LLM может галлюцинировать условия — нужен LLM-judge (Phase v2.G)

### Phase v2.C — ИТС/БСП mention extraction (~4 часа)

**Цель:** Привязать карточки к существующему RAG (M-K2.7 ИТС, M-K2.8 БСП).

**Артефакты:**
- `card_mentions.py` — `enrich_card_with_links(card)`:
  1. `search_its(card.embedding_text, top_k=3)` → фильтр similarity ≥ 0.65
  2. `search_bsp(...)` аналогично
- New поля карточки: `its_links: list[ITSLink]`, `bsp_links: list[BSPLink]`
- Tests: mock ИТС/БСП search возвращает фиксированные chunks → проверка filter

**Acceptance:**
- Карточка `РеализацияТоваровУслуг` получает ≥2 ИТС-ссылки (std396 + pattern-*)
- 90% карточек документов имеют ≥1 БСП-ссылку (через ОбщегоНазначения / РаботаСФайлами / etc)
- Precision ≥ 0.8 (manual review 50 sample карточек)

**Риски:**
- ИТС/БСП embedding должны быть совместимы по dim/модели с карточками — verify
- Похожий вопрос: cardinality — у популярных терминов («регистр накопления») много false positives

### Phase v2.D — Cross-config map (~3 часа)

**Цель:** Compare-поиск между конфигурациями.

**Артефакты:**
- Migration v20: таблица `typical_cross_config_map`
- `populate_cross_config_map()` — после загрузки всех типовых сравнивает по `short_qname` (без kind prefix)
- LLM tool `find_in_other_configs(qname)` — возвращает где ещё есть этот объект и diff signature

**Acceptance:**
- Для `Document.РеализацияТоваровУслуг` map содержит {УТ, БП, КА, ERP}
- Semantic signature `key_attributes + movements` показывает diff (БП имеет НДС-движения, УТ — товарные)
- Tool возвращает diff за <1 сек

**Риски:**
- Имена могут отличаться (Документ.РеализацияТоваровУслуг vs Document.SalesOfGoods для EN-локали)
- Нормализация EN/RU names

### Phase v2.E — Roles + Subsystems + Form-handlers (~5 часов)

**Цель:** Добить остальные context-поля.

**Артефакты:**
- `Roles/*/Ext/Rights.xml` парсер → `RoleAccess` model
- `Subsystem.xml ChildObjects` → fill `subsystems[]` в карточке
- `form_handlers` извлечение из графа (уже есть после audit-fix)
- Тесты parsing Rights.xml на синтетических fixtures

**Acceptance:**
- Карточка показывает 3-5 ролей с правом на чтение/запись/проведение
- Подсистемы указаны для 95%+ объектов
- Форм-handlers заполнены для всех документов и справочников с формами

**Риски:**
- Rights.xml формат меняется между версиями платформы (8.3.18 vs 8.3.27)
- Subsystem иерархия (subsystem of subsystem) — глубина

### Phase v2.F — Versional meta (~3 часа)

**Цель:** Поля `introduced_in`, `last_modified_in`, `breaking_changes`.

**Артефакты:**
- Скрипт `version_archeology.py` — анализирует все snapshot'ы одной типовой конфигурации (УТ 11.5.17 vs 11.5.18 vs ...) и формирует `breaking_changes`
- Требует 2+ snapshot'а одной типовой (пока есть только по 1)

**Acceptance:**
- Когда есть 2 snapshot'а УТ — карточка показывает diff
- Если 1 snapshot — поля пустые без ошибок

**Риски:**
- Нужно скачать дополнительные версии типовых (релизы 1С)
- Объём storage растёт линейно по числу snapshot'ов

### Phase v2.G — LLM judge validation (~4 часа)

**Цель:** Cross-check карточки vs графа для отлова галлюцинаций.

**Артефакты:**
- `card_validator.py`:
  - `validate_movements_vs_graph(card, graph)` — каждый movement.register должен иметь WRITES_TO edge от method-узлов объекта
  - `validate_related_objects_vs_graph` — должен быть REFERENCES / USES / CALLS
  - `validate_handlers_vs_graph` — handlers упомянутые в карточке существуют как method-узлы
- New поля: `validation_status` (passed/partial/failed), `validation_notes: list[str]`
- LLM-judge через **второй LLM-call** (когда есть real LLM):
  - prompt: «оцени соответствие карточки контексту 1-5»
  - сохранить `llm_judge_score` в карточке

**Acceptance:**
- 95% карточек проходят `validate_movements_vs_graph`
- 5% с проблемами помечены `validation_status=partial` с конкретными notes
- LLM judge score median ≥ 4.0 на golden dataset 20 объектов

**Риски:**
- Real LLM может ошибаться в обе стороны (false positive галлюцинаций)
- Cost double — каждый объект через 2 LLM call'а вместо 1

### Phase v2.H — Embedding v2 + semantic search (~3 часа)

**Цель:** Полный embedding_text + интеграция в vec_objects.

**Артефакты:**
- `TypicalObjectCard.embedding_text` v2 (расширенный)
- `embedding_text_short` для названий
- `embed_typical_cards(channel)` — batch embedding через OpenAI/NVIDIA → `vec_objects`
- LLM tool `search_typical_semantic(query, top_k=10)` — vector search вместо substring

**Acceptance:**
- *«операции в конце месяца»* находит `ЗакрытиеМесяца` через vector (substring не находит)
- *«учёт зарплаты»* находит `НачислениеЗарплаты` + связанные
- Recall@10 ≥ 0.8 на golden 30 запросов

**Риски:**
- Embedding cost: 63k карточек × ~500 tokens = ~32M tokens × $0.02/1M = $0.64. Дёшево
- Storage vec_objects: 63k × 1536 dim × 4 bytes = ~400 MB

---

## 4. Проверка качества

### 4.1 Golden dataset

Создать ручной список 30-50 эталонных карточек **разных типов** в 4 типовых:

```
- Документ.РеализацияТоваровУслуг (УТ): эксперт пишет «правильную» карточку
- Документ.СписаниеТоваров (БП): эксперт
- Регистр.Хозрасчетный (БП): эксперт
- Регламентное задание.ЗакрытиеМесяца (ERP): эксперт
- ... (35-45 объектов)
```

LLM-генерированные карточки сравниваются с эталонами:
- **Coverage** — % полей заполненных у LLM vs эталон
- **Accuracy** — % полей где LLM-значение семантически совпадает с эталоном (LLM-judge)
- **Hallucination rate** — % полей с false claims (нет в графе / противоречит факту)

### 4.2 Метрики качества (numerical targets)

| Метрика | Цель v2 | Замер |
|---|---:|---|
| Coverage (% non-empty полей) | ≥ 80% | автомат |
| Movements validation passed | ≥ 95% | автомат через `validate_movements_vs_graph` |
| ИТС-link relevance | precision ≥ 0.8 | manual review 50 карточек |
| Cross-config diff accuracy | ≥ 90% | manual review 20 пар |
| Semantic search Recall@10 | ≥ 0.8 | golden 30 запросов |
| Hallucination rate | ≤ 5% | manual review 100 карточек |
| LLM-judge median score | ≥ 4.0/5.0 | автомат |
| Latency `explain` end-to-end | ≤ 500 ms | smoke |

### 4.3 Регрессионный smoke

`typical_smoke_questions_v2.py` (расширение текущего) — на каждую фазу добавлять блок проверок:
- v2.A: разные типы карточек возвращают правильную shape
- v2.B: условная логика парсится
- v2.C: ИТС-ссылки фильтруются
- v2.D: cross-config map отвечает
- v2.E: роли/подсистемы заполнены
- v2.F: versional meta присутствует
- v2.G: validation_status корректен
- v2.H: semantic search recall ≥ target

Итого 100+ smoke проверок.

### 4.4 Cost monitoring

Перед массовой генерацией — runtime estimate:
- 9 типов карточек × 4 конфигурации × ~10k объектов = 360k объектов суммарно
- Реальный LLM × $0.0003/карточка = ~$108 на полный rebuild
- + LLM judge × 2 = $216
- + ИТС/БСП mention (existing embedding, бесплатно) = $0
- + Embedding карточек 32M tokens × $0.02/1M = $0.64
- **Итого: ~$220 за полный rebuild v2 на 4 типовые**

Бюджет умеренный, но **в 17× выше v1**. Нужно явное подтверждение пользователя перед запуском.

---

## 5. Возможные несостыковки и подводные камни

### 5.1 Schema migration backward compat
Существующие 63k v1 карточек в БД — нельзя удалить, нельзя сломать. Решение:
- Колонка `card_schema_version` ('v1' / 'v2')
- Старые карточки читаются через `GenericCard` (fallback)
- Перегенерация v1 → v2 — отдельным batch'ом

### 5.2 Длина prompt'а
Карточка с conditional posting_flow + ИТС-mentions + form-handlers легко превысит 2000 tokens в output. Это:
- Дороже на input/output
- Truncate риск при output limit модели

Решение: split prompt на несколько LLM-calls (1 для базы, 1 для conditional, 1 для links).

### 5.3 LLM-judge expensive
Cross-check через второй LLM-call удваивает cost. Альтернатива:
- **Rule-based valid** для movements (граф ↔ карточка) — бесплатно
- LLM-judge только для семантики (как написана formulation) — выборочно

### 5.4 Cross-config ambiguity
`Документ.РеализацияТоваровУслуг` в УТ vs БП — это **один и тот же объект** или **разные**? Технически разные (разные UUID), семантически близкие. Решение:
- `semantic_signature` — hash(key_attributes_sorted + movements_sorted)
- Cross-config map → даёт списком но **не** утверждает идентичность
- LLM `compare_with_typical` интерпретирует

### 5.5 Версии vs reality
Карточка построена на snapshot версии N. Если клиент обновился на N+1 — карточка устарела. Решение:
- Поле `snapshot_version` в карточке
- Frontend UI badge «карточка для версии X, у клиента Y»
- Periodic refresh (раз в квартал — новые snapshot'ы релизов 1С)

### 5.6 Embedding drift
При смене embedding-провайдера (OpenAI 1536 → NVIDIA 768) — все existing embeddings нужно пересчитать. Поле `embedding_model` + миграционный скрипт.

### 5.7 Roles XML parsing
Rights.xml — большой и сложный (предикаты RLS в XPath-подобном синтаксисе). Полный парсинг = недельная работа. Решение для v2:
- Извлечь только **списки** действий (Read/Write/Update/Post) без парсинга RLS-предикатов
- RLS-предикаты — в M-K3 (там есть own RLS-tracer)

### 5.8 Subsystem иерархия
`Subsystem A → Subsystem A.B → Subsystem A.B.C`. Глубина может быть 4-5. Решение:
- `subsystems: list[str]` — плоский список (полные пути «Продажи.Опт.Документы»)
- Иерархия — в отдельной карточке `SubsystemCard`

### 5.9 Form-handlers cardinality
Документ Реализация может иметь 10 форм × 30 handlers = 300 элементов. Это раздувает карточку. Решение:
- Лимит top-15 handlers по «важности» (handler-event > exported > internal)
- Полный список — через отдельный tool `list_form_handlers(qname, form_name)`

### 5.10 ИТС-link false positives
Поиск ИТС по «регистр накопления» вернёт top-10 — но большинство нерелевантно конкретному объекту. Решение:
- Не только semantic similarity, но **filter по object kind** (если ИТС-chunk про документы — не для регистра)
- Manual review 50 карточек после первой реализации, tune similarity threshold

---

## 6. Backward compatibility и rollout

### 6.1 Roll-out фазами

1. **Phase v2.A** — schema only, **не трогаем существующие карточки**. Новые объекты можно генерить в v2.
2. **Phase v2.B-H** — добавляем фичи, новые поля становятся optional
3. **Bulk migration** — после стабилизации запустить `migrate_all_v1_to_v2()` на всех 63k карточках (отдельная сессия)

### 6.2 Совместимость API

- `tool.explain_typical_object` v1 продолжает работать на v1 карточках
- Новый формат returnable через флаг `version: "v2"` в params
- Backward compatible для frontend `TypicalObjectCard.tsx` — компонент рендерит generic v1 поля, **игнорирует** v2-only

### 6.3 Frontend roll-out

- v1 рендер работает с v1 + v2 карточками (с graceful fallback при missing полях)
- Новые секции (`form_handlers`, `legal_basis`, `cross_config`) — отдельные компоненты, появляются если поля заполнены
- A/B-toggle через localStorage для прогрессивного roll-out

---

## 7. Сроки и зависимости (revised 2026-05-27)

```
Phase v2.0 (CRITICAL preventive) ── обязательно ПЕРЕД всем
       ↓
Phase v2.A (specializations) ─┬─ Phase v2.B (conditional, COULD)
                              ├─ Phase v2.C (ИТС/БСП links) — нужен M-K2.7/2.8 (готовы)
                              ├─ Phase v2.D (cross-config) — 3 строки SQL, SHOULD
                              ├─ Phase v2.E (roles/subsystems/handlers)
                              ├─ Phase v2.G (LLM-judge graph-based) — наш уникальный path
                              └─ Phase v2.H (embedding+hybrid search) — нужен real LLM
                                              ↓
                                           Phase v2.F (version archeology)
                                              нужны 2+ snapshot'а
```

**Минимум для production:** v2.0 + v2.A + v2.G + v2.H — **5-6 сессий ≈ 25-30 часов**.

**Полный план:** v2.0 + все 8 фаз — **8-10 сессий ≈ 40-50 часов**.

### Изменения после research

| Что | Старый план | Новый план | Причина |
|---|---|---|---|
| v2.0 (preventive) | отсутствовала | **обязательно перед v2.A** | 9 критичных рисков из research |
| v2.B (conditional) | SHOULD | COULD (отложить) | LLM может галлюцинировать условия (предупреждение из GraphRAG) |
| v2.D (cross-config) | medium | SHOULD high | 3 строки SQL, главный вопрос аналитика |
| v2.G (LLM-judge) | через 2-й LLM call | **через граф (GraphEval-стиль)** | У нас есть граф 2.2M узлов = идеальный ground truth |
| v2.H (embedding) | dense only | **hybrid BM25 + dense** | Mem0 v3 паттерн для proper nouns |

---

## 8. Гэпы которые НЕ закрывает v2

- **Performance UI** на больших картах — отложено в v3 (lazy-load секций, virtual scroll)
- **Multi-language** карточки (EN-локали ERP) — v3 после русских
- **Real-time refresh** при обновлении графа — v3 (требует change-data-capture)
- **Сравнение карточек между snapshot'ами УТ 11.5.17 → 11.5.18** — частично закрыто v2.F, но diff UI = v3
- **Совместная редактируемость экспертами** (overriding LLM output) — v3

---

## 9. Acceptance criteria для v2 в целом

- [ ] 9 типов карточек реализованы и валидируются Pydantic
- [ ] 80%+ полей не пусты на golden dataset (50 объектов)
- [ ] Movements validation passed ≥ 95% (automatic, vs граф)
- [ ] ИТС-links добавлены к ≥ 70% карточек с precision ≥ 0.8
- [ ] Cross-config map покрывает все 4 типовых
- [ ] Roles / subsystems / form-handlers заполнены автоматически
- [ ] LLM-judge median score ≥ 4.0/5.0
- [ ] Semantic search Recall@10 ≥ 0.8
- [ ] Hallucination rate ≤ 5% (manual review)
- [ ] Production cost ≤ $250 для rebuild 4 типовых
- [ ] Frontend graceful fallback на v1 карточках

---

## 10. Что делать СЕГОДНЯ

1. **Зафиксировать этот план** в `phases/M-K2.5/CARDS-V2-PLAN.md` (этот файл)
2. **Не реализовывать v2 сейчас** — это 6-8 сессий, требует:
   - Real LLM adapter (отдельный коммит)
   - Решение по бюджету ($220 на полный rebuild)
   - Декомпозицию loop.py из M-K3.0 (для clean integration)
3. **Закрыть M-K2.5 с пометкой** «v1 cards = MVP, v2 plan ready»
4. **При старте M-K3** держать в голове: некоторые поля v2 (RLS, roles) будут эффективнее закрыть **после** появления client-graph

---

## 11. Связанные документы

- `ADR-003-typical-configurations.md` — базовые архитектурные решения
- `M-K2.5-PLAN.md` — original план (фазы 0-8)
- `PILOT-FULL-RESULTS.md` — результаты v1
- `PILOT-UT-ERP-RESULTS.md` — расширение до 4/7
- `SUMMARY.md` — closing M-K2.5
- `M-K2.SUMMARY.md` — handoff в M-K3 (M-K2 closed)
