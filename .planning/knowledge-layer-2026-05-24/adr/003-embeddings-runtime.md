# ADR-003: Embeddings runtime — FastEmbed + BGE-M3

**Status:** Accepted
**Date:** 2026-05-25
**Deciders:** Никита, Claude
**Phase:** M-K1

## Context

Knowledge Layer нуждается в **локальном** embeddings runtime для:
- Индексации корпусов (ИТС, БСП API, code patterns) при `/connections` POST
  — без отправки в облако (privacy)
- Runtime query embeddings при retrieval (chat input → vector)
- Перевычисления при обновлении модели

**Constraints:**
- **Multilingual обязателен**: ИТС/БСП — русский, code — русский+английский+1С
- **CPU-only** (Electron desktop, не у всех GPU)
- **Cold-start < 5 сек** (UX баг иначе)
- **Bundle size**: ≤ 300 MB на модель (Electron installer уже 100+ MB)
- **License**: совместима с Apache 2.0 core

## Decision

Использовать **FastEmbed** (https://github.com/qdrant/fastembed) с моделью
**BAAI/bge-m3** (sentence-transformers).

- Runtime: ONNX (через FastEmbed) → CPU-only inference
- Модель: BGE-M3 (multilingual, 1024d, ~570 MB ONNX)
- Bundling: модель **скачивается при первом запуске** (не в installer)
  → installer остаётся ≤ 150 MB
- Storage: `~/.analyst-1c/models/bge-m3/` (один раз для всех каналов)

## Consequences

### Положительные
- **No GPU required**: BGE-M3 на CPU ~50-100 ms на batch 32 текстов
- **Apache 2.0 license**: BGE-M3 от BAAI, FastEmbed Apache 2.0 — clean
- **Multilingual из коробки**: 100+ языков, в т.ч. русский на уровне специализированных
- **ONNX runtime ~20 MB** — лёгкий относительно torch (~500 MB)
- **Лидер MTEB Retrieval** среди open-source multilingual (state на 2026-05)
- **1024d вектор**: больше чем 384d у MiniLM, но лучше recall

### Отрицательные
- **570 MB модель скачивается при первом запуске** — нужен прогресс-бар + retry
- **Cold-start ~3-5 сек** при первой загрузке модели в RAM (subsequent ~100 ms cached)
- **RAM footprint ~1.5 GB** во время inference (для batch 64) — узкое место на
  машинах 4 GB RAM, но мы целимся в developers (8-16 GB norm)
- **Reindex при upgrade модели** — нужно явное `model_version` поле в SQLite
  schema, см. ADR-005

### Нейтральные
- Альтернатива OpenAI API дала бы меньше bundle, но нарушает privacy claim

## Alternatives considered

| Alt | Verdict | Reason |
|---|---|---|
| **OpenAI text-embedding-3-small** | rejected | Cloud API нарушает privacy, $0.02/1M токенов накапливается, blocked в РФ |
| **sentence-transformers + torch** | rejected | Bundle +500 MB torch, медленнее cold-start, та же модель но heavy runtime |
| **paraphrase-multilingual-MiniLM-L12-v2** | considered | 384d, 130 MB — компактнее, но retrieval quality на русском заметно хуже (MTEB) |
| **multilingual-e5-large** | considered | Apache 2.0, 1024d, ~1.1 GB — сопоставимо качество, больше bundle |
| **OllamaEmbeddings** | rejected | Требует отдельный Ollama daemon, double install для user — против UX |
| **Custom-fine-tuned-1C** | rejected | Out of scope, нет датасета для fine-tuning, в M-K5+ при необходимости |

## References

- FastEmbed: https://github.com/qdrant/fastembed
- BGE-M3 paper: https://arxiv.org/abs/2402.03216
- MTEB Retrieval ru: BGE-M3 ranks top-3 для русского (state на 2026-05)
- Будет в `backend/app/knowledge/embeddings.py` (создаётся в M-K2)
- См. также ADR-001 (sqlite-vec для storage) и ADR-005 (migrations для model_version)
