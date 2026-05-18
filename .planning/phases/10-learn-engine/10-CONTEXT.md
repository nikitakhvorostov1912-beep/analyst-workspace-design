# Phase 10: Learn Engine — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning — **Path B chosen by Claude's discretion**
**Source:** MSG #10 — «на этих данных нужно обучаться»

<domain>
## Phase Boundary

**Что делает эта фаза:**
LLM в самом приложении использует **прошлые сессии аналитика** как контекст для текущего ответа. После N сессий вопрос «как ты вчера решал проблему с поручительствами?» → ответ ссылается на конкретный прошлый разговор, badge «📚 1 message» под ответом.

**Outcome:**
1. Аналитик открывает приложение, идёт в Settings → включает «Обучение на моих сессиях» (default OFF)
2. Backend background job индексирует все существующие сообщения через embeddings API
3. Каждое новое сообщение индексируется в течение 60 сек
4. Аналитик задаёт вопрос → orchestrator делает retrieve → если top-1 similarity ≥ 0.7 → встраивает 3 snippet'а в system prompt
5. Под ответом ассистента — badge «📚 N сообщений» с кликабельным списком источников

**Что НЕ доставляется:**
- Cross-user learning — Privacy violation, Out of Roadmap
- Auto-summarization старых сессий — Phase 11+
- Sharing context между MCP channels (разная бизнес-логика клиентов) — Phase 11+
- Fine-tuning отдельной модели на данных — не делаем (это другой уровень)
</domain>

<decisions>
## Implementation Decisions

### Path A vs Path B

**Path A: Anthropic Memory Tool API**
- ✅ Managed, нативный для Claude
- ❌ Работает ТОЛЬКО с Anthropic Claude
- ❌ Нарушает Multi-LLM requirement (MSG #11: «возможностью подключения к разным моделям по апи»)
- **Verdict: ❌ отказ**

**Path B: Собственный RAG (SQLite-vec + embeddings)**
- ✅ Работает с любым LLM (embeddings отдельный шаг)
- ✅ Локальный, нет внешних managed-сервисов
- ✅ Согласуется с privacy story (данные в `%APPDATA%`, никуда не уходят кроме embeddings API)
- ⚠️ Сложнее в реализации
- ⚠️ Нужен embedding-провайдер (cloud или self-hosted)
- **Verdict: ✅ выбран — Claude's discretion**

### Архитектура (Path B)

```
┌─────────────────────────────────────────────────┐
│ Background Job (1)                              │
│ Каждые 60 сек:                                  │
│  - SELECT id, content FROM messages             │
│    WHERE id NOT IN (SELECT message_id           │
│                     FROM message_embeddings)    │
│  - embedding = embeddings_api.embed(content)    │
│  - INSERT INTO message_embeddings ...           │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ SQLite-vec table (2)                            │
│ message_embeddings(message_id, embedding[N])    │
│ N = dim модели (1536 / 1024 / 768)              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼ retrieve
┌─────────────────────────────────────────────────┐
│ Orchestrator hook (3)                           │
│ POST /chat:                                     │
│  - if learn_enabled:                            │
│    snippets = await retrieve(message, top_k=5)  │
│    if snippets[0].similarity >= 0.7:            │
│      system_prompt += "\n\nНа основе ваших      │
│        прошлых сессий:\n" + format(snippets[:3])│
│  - SSE event 'learn_context' с массивом         │
│    использованных snippet'ов                    │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Frontend LearnContextBadge (4)                  │
│ <Badge>📚 {snippets.length}</Badge>             │
│ click → Popover со списком:                     │
│   - {session.title} (timestamp)                 │
│   - {snippet.preview} (100 chars)               │
│   - link to /sessions/{id}                      │
└─────────────────────────────────────────────────┘
```

### Embeddings provider (Claude's discretion)

**Default:** `text-embedding-3-small` (OpenAI) — 1536 dims, $0.02 / 1M tokens
**Альтернативы (можно поменять в Settings):**
- Yandex Embedding API (1024 dims)
- BGE-M3 self-hosted через Docker (1024 dims, бесплатно но медленно)
- OpenAI `text-embedding-3-large` (3072 dims, точнее но дороже)

Отдельная настройка в Settings секция «Embeddings» (independent от main LLM):
- endpoint URL
- model name
- api_key
- dimensions (auto-detect или explicit)

### Default: LEARN = OFF

**Claude's discretion:** opt-in, не opt-out.

Reason:
- Privacy-first — пользователь явно соглашается
- Embeddings API стоит денег (даже копейки) — не запускать без согласия
- Onboarding Step 3 (после MCP + LLM) показывает чекбокс «Включить обучение на моих сессиях» с описанием

### SQLite-vec vs SQLite-vss

**Claude's discretion:** `sqlite-vec` (преемник sqlite-vss).

Reason:
- sqlite-vss deprecated с 2024
- sqlite-vec поддерживается, активная разработка
- Python binding через `sqlite-vec` pip package
- Работает с PyInstaller (есть прецеденты)
</decisions>

<canonical_refs>
## Canonical References

### Project
- `phases/04-demo-refine/04-01-SUMMARY.md` — анонимизация (схожая концепция — backend перехватывает chat flow)
- `phases/02-mvp-chat/02-01-SUMMARY.md` — orchestrator loop (куда вкручивать retrieve hook)
- `backend/app/services/orchestrator.py` — главный chat loop
- `backend/app/storage/db.py` — миграции
- `.claude/memory/llm-providers.md` — Multi-LLM context

### External
- sqlite-vec: <https://github.com/asg017/sqlite-vec>
- OpenAI embeddings API: <https://platform.openai.com/docs/guides/embeddings>
- Yandex embeddings: <https://yandex.cloud/ru/docs/foundation-models/concepts/embeddings>
- BGE-M3: <https://huggingface.co/BAAI/bge-m3>
- Anthropic Memory Tool (для справки, не используем): <https://docs.anthropic.com/en/docs/build-with-claude/memory>
</canonical_refs>

<specifics>
## Specifics

### Migration v6 schema

```sql
-- Включить vec0 extension
SELECT vec_version();  -- check loaded

CREATE VIRTUAL TABLE IF NOT EXISTS message_embeddings USING vec0(
    message_id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]
);

-- Индекс по session_id для retrieve по сессии при необходимости
-- (vec0 не поддерживает обычные индексы — фильтр через JOIN на messages)

UPDATE schema_version SET version = 6;
```

### Migration v7 schema (Plan 10.3)

```sql
ALTER TABLE llm_settings ADD COLUMN learn_enabled BOOLEAN DEFAULT 0;
ALTER TABLE llm_settings ADD COLUMN embeddings_endpoint TEXT;
ALTER TABLE llm_settings ADD COLUMN embeddings_model TEXT DEFAULT 'text-embedding-3-small';
ALTER TABLE llm_settings ADD COLUMN embeddings_api_key_ref TEXT;  -- ref в sessionStorage, не value

UPDATE schema_version SET version = 7;
```

### Embeddings service (`backend/app/services/embeddings.py`)

```python
import httpx
from app.config import settings

class EmbeddingsService:
    def __init__(self, endpoint: str, model: str, api_key: str, dim: int = 1536):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.dim = dim
        self._client = httpx.AsyncClient(timeout=30.0, trust_env=False)

    async def embed(self, text: str) -> list[float]:
        r = await self._client.post(
            f"{self.endpoint}/embeddings",
            json={"model": self.model, "input": text},
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        result = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            r = await self._client.post(
                f"{self.endpoint}/embeddings",
                json={"model": self.model, "input": batch},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            result.extend([d["embedding"] for d in r.json()["data"]])
        return result
```

### Background indexing job (`backend/app/jobs/index_messages.py`)

```python
import asyncio
import structlog
from app.storage.db import DB
from app.services.embeddings import EmbeddingsService

logger = structlog.get_logger()

async def index_pending_messages(db: DB, emb: EmbeddingsService):
    rows = await db.execute(
        "SELECT m.id, m.content FROM messages m "
        "LEFT JOIN message_embeddings me ON me.message_id = m.id "
        "WHERE me.message_id IS NULL AND m.role IN ('user', 'assistant') "
        "LIMIT 100"
    )
    if not rows:
        return 0
    texts = [r["content"] for r in rows]
    embeddings = await emb.embed_batch(texts)
    for row, vec in zip(rows, embeddings):
        await db.execute(
            "INSERT INTO message_embeddings(message_id, embedding) VALUES (?, ?)",
            (row["id"], vec),
        )
    await db.commit()
    return len(rows)

async def run_indexing_loop(interval_sec: int = 60):
    while True:
        try:
            # check learn_enabled
            settings = await get_llm_settings()
            if not settings.learn_enabled:
                await asyncio.sleep(interval_sec)
                continue
            emb = EmbeddingsService(...)
            n = await index_pending_messages(db, emb)
            if n:
                logger.info("indexed_messages", count=n)
        except Exception as e:
            logger.error("indexing_failed", error=str(e))
        await asyncio.sleep(interval_sec)
```

### Retrieve API (`backend/app/routes/learn.py`)

```python
@router.post("/learn/retrieve")
async def retrieve_relevant(
    body: RetrieveRequest,  # query, channelId?, topK=5
    db: DB = Depends(get_db),
    settings: LLMSettings = Depends(get_llm_settings),
):
    if not settings.learn_enabled:
        return {"snippets": []}
    emb = build_embeddings_service(settings)
    query_vec = await emb.embed(body.query)
    rows = await db.execute(
        """
        SELECT m.id, m.session_id, m.content, m.created_at, s.title,
               vec_distance_cosine(me.embedding, ?) AS dist
        FROM message_embeddings me
        JOIN messages m ON m.id = me.message_id
        JOIN sessions s ON s.id = m.session_id
        WHERE m.role = 'assistant'
        ORDER BY dist
        LIMIT ?
        """,
        (json.dumps(query_vec), body.top_k),
    )
    return {
        "snippets": [
            {
                "messageId": r["id"],
                "sessionId": r["session_id"],
                "sessionTitle": r["title"],
                "snippet": r["content"][:500],
                "similarity": 1.0 - r["dist"],  # cosine distance → similarity
                "createdAt": r["created_at"],
            }
            for r in rows if r["dist"] < 0.3  # threshold ~ similarity ≥ 0.7
        ]
    }
```

### Orchestrator integration

В `app/services/orchestrator.py` перед LLM-вызовом:

```python
async def chat(session_id, message_text, ...):
    # ... existing code: load history, tools, etc.

    learn_context = ""
    if settings.learn_enabled:
        snippets = await retrieve_relevant(
            RetrieveRequest(query=message_text, channel_id=channel_id, top_k=5),
            db, settings,
        )
        if snippets["snippets"]:
            learn_context = "\n\nНа основе ваших прошлых сессий:\n" + "\n".join(
                f"— [{s['sessionTitle']}] {s['snippet'][:300]}..."
                for s in snippets["snippets"][:3]
            )
            await sse_send("learn_context", snippets["snippets"][:3])

    system_prompt = base_system_prompt + learn_context
    # ... continue with LLM call
```

### Frontend `LearnContextBadge` component

```tsx
"use client";
import { useState } from "react";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { BookOpen } from "lucide-react";
import Link from "next/link";

type Snippet = {
  messageId: number;
  sessionId: number;
  sessionTitle: string;
  snippet: string;
  similarity: number;
  createdAt: string;
};

export function LearnContextBadge({ snippets }: { snippets: Snippet[] }) {
  if (!snippets.length) return null;
  return (
    <Popover>
      <PopoverTrigger className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <BookOpen className="h-3 w-3" />
        Использовано {snippets.length} {snippets.length === 1 ? "сообщение" : "сообщения"} из прошлых сессий
      </PopoverTrigger>
      <PopoverContent className="w-96">
        <h4 className="font-medium mb-2">Источники контекста</h4>
        <ul className="space-y-2">
          {snippets.map((s) => (
            <li key={s.messageId} className="border-l-2 border-blue-500 pl-3">
              <Link href={`/sessions/${s.sessionId}`} className="text-sm font-medium hover:underline">
                {s.sessionTitle}
              </Link>
              <p className="text-xs text-muted-foreground mt-1">{s.snippet}...</p>
              <span className="text-xs text-muted-foreground">
                Релевантность: {(s.similarity * 100).toFixed(0)}%
              </span>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
```

### Caveat: sqlite-vec + PyInstaller

`sqlite-vec` использует native DLL — PyInstaller через `--add-binary` или `--collect-all sqlite_vec` соберёт. Verify через test PyInstaller bundle.

### Caveat: embeddings cost

При первом включении на 1000 сессий × 5 сообщений × 200 слов ≈ 1 млн токенов → $0.02 на OpenAI. Это копейки, но **показать пользователю предупреждение** при первом включении: «Будет проиндексировано N сообщений (~$X)».

### Caveat: privacy

`/learn/forget?sessionId=X` — удаляет embeddings конкретной сессии. `/learn/forget-all` — все embeddings. Reset local DB (Phase 9) тоже чистит embeddings.
</specifics>

<deferred>
## Deferred (НЕ в Phase 10)

- Auto-summarization старых сессий через LLM (отдельный flow) — Phase 11+
- Sharing context между MCP channels (cross-tenant учёт бизнес-логики) — Phase 11+
- Vector DB compaction / re-embedding при смене модели — v1.3+
- Семантический поиск в sidebar (отдельная фича) — v1.3+
- Multi-modal embeddings (картинки/скрины) — Out of Roadmap
- Reranking через LLM — Phase 11+ если retrieve unprecise
</deferred>

---
*Phase: 10-learn-engine*
*Context gathered: 2026-05-18 — yolo mode, Path B chosen, default LEARN=OFF (opt-in)*
