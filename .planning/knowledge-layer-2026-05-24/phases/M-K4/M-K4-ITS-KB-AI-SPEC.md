# AI-SPEC — Phase M-K4 (ИТС База Знаний / Knowledge Base): экспертные знания 1С

> AI design contract. Сгенерирован через GSD `/gsd-ai-integration-phase` (адаптировано: шаг framework-selector пропущен — фреймворк уже зафиксирован стратегией). Секции 1b/3/4/4b/5/6/7 написаны агентами `gsd-domain-researcher`, `gsd-ai-researcher`, `gsd-eval-planner`.
> **Дата:** 2026-05-29 · **Источник истины:** `docs/strategic-research/Analyst_Workspace_Strategy_2026-05-23.xlsx` (Направление I, приоритет P0) + `../../PLAN.md` (L5 Normative / Hybrid Retrieval).
> **Scope:** foundational ИТС knowledge base (RAG). Это **отдельный трек** от карточек типовых (M-K2.5, структура объектов) и от EPF/CFE (M-K3, доступ к данным базы). Consumed by `gsd-planner`.
> ⚠ **OPEN QUESTION (нужно подтверждение пользователя):** какие API-ключи использовать — **Anthropic** (LLM + prompt caching) и/или **OpenAI** (embeddings text-embedding-3-small). Без этого Раздел 4/5 нельзя финализировать.

---

## 1. System Classification

**System Type:** RAG / Knowledge Q&A (Hybrid Retrieval: vector ANN + BM25 + RRF)

**Description:**
База знаний экспертной методологии 1С для бота-аналитика «1С Напарник». RAG поверх **легальных** источников (v8std стандарты CC0, API платформы через bsl-context/HBK, БСП 3.2 паттерны, comol/ai_rules_1c). Интегрируется как RAG-prefetch ПЕРЕД LLM-вызовом в оркестраторе (`loop.py`). Пользователи — бизнес-аналитики 1С (не обязательно senior-разработчики). «Хорошо» = ответ уровня senior-методолога, заземлённый на **процитированные** источники, с честным «не нашёл» когда вопроса нет в корпусе. Бизнес-цель: hallucination rate по API платформы **30% → <5%**.

**Critical Failure Modes:**
1. **Фантомные методы/сигнатуры БСП** (FM-1) — выдуманный метод или параметр → сломанный BSL-код в боевой базе клиента. Самый частый (до 65% галлюцинаций кодогенерации) и самый опасный.
2. **Достройка ответа при пустом retrieval** вместо честного «не нашёл» — уверенная галлюцинация с «логичными» деталями.
3. **Цитирование несуществующих стандартов/источников** — мнимая верифицируемость, аналитик доверяет ложной ссылке.
4. **Утечка конфиденциального кода клиента** в публичный v8std MCP (152-ФЗ) — для prod только self-hosted retrieval.
5. **Путаница версий БСП 3.0/3.1/3.2** и контекста Клиент/Сервер/КлиентСервер (FM-2/FM-4) — код не работает в конкретной конфигурации/клиенте.

---

## 1b. Domain Context

**Industry Vertical:** Разработка и внедрение программного обеспечения на платформе 1С:Предприятие (экосистема 1С-партнёров и корпоративных аналитиков)
**User Population:** Бизнес-аналитики 1С, работающие с клиентскими базами через чат-интерфейс. Профиль: знают предметную область 1С (УТ, ERP, КА), но не обязательно владеют BSL на уровне senior-разработчика. Действуют в боевых или приближённых к боевым конфигурациях клиента.
**Stakes Level:** High
**Output Consequence:** Аналитик применяет ответ системы напрямую — пишет BSL-код, настраивает конфигурацию, консультирует клиента. Выдуманная сигнатура метода или несуществующий параметр → сломанный код в боевой базе клиента, потеря доверия аналитика к инструменту, потенциальные финансовые потери заказчика.

### What Domain Experts Evaluate Against

```
Dimension: Точность сигнатуры метода
Good: Ответ называет метод ОбщегоНазначения.ЗначениеРеквизитаОбъекта() с правильным набором
      параметров: (Ссылка, ИмяРеквизита, Тип) — и указывает, что возвращает произвольный тип.
Bad:  Ответ называет ОбщегоНазначения.ПолучитьЗначениеРеквизита() — метод не существует в БСП
      (выдуман на основе «звучит похоже»).
Stakes: Critical
Source: Документация БСП 3.x, bsl-context MCP / HBK — верифицируемые сигнатуры через API
```

```
Dimension: Ссылка на конкретный стандарт v8std
Good: «Согласно стандарту v8std #456 "Тексты модулей": процедуры экспортного API должны
      располагаться в разделе "Программный интерфейс" модуля общего назначения.»
Bad:  «По стандартам 1С принято размещать экспортные процедуры в начале модуля» — без номера
      стандарта, не верифицируемо.
Stakes: High
Source: v8std.ru (CC0) — стандарты имеют точные номера и заголовки
```

```
Dimension: Честное «не нашёл» вместо конструирования ответа
Good: «В индексированных источниках (v8std, HBK, БСП 3.2) описания метода
      БезопасноеХранилище.ПолучитьДанные() с параметром ВидХранилища не найдено.»
Bad:  Система конструирует описание несуществующего параметра ВидХранилища по аналогии.
Stakes: Critical
Source: Production RAG на узких корпусах — generation deficiency (модель замещает retrieved
        context внутренними параметрами)
```

```
Dimension: Соответствие версии БСП
Good: «ДлительныеОперации.ВыполнитьФункцию() доступен начиная с БСП 3.1.3. В БСП 3.0.x аналог —
      ДлительныеОперации.ВыполнитьВФоне() с иным набором параметров.»
Bad:  Описывает поведение БСП 3.1 без указания версии → пользователь на БСП 3.0 получает
      «Метод не обнаружен».
Stakes: High
Source: Changelog БСП 3.x — breaking changes между 3.0/3.1/3.2
```

```
Dimension: Применимость к управляемому приложению
Good: «РаботаСФайлами.ДобавитьФайл() работает в управляемом приложении; уточните режим
      конфигурации клиента.»
Bad:  Рекомендует Диалог.Открыть() — недоступно в веб-клиенте, без предупреждения.
Stakes: High
Source: Документация платформы 8.3 — клиентские ограничения управляемого приложения
```

### Known Failure Modes in This Domain

**FM-1: Фантомные методы общих модулей БСП.** Система генерирует `ОбщегоНазначения.ПолучитьТекущегоПользователя()` — метода не существует, есть `ПользователиКлиентСервер.ТекущийПользователь()`. Phantom function — доминирующий тип галлюцинации (до 65%). В 1С риск выше: модули БСП имеют неочевидные имена и Клиент/Сервер/КлиентСервер-суффиксы.

**FM-2: Несуществующие параметры.** `ДлительныеОперации.ВыполнитьФункцию(ИмяФункции, Параметры, ФоновоеЗадание)` — третий параметр в реальном API называется иначе и имеет другую структуру → «Несоответствие типов» в runtime.

**FM-3: Смешение v8std с устаревшими неофициальными рекомендациями** (посты Инфостарта 2015–2018), противоречащими актуальным стандартам. Аналитик не может верифицировать без номера стандарта.

**FM-4: Путаница суффиксов клиентского контекста.** Рекомендует серверный `ОбщегоНазначения.МетаданныеОбъекта()` на клиенте. Воспроизводится только в тонком/веб-клиенте, не в конфигураторе.

### Regulatory / Compliance Context

| Ограничение | Суть | Последствие нарушения |
|---|---|---|
| Запрет парсинга its.1c.ru | ToS ИТС запрещают автосбор | Претензия от «Фирма 1С», нелегальность распространения |
| Запрет интеграции code.1c.ai / 1С:Напарник | EULA запрещает встраивание | Прекращение доступа, юр. последствия |
| Атрибуция БСП (CC-BY-4.0) | Обязательна атрибуция «ООО Фирма 1С» | Нарушение лицензии |
| 152-ФЗ (ПДн) | Код клиента может содержать ПДн | Запрос к публичному v8std MCP недопустим; prod — только self-hosted |
| HBK платформы | Индексировать только локально, не в дистрибутив | Нарушение лицензии платформы |

### Domain Expert Roles for Evaluation

| Роль | Ответственность в оценке |
|---|---|
| Senior-методолог 1С (5+ лет, v8std + БСП) | Калибровка рубрики Good/Bad; разметка golden set (15–20 вопросов по реальным сигнатурам БСП) |
| Бизнес-аналитик 1С — целевой пользователь | A/B «принял бы как руководство / не принял»; выявление ложной уверенности |
| 1С-разработчик (bsl-context / HBK) | Верификация сигнатур по API; тест-кейсы FM-2/FM-4 |
| Юрист / продакт | Проверка источников на ToS/EULA; аудит атрибуции БСП |

---

## 2. Framework Decision

**Selected Framework:** Собственный лёгкий **Hybrid RAG** — `sqlite-vec` (vec0) + SQLite `FTS5` (BM25) + **RRF merge**, на FastAPI + aiosqlite. БЕЗ тяжёлого RAG-фреймворка.

**Version:** sqlite-vec 0.1.x · aiosqlite 0.21+ · openai SDK 1.68+ (embeddings) · FastAPI 0.115+ · Python 3.12. Eval-стек: RAGAS + Arize Phoenix + Promptfoo.

**Rationale:**
Стратегия (лист `02_ИТС_Подходы`) уже сравнила 7 подходов и выбрала **«MCP servers + Hybrid RAG»** как победителя (28/30, $0–30/мес, MVP 1–3 дня). Под Electron desktop (offline-friendly) лёгкий собственный RAG предпочтительнее тяжёлых фреймворков: `sqlite-vec` уже зафиксирован в стеке, FTS5 уже есть (`messages_fts`), LLM-транспорт model-agnostic (OpenAI-compat) уже в проекте. Нет внешних серверов, всё в одном `app.db` — критично для desktop-дистрибуции через PyInstaller/Electron. Дополнительно — MCP-серверы знаний (v8std публичный, bsl-context) как **supplementary retrieval** (tool-calls `search_its`/`search_bsp` уже заложены в `loop.py`).

**Alternatives Considered:**

| Framework | Ruled Out Because |
|-----------|------------------|
| LlamaIndex | Тяжёлый для Electron desktop, dependency bloat, боль PyInstaller-бандлинга; sqlite-vec уже locked, retrieval-логика проста (Hybrid + RRF) |
| LangChain / LangGraph | Abstraction overhead; нет сложного agent-state; RAG-primary use case |
| GraphRAG / Neo4j | Внешний сервер ~1GB, преждевременно (стратегия: только если реально нужны связи) |
| Fine-tuning (QLoRA на BSL) | Нет датасета (10K+ Q&A), дорого, catastrophic forgetting — RAG+LLM лучше (анти-паттерн стратегии) |
| Qdrant (Docker/managed) | Docker-зависимость конфликтует с Electron offline; опц. self-hosted позже при >100K векторов |

**Vendor Lock-In Accepted:** **Partial** (осознанно). Anthropic prompt caching (`cache_control`) — Anthropic-specific, но с документированным fallback для других провайдеров (plain system prompt). Embeddings — OpenAI-compat (свопается на Voyage multilingual для русского). Ядро RAG (sqlite-vec + FTS5 + RRF) — полностью провайдеро-независимо.

**System Type (downstream):** RAG / Knowledge Q&A · **Model providers:** Anthropic (LLM + caching) + OpenAI (embeddings) — ⚠ подтвердить ключи · **Eval concerns:** hallucination (phantom methods), context faithfulness, citation accuracy, retrieval precision/recall.

---

## 3. Framework Quick Reference — Custom Hybrid RAG (sqlite-vec + FTS5 + FastAPI)

### 3.1 Installation

```bash
# Core stack
pip install sqlite-vec aiosqlite fastapi uvicorn pydantic httpx openai

# Optional: Voyage multilingual для русского (лучше text-embedding-3-small на кириллице)
pip install voyageai

# PyInstaller target (Electron packaging) — нативный .dll в sqlite_vec wheel
pyinstaller --collect-all sqlite_vec --onefile app/main.py
```

**Версии (2026-05):** `sqlite-vec` 0.1.x (alpha, vec0 API стабилен) · `aiosqlite` 0.21+ · `openai` 1.68+ · `fastapi` 0.115+.

### 3.2 Ключевые импорты

```python
import sqlite_vec
import aiosqlite
from sqlite_vec import serialize_float32    # упаковка float-вектора в BLOB
```

**Загрузка расширения в aiosqlite:**
```python
async def get_db(path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(path)
    await db.enable_load_extension(True)
    await db.execute("SELECT load_extension(?)", [sqlite_vec.loadable_path()])
    await db.enable_load_extension(False)
    db.row_factory = aiosqlite.Row
    return db
```

### 3.3 Схема базы данных

```sql
-- vec0 virtual table; distance_metric=cosine для OpenAI embeddings (нормализованы)
CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    chunk_id    INTEGER PRIMARY KEY,
    channel_id  INTEGER,                              -- изоляция tenant
    embedding   float[1536] distance_metric=cosine    -- text-embedding-3-small
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  INTEGER NOT NULL,
    source      TEXT NOT NULL,       -- 'v8std' | 'bsp' | 'comol' | 'hbk'
    source_ref  TEXT,                -- номер стандарта / путь к файлу
    content     TEXT NOT NULL,
    token_count INTEGER,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, source_ref, content='chunks', content_rowid='id'
);
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content, source_ref) VALUES (new.id, new.content, new.source_ref);
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, source_ref) VALUES ('delete', old.id, old.content, old.source_ref);
END;
```

### 3.4 Entry-Point Patterns

**Pipeline A — INGEST** (load → chunk → embed → INSERT vec0+fts): чанкинг (см. 4b.4) → батч-embed (≤2048 строк) → транзакция INSERT в `chunks` + `vec_chunks` (через `serialize_float32`).

**Pipeline B — QUERY** (embed → vec ANN + FTS BM25 → RRF → inject):
```python
K_VEC, K_FTS, K_OUT = 10, 10, 5
RRF_K = 60

async def hybrid_retrieve(db, channel_id, query, oai):
    resp = await oai.embeddings.create(model=EMBED_MODEL, input=[query])
    q_vec = serialize_float32(resp.data[0].embedding)

    # Vector ANN — строго WHERE channel_id = ?
    vec_rows = await db.execute_fetchall(
        "SELECT chunk_id, distance FROM vec_chunks "
        "WHERE embedding MATCH ? AND channel_id = ? AND k = ? ORDER BY distance",
        (q_vec, channel_id, K_VEC))
    vec_ranks = {r["chunk_id"]: i+1 for i, r in enumerate(vec_rows)}

    # FTS5 BM25 — rank колонка быстрее bm25()
    fts_rows = await db.execute_fetchall(
        "SELECT c.id AS chunk_id FROM chunks c JOIN chunks_fts ON c.id = chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.channel_id = ? ORDER BY rank LIMIT ?",
        (fts_query_escape(query), channel_id, K_FTS))
    fts_ranks = {r["chunk_id"]: i+1 for i, r in enumerate(fts_rows)}

    # RRF merge
    rrf = {}
    for cid in set(vec_ranks) | set(fts_ranks):
        rrf[cid] = (1.0/(RRF_K+vec_ranks[cid]) if cid in vec_ranks else 0) \
                 + (1.0/(RRF_K+fts_ranks[cid]) if cid in fts_ranks else 0)
    top_ids = sorted(rrf, key=rrf.get, reverse=True)[:K_OUT]
    # … fetch chunk text для top_ids …

def fts_query_escape(q: str) -> str:
    # FTS5 не терпит '.' в MATCH — оборачиваем токены в кавычки
    return " ".join(f'"{t}"' for t in q.strip().split() if t)
```

### 3.5 Ключевые абстракции

| Абстракция | Что делает | Критично для |
|---|---|---|
| `vec0` virtual table | Плоский ANN (cosine) поверх SQLite | Offline ANN без сервера |
| `FTS5` + `rank` | BM25; `rank` быстрее `bm25()` | Keyword recall терминов 1С |
| RRF (k=60) | Объединяет 2 ранжированных списка без нормализации | Robustness |
| `cache_control` (Anthropic) | Промпт-кэш блока знаний (TTL=1h) | 90% экономия на knowledge_base.md |
| MCP supplementary | Fallback вне локального индекса | Актуальность v8std без переиндексации |

### 3.6 Типичные pitfalls

- **P1 — нет `channel_id` фильтра** в vec0-запросе → молча смешает tenant'ов. Каждый SELECT обязан `WHERE channel_id = ?`.
- **P2 — sqlite-vec flat ANN** деградирует после ~100K векторов (полный перебор, не HNSW). Для ~4K (800 стандартов × 5 чанков) — не проблема (~5 мс).
- **P3 — размерность.** `vec0(float[1536])` отвергает другую длину без внятной ошибки. Voyage = 1024 dims. Зафиксировать `EMBED_DIMS` + assert.
- **P4 — PyInstaller не включает нативный `.dll`** без `--collect-all sqlite_vec`. Симптом: `OSError: extension not found` только в prod-сборке.
- **P5 — FTS5 MATCH на `.`** (`ОбщегоНазначения.Метод`) падает `fts5: syntax error`. Экранировать токены кавычками (`fts_query_escape`).
- **P6 — `cache_control` TTL=1h** = 2× cache write на холодном старте сессии, окупается с 3-го хода. Только для стабильного knowledge_base.md, не для retrieved chunks.

### 3.7 Структура папок

```
app/knowledge/its/
  ingest.py      # Pipeline A
  retrieve.py    # Pipeline B (hybrid + RRF)
  chunker.py     # split_md_standard / split_bsl_code
  fts.py         # fts_query_escape, FTS DDL
  schema.py      # DDL + migrate()
app/llm/prompt_cache.py   # Anthropic cache_control builder
app/models/rag.py         # Pydantic RAGResponse, Citation
data/knowledge_base.md    # статические правила/стандарты → system prompt
sources/{v8std,comol,bsp,hbk}/
```

### 3.8 Sources
sqlite-vec (alexgarcia.xyz/sqlite-vec) · SQLite FTS5 BM25 · Anthropic prompt caching · OpenAI embeddings · RRF (Cormack 2009, k=60).

---

## 4. Implementation Guidance

### 4.1 Конфигурация модели
```python
EMBED_MODEL = "text-embedding-3-small"   # 1536 dims, $0.02/1M  (альт: voyage-multilingual-2, 1024)
EMBED_DIMS, EMBED_BATCH = 1536, 512
LLM_MODEL = "claude-sonnet-4-6"          # model-agnostic; температура низкая для фактологии
LLM_TEMP, LLM_MAX_TOKENS, LLM_TIMEOUT = 0.1, 1024, 30.0
K_VEC, K_FTS, K_OUT = 10, 10, 5
KNOWLEDGE_BASE_PATH, CACHE_TTL = "data/knowledge_base.md", "1h"
```

### 4.2 Core Pattern — RAG prefetch hook
RAG выполняется ПЕРЕД LLM-вызовом: `hybrid_retrieve` → форматирование контекста с явными источниками `[i] source/source_ref` → system (knowledge_base.md + cache_control) + user (`<retrieved_context>…</retrieved_context>` + вопрос) → LLM (`response_format=json_object`) → parse в Pydantic с retry.

### 4.3 Tool Use — локальный RAG + MCP supplementary
Если топ-RRF score < порога уверенности (≈0.02) → fallback к MCP `search_its`/`search_bsp` (v8std/bsl-context), приоритет MCP-результатам (свежее). Иначе — локальный RAG.

### 4.4 State Management
Векторный + FTS индекс персистентны в `knowledge.db` (FTS синхронизируется триггерами). История диалога `WHERE channel_id=?`. Backfill-джоб (`LEFT JOIN vec_chunks … WHERE chunk_id IS NULL`) до-индексирует чанки без векторов после сбоя/добавления источников.

### 4.5 Context Window Strategy
Бюджет (claude-sonnet, 200K): system base ~100 + knowledge_base.md ~8000 (КЭШ) + retrieved top-5 ~2500 + history ~3000 + вопрос ~100 ≈ 13.7K input. Усечение истории > 20 ходов: первые 2 + сводка (cheap model) + последние 10.

---

## 4b. AI Systems Best Practices

### 4b.1 Structured Outputs с Pydantic
```python
class Citation(BaseModel):
    source: str                          # 'v8std'|'bsp'|'comol'|'hbk'
    source_ref: str                      # номер стандарта / путь
    quote: str = Field(max_length=300)

class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]            # пустой если ответа нет в базе
    confidence: Literal["high","medium","low","not_found"]
    reasoning: str | None = None         # не показывать пользователю

    @field_validator("citations")
    @classmethod
    def citations_required_if_found(cls, v, info):
        if (info.data or {}).get("confidence","not_found") != "not_found" and len(v) == 0:
            raise ValueError("citations обязателен при confidence != not_found")
        return v
```
`response_format=json_object` гарантирует валидный JSON, но НЕ совпадение со схемой → Pydantic-валидация обязательна (2-й уровень), retry ≤2 с fallback в `not_found`.

### 4b.2 Async-First
`aiosqlite` (executor) + `AsyncOpenAI` + `httpx.AsyncClient` — не блокируют event loop. Критичная ошибка: `asyncio.run()` внутри FastAPI event loop (→ RuntimeError); только `await`. Stream несовместим с `json_object` — для streaming отдавать текст, Pydantic-валидация по финалу. Embed батчами по 512.

### 4b.3 Prompt Discipline
**System** (кэш): роль + инструкция JSON + few-shot NOT_FOUND + knowledge_base.md (`cache_control`). **User** (динамика): `<retrieved_context>` с источниками + вопрос. `max_tokens` всегда явно. Темп 0.1 (выше 0.3 → «творческие» цитаты). XML-теги > markdown-разделители для Claude.

### 4b.4 Context / Chunking
`split_md_standard` (по заголовкам ##/###, sliding window с overlap при превышении, не разрывать нумерованные списки стандартов) vs `split_bsl_code` (по границам `Процедура/Функция … КонецПроцедуры`, не разрывать тело, chunk_tokens выше). `_approx_tokens ≈ len//4`.

### 4b.5 Cost / Latency
Cache hit: ~$0.0195/вызов; cache miss (1-й в сессии): ~$0.065 (окупается с 4-го хода). Output 1024 × $15/1M = $0.015. Типичный ~$0.035/запрос. Оптимизации: prompt cache (−60-90%), exact-match cache (sha256(channel+question)→ответ), cheap model для суммаризации, K_OUT=3. **Latency:** embed ~50мс + ANN ~5мс + BM25 ~2мс + RRF <1мс + LLM ~2с → p50 ~2.5с, **p95 <5с** (timeout 30с защита).

---

## 5. Evaluation Strategy

### 5.1 Eval Dimensions & Rubrics

| # | Dimension | Priority | Measurement | Target |
|---|-----------|----------|-------------|--------|
| D1 | Phantom Method Detection | Critical | Code (bsl-context lookup) | hallucination rate <5% |
| D2 | Context Faithfulness | Critical | RAGAS | faithfulness ≥ 0.90 |
| D3 | Honest Not-Found | Critical | Code | 100% при пустом retrieval |
| D4 | Citation Accuracy | High | Code + LLM Judge | citation coverage ≥ 95% |
| D5 | Retrieval Precision / Recall | High | RAGAS | context_precision@5 ≥ 0.85 |
| D6 | BSP Version Correctness | High | LLM Judge | judge corr. ≥ 0.7 с human |
| D7 | Managed App Applicability | Medium | LLM Judge | — |
| D8 | Schema Validity (RAGResponse) | High | Code | 0 нарушений |
| D9 | Latency p95 | High | Code | <5 000 ms e2e |

**D1 — Phantom Method Detection (killer-feature, детерминированно):** каждый идентификатор `Модуль.Метод(` в `answer` → lookup через `bsl-context` MCP. Не найден (при confidence != not_found) → `phantom_flag=True`. Фильтр по core-namespace БСП (`ОбщегоНазначения.*`, `ДлительныеОперации.*` и т.д.), чтобы не ловить методы кастомных конфигураций.
```python
BSL_CALL_RE = re.compile(r'([А-ЯЁа-яёA-Za-z][\wА-ЯЁа-яё]*)\.([А-ЯЁа-яёA-Za-z][\wА-ЯЁа-яё]*)\(')
async def check_phantom_methods(answer):
    phantoms = [f"{m}.{f}" for m, f in BSL_CALL_RE.findall(answer)
                if not (await bsl_context.search(f"{m}.{f}")).found]
    return {"phantom_count": len(phantoms), "phantoms": phantoms, "pass": not phantoms}
```
**D2** RAGAS faithfulness (каждый факт прослеживается до retrieved chunk). **D3** при 0 chunks выше threshold → confidence=not_found + citations=[]. **D4** quote реально присутствует в source_ref chunk (substring/≥0.85 sim). **D5** RAGAS context_precision/recall. **D6/D7** LLM judge (калибровка ≥0.7 на 10 human-примерах). **D8** Pydantic. **D9** Phoenix spans.

### 5.2 Eval Tooling

| Concern | Tool | Обоснование |
|---|---|---|
| Tracing | **Arize Phoenix** | OSS, self-host, OTel-native, RAG dashboard |
| RAG metrics | **RAGAS** | faithfulness / answer_relevance / context_precision / recall |
| CI/CD regression | **Promptfoo** | CLI, YAML, без cloud-аккаунта |
| Phantom check | **bsl-context MCP** | уже в стеке, детерминированный lookup |
| Schema | **Pydantic** | RAGResponse уже Pydantic |

```bash
pip install ragas arize-phoenix opentelemetry-sdk opentelemetry-instrumentation-httpx
npm install -g promptfoo
python -m phoenix.server.main serve          # Phoenix локально :6006
promptfoo eval --config eval/promptfooconfig.yaml   # CI regression
```

### 5.3 Reference Dataset
**20 примеров**, JSONL (`eval/dataset/reference_set.jsonl`). Состав: 5× critical BSP signatures (FM-1), 3× несуществующие параметры (FM-2 → not_found), 3× v8std vs Инфостарт (FM-3), 3× суффиксы Клиент/Сервер (FM-4), 3× версии БСП 3.0/3.1/3.2, 3× honest not-found (пустой retrieval). Поля: `query`, `ground_truth_answer` (или null), `expected_confidence`, `phantom_methods_in_answer:[]`, `required_citations:[source_ref]`. Разметка — **senior-методолог 1С**. Старт во время реализации (Sprint 1), первые 10 = FM-1 + not-found.

**Целевые метрики:** hallucination <5% (baseline ~30%) · faithfulness ≥0.90 · context_precision@5 ≥0.85 · honest_not_found 100% · citation_accuracy ≥95% · latency p95 <5с · RAG hit rate >40% (после 2 недель).

---

## 6. Guardrails

### 6.1 Online (real-time) — 3 критических, минимум latency

| # | Guardrail | Триггер | Действие | Latency |
|---|-----------|---------|----------|---------|
| G1 | **Citation Required** | confidence != not_found AND citations == [] | Блок + регенерация с усиленным промптом (1 retry); если пусто → force confidence=low + warn | <10 ms |
| G2 | **Phantom Method** | `Модуль.Метод(` не найден в bsl-context (async, параллельно стриму) | Flag phantom + UI-баннер «сигнатура не верифицирована, проверьте»; лог в Phoenix `phantom=true`. Не блокирует UX | <50 ms async |
| G3 | **Empty Retrieval → Not-Found** | 0 chunks ИЛИ max RRF < 0.15 | Прервать LLM, вернуть not_found + «нет в базе знаний», citations=[]. Не тратить токены | <5 ms (до LLM) |

### 6.2 Offline Flywheel

| Сигнал | Условие | Действие | Период |
|--------|---------|----------|--------|
| Low RRF | max RRF < 0.30 при непустом retrieval | human review → dataset/корпус | еженедельно |
| Zero citations | citations==[] при confidence!=not_found | LLM judge faithfulness → dataset | еженедельно |
| Negative feedback | юзер «Неверно» | review queue, 48h SLA, авто phantom-check | ежедневно |
| Phantom в prod | G2 сработал | сохранить query+answer+phantoms → corpus gap | еженедельно |
| confidence=low spike | >20%/день | алерт → аудит 10 сэмплов | real-time |

---

## 7. Production Monitoring

**Tracing:** Arize Phoenix (`:6006`, self-host, `channel_id` tag на span). Spans: `retrieval` (ann_ms/bm25_ms/rrf_ms/chunks_retrieved) → `llm_generation` (prompt/completion tokens, cache_hit, ttft_ms) → `phantom_check` (phantoms_detected) → `response` (confidence, citation_count, total_ms).

**Key Metrics & Alerts:**

| Метрика | WARN | CRIT | Действие |
|---------|------|------|----------|
| hallucination_rate (phantom/total, 1h) | >3% | >7% | alert + review 50 phantom cases |
| citation_coverage (1h) | <90% | <80% | check G1 logs, audit prompt |
| rag_hit_rate (24h) | <35% | <25% | corpus gap analysis |
| not_found_rate (1h) | >40% | >60% | corpus freshness, threshold review |
| latency_p95_ms (5m) | >4000 | >6000 | check sqlite-vec index, Phoenix breakdown |
| cache_hit_rate | <40% | <20% | review prompt caching / prompt stability |

**Smart Sampling:** phantom_flag → 100%; not_found при rag_hit → 30%; confidence=low → 20%; negative feedback → 100%; G1 retry → 100%; norm → 2% (drift).

**Минимум для launch:** G1 + G3 в коде до первого юзера · 10 примеров dataset (FM-1 + not-found) · Phoenix tracing + hallucination_rate метрика · G2 async с UI-флагом.

---

## Checklist

- [x] System type classified (RAG / Knowledge Q&A)
- [x] Critical failure modes identified (≥ 3) — 5 шт.
- [x] Domain context researched (Section 1b: vertical, stakes, expert criteria, failure modes FM-1..4)
- [x] Regulatory/compliance context identified (152-ФЗ, EULA/ToS, CC-BY/CC0)
- [x] Domain expert roles defined for evaluation
- [x] Framework selected with rationale (Hybrid RAG sqlite-vec, не LlamaIndex/LangChain)
- [x] Alternatives considered and ruled out (5 шт.)
- [x] Framework quick reference written (install, imports, pattern, pitfalls P1-P6)
- [x] AI systems best practices written (Pydantic, async, prompt discipline, chunking, cost)
- [x] Evaluation dimensions grounded in domain rubric (D1-D9)
- [x] Each eval dimension has concrete rubric (Good/Bad в языке 1С)
- [x] Eval tooling selected (RAGAS + Arize Phoenix + Promptfoo + bsl-context)
- [x] Reference dataset spec (20 примеров, состав + разметка senior-методологом)
- [x] CI/CD eval integration specified (Promptfoo)
- [x] Online guardrails defined (G1-G3)
- [x] Production monitoring configured (Phoenix + smart sampling)
- [ ] ⚠ OPEN: подтвердить API-ключи (Anthropic для caching / OpenAI для embeddings) — нужно от пользователя
- [ ] ⚠ OPEN: согласовать позицию фазы в roadmap (стратегия: P0 «вперёд»; knowledge-layer: M-K4)
