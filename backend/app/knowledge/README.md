# `backend/app/knowledge/` — Knowledge Layer Module

**Created:** 2026-05-25 (M-K1.3 pre-flight skeleton)
**Phase ownership:** M-K1 (skeleton) → M-K2 (storage + indexer) → M-K3 (graph) → M-K4 (behavioral) → M-K5 (predictive)

## Назначение

Knowledge Layer — модуль предоставляющий **per-configuration** базы знаний для
ответов на 6 уровней вопросов о 1С-системе пользователя.

## Структура

```
backend/app/knowledge/
├── __init__.py           ← Public API (re-export)
├── README.md             ← этот файл
├── types.py              ← Базовые типы (KnowledgeMode, ObjectPath, etc.)
├── fingerprint.py        ← Configuration Fingerprint (M-K1.5)
├── storage.py            ← Per-config layout (M-K1.4)
├── metadata_cache.py     ← L1 Metadata cache filler (M-K1.12, TBD)
├── dossier.py            ← Object Dossier API (M-K1.13, TBD)
├── vector_store.py       ← L5 sqlite-vec wrapper (M-K2, TBD)
├── embeddings.py         ← FastEmbed + BGE-M3 (M-K2, TBD)
├── indexer.py            ← Indexer Pipeline X-1..X-4 (M-K2, TBD)
├── graph_store.py        ← L2 SQLite + CTE graph (M-K3, TBD)
├── rulebook/             ← L4 Diagnose Engine YAML (M-K3, PROPRIETARY)
└── corpora/              ← Bundled / cached corpora
    ├── v8std/            ← Cached sfaqer ИТС (M-K2)
    └── proprietary/      ← Reference Library (M-K5, PROPRIETARY)
```

## Текущий статус (M-K1.3)

Создан **skeleton** — только базовые типы и фабрики без бизнес-логики.
Логика добавляется атомарными коммитами в M-K1.4+ согласно плану.

| File | Created in | Has logic? |
|---|---|---|
| `__init__.py` | M-K1.3 | re-export only |
| `types.py` | M-K1.3 | Pydantic types + Literal aliases |
| `storage.py` | M-K1.4 | YES |
| `fingerprint.py` | M-K1.5 | YES |
| остальные | M-K2+ | TBD |

## Конвенции

1. **No global state** — все объекты создаются через factory functions
   (`get_storage(channel_id)`) или DI в FastAPI endpoints
2. **Per-channel isolation** — каждый канал получает свой `KnowledgeStorage`
   с собственным fingerprint'ом и path
3. **Async-friendly** — все I/O операции через `asyncio` (`aiosqlite`,
   `aiofiles`)
4. **Type-safe** — Pydantic v2 models + Literal/Final, без `Any` в публичном API
5. **Read-only by default** — методы знают как читать, modify pathways
   защищены `@requires_write` декоратором (TBD M-K2.5)

## Безопасность

- **Path traversal:** `storage.py` валидирует что все paths внутри root
- **Encoding:** все файлы UTF-8 (without BOM), enforce при write
- **Permissions:** на Unix — `0o700` (только owner) для knowledge каталогов
- **PII:** в metadata_cache не хранятся данные базы (только структура);
  embeddings — над публичными корпусами (ИТС, БСП), не пользовательскими
  данными

## Тесты

`backend/tests/test_knowledge_*.py` — по одному файлу на каждый модуль.

См. `backend/tests/test_knowledge_storage.py` (M-K1.4),
`backend/tests/test_knowledge_fingerprint.py` (M-K1.5).

## Документация ссылок

- Architecture: `.planning/knowledge-layer-2026-05-24/PLAN.md`
- ADR: `.planning/knowledge-layer-2026-05-24/adr/`
- M-K1 phase plan: `.planning/knowledge-layer-2026-05-24/phases/M-K1/M-K1-PLAN.md`
