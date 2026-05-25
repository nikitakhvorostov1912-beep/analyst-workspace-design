# ADR-001: Vector storage — sqlite-vec

**Status:** Accepted
**Date:** 2026-05-25
**Deciders:** Никита, Claude
**Phase:** M-K1

## Context

Knowledge Layer требует semantic search по:
- ИТС стандартам (~317 .md из v8std, ~3 MB текста)
- БСП API (~3000 методов из ssl_3_1 + ssl_3_2, ~10 MB)
- Code patterns / antipatterns (топ-100, ~500 KB)
- Reference configurations metadata (5 typical: УТ/ERP/КА/БГУ/ЗУП)

**Объём:** до 10K-50K embeddings (768d при BGE-M3).
**Latency бюджет:** <100ms на retrieve top-k (k=5..20) — критично для chat UX.
**Constraint:** Electron desktop deployment — никаких внешних серверов.
**Constraint:** один файл БД на каналу (`~/.analyst-1c/knowledge/<fingerprint>/`).

## Decision

Использовать **sqlite-vec** (https://github.com/asg017/sqlite-vec) — vector
search extension для SQLite.

- Хранение: float32 BLOB в обычной SQLite-таблице, vec0 virtual table для KNN
- Distance: cosine (нормализованные эмбеддинги от BGE-M3)
- Дистрибуция: 1 .dll/.dylib/.so файл ~500 KB, загружается через `SELECT load_extension(...)`
- Bundling в Electron: положить рядом с backend.exe (PyInstaller `--add-binary`)

## Consequences

### Положительные
- **Zero infra**: SQLite already in stack для sessions/connections — vector тоже в одной БД
- **Один файл = одна конфигурация**: per-config snapshot работает атомарно
- **MIT license**: совместим с Apache 2.0 core
- **Latency 5-30ms** для 10K векторов на CPU (бенчи asg017) — укладываемся в budget
- **Pickle-free**: BLOB в SQLite, не Python-specific

### Отрицательные
- **Embeddings re-index при изменении модели** — нужно явное versioning (см. ADR-003)
- **No HNSW** (только brute-force через SIMD) — потолок ~100K векторов на одну таблицу.
  Для нашего scope OK, но плохо масштабируется на enterprise CMDB (out of M-K0..M-K6 scope).
- **Расширение нужно `load_extension(1)`** — некоторые managed Python distributions это запрещают.
  Для нашего PyInstaller bundle — не проблема.

### Нейтральные
- Альтернатива FAISS требовала бы отдельной in-memory store + ручной persist цикл

## Alternatives considered

| Alt | Verdict | Reason |
|---|---|---|
| **FAISS** (Meta) | rejected | In-memory only, требует ручной persist/load, не SQLite-native |
| **Chroma** | rejected | Heavy dependency (~50 MB wheel), client-server architecture даже в embedded mode |
| **Qdrant embedded** | rejected | Раздувает Electron bundle до 200+ MB, overhead не оправдан для 10K векторов |
| **pgvector** | rejected | Требует PostgreSQL — не подходит для desktop deployment |
| **LanceDB** | rejected | Apache 2.0 OK, но raw Rust binding для Windows ~50 MB и менее зрелый чем sqlite-vec |
| **Numpy + ручной brute-force** | rejected | Будет работать до 5K, но потом нужен SIMD и proper KNN — лучше сразу sqlite-vec |

## References

- https://github.com/asg017/sqlite-vec
- Бенчи: 10K × 768d cosine top-k=10 → ~15ms на M1, ~25ms на i7
- Будет использоваться в `backend/app/knowledge/vector_store.py` (создаётся в M-K2)
- См. также ADR-003 (выбор embeddings model) и ADR-002 (граф через CTE, не Neo4j)
