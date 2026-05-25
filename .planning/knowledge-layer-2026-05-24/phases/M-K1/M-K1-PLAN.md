# M-K1 — Foundation: Decisions + Quick Wins

**Milestone:** M-K1  
**Срок:** 1-2 недели, до **15.06.2026**  
**Parent plan:** `../../PLAN.md`  
**Branch:** `feature/m-k1-foundation` (создаётся при kickoff)

---

## Цель милстоуна (одна фраза)

Зафиксировать 3 архитектурных решения (vector / graph / embeddings), создать  
скелет модуля `backend/app/knowledge/`, заполнить metadata_cache и выдать  
первый killer-UX «расскажи про объект» за **5 рабочих дней**.

---

## Definition of Done всего милстоуна

- [ ] 3 ADR написаны и committed: `adr/001-vector-db.md`, `adr/002-graph-db.md`,  
  `adr/003-embeddings.md`
- [ ] `OPEN-VS-CLOSED.md` boundary документ committed
- [ ] Модуль `backend/app/knowledge/` существует с README + `__init__.py` +  
  базовыми types
- [ ] `backend/app/knowledge/storage.py` управляет per-config layout  
  (`~/.analyst-1c/knowledge/<fingerprint>/`)
- [ ] Configuration Fingerprint считается на `/connections/{id}/ping`,  
  записывается в SQLite
- [ ] При POST `/connections` — `metadata_cache` заполняется автоматически  
  background-таском
- [ ] `GET /knowledge/{channel}/dossier/{object_path}` возвращает паспорт  
  объекта 1С (структура + табл.части + формы + подписки)
- [ ] В чате `@Документ.ОПП` (или другой реальный объект) → orchestrator вызывает  
  `knowledge_dossier` internal tool → выводит Object Card с полным паспортом  
  за ≤ 5 сек (cold)
- [ ] `backend/tests/knowledge/` содержит ≥ 15 тестов, все проходят
- [ ] `pytest` + `vitest` + `pnpm build` зелёные
- [ ] Smoke на InfoBase5 (или dev-стенде) — UC «расскажи про объект» работает
- [ ] `phases/M-K1/SUMMARY.md` написан, content передан в M-K2 handoff

---

## Phases внутри M-K1

```
M-K1.1 — ADR (3 решения)              [0.5d]  ●○○○○○○○○ pending
M-K1.2 — OPEN-VS-CLOSED.md            [0.5d]  ●○○○○○○○○ pending  
M-K1.3 — Module skeleton              [0.5d]  ●○○○○○○○○ pending
M-K1.4 — Storage Layout (X-3)         [0.5d]  ●○○○○○○○○ pending
M-K1.5 — Configuration Fingerprint    [0.5d]  ●○○○○○○○○ pending  (L1-4)
M-K1.6 — Metadata Cache filler        [0.5d]  ●○○○○○○○○ pending  (L1-1)
M-K1.7 — Object Dossier API           [1.0d]  ●○○○○○○○○ pending  (L1-2)
M-K1.8 — UC «расскажи про объект»     [0.5d]  ●○○○○○○○○ pending  (L1-3)
M-K1.9 — SUMMARY + smoke + handoff    [0.5d]  ●○○○○○○○○ pending
                                       ────
                                       5.0d  (~1-2 недели календарно)
```

Dependencies:

```
1.1 ─┐
1.2 ─┼─→ 1.3 ─→ 1.4 ─→ 1.5 ─→ 1.6 ─→ 1.7 ─→ 1.8 ─→ 1.9
     │
     └→ всё остальное может ссылаться на ADR
```

1.1 и 1.2 — независимы между собой, можно параллельно. Остальное — последовательно.

---

## M-K1.1 — ADR (3 решения)

### Subject
Зафиксировать архитектурные выборы в формальных Architecture Decision Records.  
Цель — снять блокирующее технологическое решение перед написанием кода.

### Файлы создаются
- `.planning/knowledge-layer-2026-05-24/adr/001-vector-db.md`
- `.planning/knowledge-layer-2026-05-24/adr/002-graph-db.md`
- `.planning/knowledge-layer-2026-05-24/adr/003-embeddings-runtime.md`
- `.planning/knowledge-layer-2026-05-24/adr/README.md` (формат ADR + индекс)

### Формат каждого ADR
```markdown
# ADR-NNN: <Title>

**Status:** Accepted  
**Date:** YYYY-MM-DD  
**Deciders:** Никита, Claude

## Context
<В чём проблема, что выбираем>

## Decision
<Что выбрали в одной фразе>

## Rationale
<Почему. Конкретные доводы.>

## Consequences
**Positive:**
- ...

**Negative / Trade-offs:**
- ...

## Alternatives considered
| Альтернатива | Pros | Cons | Почему отвергли |
|--------------|------|------|-----------------|

## Migration / Reversibility
<Если решение придётся отменить — что стоит, насколько reversible>

## References
- <ссылки на research, документацию>
```

### Содержание решений (выбраны в Excel)

**ADR-001 Vector DB: sqlite-vec (старт) → LanceDB (when scale)**
- Альтернативы: Qdrant embedded, Chroma, LanceDB сразу
- Почему: всё в одном SQLite, минимум зависимостей, lock-in минимальный

**ADR-002 Graph DB: SQLite + edges table + recursive CTE**
- Альтернативы: Kuzu (Apple купила 10.2025 — risk), Neo4j (heavy)
- Почему: Code Index доказал на 93k файлов, без vendor lock-in

**ADR-003 Embeddings Runtime: FastEmbed (ONNX, in-process)**
- Альтернативы: Ollama (требует daemon), HF TEI (требует Docker)
- Почему: один pip install, bundling в PyInstaller, critical для Electron-deploy

### Acceptance criteria
- [ ] Все 3 ADR написаны по формату выше
- [ ] Каждый ADR имеет ≥ 2 альтернативы рассмотренных
- [ ] README.md в adr/ содержит индекс
- [ ] Никита просмотрел и поставил «approved» (комментарий в PR / в чате)

### Estimate
0.5 дня. Это чистый writing, без кода.

---

## M-K1.2 — OPEN-VS-CLOSED.md

### Subject
Зафиксировать boundary что из Knowledge Layer open-source, что closed.

### Файл создаётся
`.planning/knowledge-layer-2026-05-24/OPEN-VS-CLOSED.md`

### Содержание (предложение, требует approval)

**OPEN (можно опубликовать в GitHub):**
- Indexer pipeline (X-1 / X-2)
- BSL parser wrapper (L2-2)
- Graph schema + builders (L2-1, L2-3, L2-4)
- Vector store wrapper (L3-1)
- Embedding pipeline (L3-2)
- Storage layout (X-3)
- MCP server wrapper (OPS-5)

**CLOSED (proprietary advantage):**
- Reference Configurations Library (L6-3) — fingerprints типовых УТ/ERP/БП/УСО
- Diagnose rulebook (L4-1) — YAML с known patterns symptom → workflow
- Business semantics knowledge — bundles для отраслей (торговля, производство,  
  бюджет, ВЭД)
- Pricing tier matrix + license enforcement

**Лицензии:**
- Open parts: Apache 2.0
- Closed parts: proprietary, commercial license

### Acceptance criteria
- [ ] Документ ≤ 1 страница, читается за 3 минуты
- [ ] Каждый компонент классифицирован
- [ ] Указан formal license для каждого
- [ ] Никита approved

### Estimate
0.5 дня. Writing + согласование.

---

## M-K1.3 — Module skeleton

### Subject
Создать `backend/app/knowledge/` модуль с минимальной структурой,  
импортируемый, тестируемый.

### Файлы создаются

```
backend/app/knowledge/
├── __init__.py              # экспорты публичных типов
├── README.md                # что это, как использовать, ссылка на PLAN
├── types.py                 # Pydantic-модели: ObjectPath, Dossier, etc.
├── exceptions.py            # KnowledgeError, ObjectNotFoundError, etc.
└── _internal/
    └── __init__.py
backend/tests/knowledge/
├── __init__.py
├── conftest.py
└── test_module_imports.py   # тест что модуль импортируется без ошибок
```

### Acceptance criteria
- [ ] `from app.knowledge import ObjectPath, Dossier` работает
- [ ] `python -m pytest tests/knowledge/test_module_imports.py` зелёный
- [ ] README.md в модуле содержит: цель, ссылку на PLAN.md, мини-пример  
  использования (даже если функционал ещё не работает)
- [ ] Pydantic-модели типизированы strict, без `any`
- [ ] Нет import'ов чего-то ещё не существующего

### Estimate
0.5 дня. Простой scaffold.

---

## M-K1.4 — Storage Layout (X-3)

### Subject
Реализовать `StorageManager` который управляет per-config layout  
в `~/.analyst-1c/knowledge/<fingerprint>/`.

### Файлы создаются / изменяются
- `backend/app/knowledge/storage.py` (новый) — `StorageManager` class
- `backend/app/config.py` (изменяется) — добавить `knowledge_root` setting  
  с default `~/.analyst-1c/knowledge`
- `backend/tests/knowledge/test_storage.py` — ≥ 5 тестов

### API спецификация
```python
class StorageManager:
    def __init__(self, root: Path, fingerprint: str): ...
    
    @property
    def metadata_db_path(self) -> Path: ...
    @property
    def graph_db_path(self) -> Path: ...
    @property
    def vectors_path(self) -> Path: ...
    @property
    def ast_dir(self) -> Path: ...
    @property
    def snapshots_dir(self) -> Path: ...
    
    def ensure_layout(self) -> None: ...
    def acquire_lock(self) -> ContextManager: ...
    def export_bundle(self, output_path: Path) -> None: ...  # M-K5
    def import_bundle(self, bundle_path: Path) -> None: ...  # M-K5
    def stats(self) -> dict: ...  # disk usage breakdown
```

### Acceptance criteria
- [ ] `StorageManager(root, "abc123").ensure_layout()` создаёт все dirs
- [ ] `metadata_db_path` etc. возвращают корректные Path
- [ ] Lock acquire/release работает (concurrent.futures Lock или filelock)
- [ ] Тест на cleanup: создан → ensure → удалить
- [ ] Тест на permissions (Windows и Linux разные)
- [ ] `export_bundle` / `import_bundle` — заглушки с raise NotImplementedError  
  (реализация в M-K5)

### Estimate
0.5 дня.

---

## M-K1.5 — Configuration Fingerprint (L1-4)

### Subject
Считать стабильный хеш конфигурации 1С для invalidation cache.

### Файлы создаются / изменяются
- `backend/app/knowledge/fingerprint.py` (новый) — `ConfigurationFingerprint`
- `backend/app/storage/migrations.py` — добавить миграцию V11 с таблицей  
  `configuration_fingerprints(channel_id, fingerprint, computed_at, components_json)`
- `backend/app/knowledge/integration/connections_hook.py` — hook на ping/create  
  для пересчёта
- `backend/tests/knowledge/test_fingerprint.py` — ≥ 4 теста

### Алгоритм fingerprint
```python
# из MCP get_metadata_tree:
components = {
    "platform_version": "8.3.27.1989",
    "bsp_version": "3.2.1.123",
    "configuration_name": "УправлениеТорговлей",
    "configuration_version": "11.5.16.140",
    "objects_count": {
        "Документ": 142,
        "Справочник": 287,
        "РегистрНакопления": 64,
        ...
    },
    "key_object_names": ["ОПП", "АгентскиеБонусы", ...],  # top-N по алфавиту
}
fingerprint = sha256(json.dumps(components, sort_keys=True)).hexdigest()[:16]
```

### Acceptance criteria
- [ ] Fingerprint считается за ≤ 1 сек на средней УТ
- [ ] Одинаковая конфигурация → одинаковый fingerprint (детерминированный)
- [ ] Изменение количества объектов → fingerprint меняется
- [ ] При `POST /connections` — fingerprint считается background-таском  
  и пишется в SQLite
- [ ] `GET /connections/{id}` возвращает поле `fingerprint`
- [ ] Тесты с моками MCP

### Estimate
0.5 дня.

---

## M-K1.6 — Metadata Cache filler (L1-1)

### Subject
Заполнить готовую таблицу `metadata_cache` при первом обращении к каналу.

### Файлы создаются / изменяются
- `backend/app/knowledge/cache.py` (новый) — `MetadataCacheService`
- `backend/app/knowledge/integration/connections_hook.py` (изменяется) — после  
  fingerprint расчёта запускает cache fill
- `backend/tests/knowledge/test_cache.py` — ≥ 5 тестов

### API
```python
class MetadataCacheService:
    def __init__(self, db: aiosqlite.Connection, channel_id: str): ...
    
    async def is_fresh(self, fingerprint: str) -> bool:
        """Кеш свежий если последний fill был при том же fingerprint."""
    
    async def fill_from_mcp(self, mcp_client: MCPClient) -> CacheFillResult:
        """Полный crawl метаданных через get_metadata_tree + write to cache."""
    
    async def get_object(self, object_path: str) -> CachedObject | None: ...
    async def list_by_type(self, object_type: str) -> list[CachedObject]: ...
    async def search_by_name(self, name_prefix: str) -> list[CachedObject]: ...
    
    async def invalidate(self) -> None: ...
```

### Acceptance criteria
- [ ] Fill средней УТ: ≤ 30 сек (через MCP get_metadata_tree)
- [ ] Повторный fill при том же fingerprint — skip (is_fresh = True)
- [ ] `get_object("Документ.ОПП")` возвращает CachedObject с полями  
  (object_type, name, presentation, attributes_json)
- [ ] Background task через FastAPI BackgroundTasks (не блокирует endpoint)
- [ ] SSE event 'metadata_cache_filled' для UI Progress
- [ ] Тесты с моками MCP

### Estimate
0.5 дня.

---

## M-K1.7 — Object Dossier API (L1-2)

### Subject
API для получения полного «паспорта» объекта 1С: композит из metadata_cache +  
MCP get_object_structure + get_form_handlers + get_event_subscriptions.

### Файлы создаются / изменяются
- `backend/app/knowledge/dossier.py` (новый) — `DossierService`
- `backend/app/routes/knowledge.py` (новый) — REST endpoints
- `backend/app/main.py` — register router
- `backend/tests/knowledge/test_dossier.py` — ≥ 6 тестов
- `backend/tests/knowledge/test_routes.py` — ≥ 3 теста на REST

### API
```python
class DossierService:
    async def get_dossier(self, channel_id: str, object_path: str) -> Dossier:
        """
        Параллельно вызывает:
        - metadata_cache.get_object
        - MCP get_object_structure
        - MCP get_form_handlers (если применимо)
        - MCP get_event_subscriptions (если применимо)
        Композирует в единый Dossier.
        """
```

### Pydantic-модель `Dossier`
```python
class Dossier(BaseModel):
    object_path: str  # "Документ.ОПП"
    object_type: str  # "Документ"
    name: str  # "ОПП"
    synonym: str | None  # "Опись передаваемых поручительств"
    presentation: str
    
    attributes: list[Attribute]  # реквизиты
    tabular_sections: list[TabularSection]  # табл.части
    forms: list[FormRef]  # формы
    commands: list[CommandRef]  # команды
    event_subscriptions: list[EventSubscription]  # подписки
    
    # для регистров — измерения/ресурсы/реквизиты + registrar
    dimensions: list[Attribute] | None
    resources: list[Attribute] | None
    registrar_types: list[str] | None
    
    # metadata
    fingerprint_at_fetch: str
    fetched_at: datetime
    fetch_duration_ms: int
```

### REST endpoint
```
GET /knowledge/{channel_id}/dossier/{object_path}

Response 200: Dossier (JSON)
Response 404: { "error": "object_not_found" }
Response 503: { "error": "mcp_disconnected" }
```

### Acceptance criteria
- [ ] Запрос на `Документ.ОПП` в Транзите возвращает корректный Dossier  
  за ≤ 3 сек (warm cache)
- [ ] Параллельные MCP вызовы (asyncio.gather), не последовательные
- [ ] Кеш metadata_cache используется (видно в trace)
- [ ] 404 если объект не существует
- [ ] 503 если MCP недоступен
- [ ] OpenAPI документация генерируется FastAPI
- [ ] Тесты с моками MCP + реальный smoke

### Estimate
1.0 день. Это самая мясная phase.

---

## M-K1.8 — UC «расскажи про объект» (L1-3)

### Subject
Подключить Dossier к чату как internal tool, чтобы LLM мог его вызвать при  
запросе `@Документ.ОПП` или «расскажи про документ ОПП».

### Файлы изменяются
- `backend/app/orchestrator/loop.py` — добавить новый internal tool  
  `knowledge_dossier`:
  ```python
  if tool_name == "knowledge_dossier":
      result = await dossier_service.get_dossier(channel_id, args["object_path"])
      yield tool_result_event(...)
  ```
- `backend/app/orchestrator/loop.py` — добавить tool description в SYSTEM_PROMPT  
  (короткий: «когда пользователь спрашивает про объект 1С — вызови knowledge_dossier»)
- `frontend/components/cards/ObjectCard.tsx` — extension для отображения Dossier  
  (или новый `DossierCard.tsx`)
- `backend/tests/test_orchestrator_dossier_tool.py` — integration тест

### Acceptance criteria
- [ ] В чате запрос «расскажи про Документ.ОПП» → LLM вызывает  
  `knowledge_dossier({object_path: "Документ.ОПП"})` → ObjectCard / DossierCard  
  выводится за ≤ 5 сек cold
- [ ] При повторном запросе — ≤ 1 сек (cache hit)
- [ ] Smoke на dev-стенде с InfoBase5
- [ ] Не ломает существующие тесты orchestrator (1457 тестов всё ещё зелёные)

### Estimate
0.5 дня. Минимальная интеграция.

---

## M-K1.9 — SUMMARY + smoke + handoff

### Subject
Финализация милстоуна. Документация. Передача в M-K2.

### Файлы создаются
- `.planning/knowledge-layer-2026-05-24/phases/M-K1/SUMMARY.md` — отчёт
- `.planning/knowledge-layer-2026-05-24/phases/M-K1/HANDOFF-to-M-K2.md` — что  
  передаём в следующую фазу

### Содержание SUMMARY.md
- ✅ Что сделано (по checklist DoD)
- ⚠ Что не успели (если есть)
- 📊 Метрики (cold/warm latency, размер кеша, etc.)
- 🐛 Технический долг
- 🔗 Файлы изменены/созданы
- 📦 Commits

### Содержание HANDOFF-to-M-K2.md
- Готовая инфраструктура для M-K2 (Storage Manager + Fingerprint + Cache)
- Открытые TODO которые M-K2 должен подобрать
- Изменения в API которые M-K2 должен учесть

### Smoke checklist
- [ ] Backend поднят (`awd-dev-up`)
- [ ] Frontend поднят
- [ ] Подключение к InfoBase5 (или dev-каналу)
- [ ] Видно как индексируется metadata_cache (через лог)
- [ ] `GET /knowledge/dev/dossier/Документ.ОПП` через curl/Postman работает
- [ ] В чате запрос работает end-to-end
- [ ] `pytest` все зелёные
- [ ] `vitest` все зелёные

### Estimate
0.5 дня.

---

## Метрики успеха всего M-K1

| Метрика | Target | Как меряем |
|---------|--------|------------|
| Cold latency «расскажи про объект» | ≤ 5 сек | `time` smoke test |
| Warm latency (повторный) | ≤ 1 сек | `time` smoke test |
| Backend tests added | ≥ 15 | pytest count |
| Frontend tests added | ≥ 3 | vitest count |
| Existing tests broken | 0 | regression check |
| Bundle size growth (Electron) | ≤ 5 MB | сравнение dist/ |
| Onboarding нового разработчика по ADR | ≤ 30 мин | спросить Никиту |

---

## Риски M-K1 и mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| FastEmbed не bundle-ится в PyInstaller | HIGH | Тест на чистой VM в M-K1.3, fallback на ONNX runtime отдельно |
| MCP `get_metadata_tree` slow на больших ERP | MEDIUM | Async, background task, прогресс UI в M-K1.6 (по факту делается в M-K2 UX-6) |
| metadata_cache схема не подходит под реальные данные 1С | MEDIUM | Прогон на 3 разных конфигурациях (УТ + ERP + УСО) в M-K1.6 |
| Внезапные breaking changes в `loop.py` | LOW | Минимальная интеграция в M-K1.8 (только tool registration) |

---

## Параллельные задачи из общего аудита (рекомендую делать в фоне)

Не блокеры M-K1, но улучшат фундамент перед M-K2:

- **SEC-12** X-LLM-API-Key deprecation marker (1 коммит)
- **DOC-1** ARCHITECTURE.md ревизия (можно делегировать в `doc-updater`)
- **BE-7** _parse_updated_at fallback fix (1 коммит)

---

## После M-K1 — что в M-K2

См. `../M-K2-PLAN.md` (создаётся в начале M-K2 kickoff).

Кратко: indexing pipeline + ИТС RAG + БСП RAG + vector store + embeddings.
