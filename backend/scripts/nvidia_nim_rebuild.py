"""NVIDIA NIM rebuild — массовая генерация эталонных карточек через build.nvidia.com.

Заменяет subagent-pipeline. Прямой OpenAI-compatible API, async параллелизм.

## Использование

```bash
# Тест 100 объектов
$env:NVIDIA_NIM_KEY = "nvapi-..."
python -m scripts.nvidia_nim_rebuild --limit 100 --model qwen/qwen3-next-80b-a3b-instruct

# Полный прогон 60k
python -m scripts.nvidia_nim_rebuild --all --model qwen/qwen3-next-80b-a3b-instruct
```

Скрипт:
1. Достаёт mock-объекты из pilot.db
2. Для каждого через build_card_context собирает compact context
3. Async parallel запросы к NIM (Semaphore=20)
4. Парсит JSON, сохраняет в claude-responses/ (формат совместим с apply_claude_batch)
5. Каждые 50 carts автоматически applies через apply_claude_batch

Checkpoint: при перезапуске пропускает уже обработанные объекты (is_mock=0).
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import aiosqlite
import httpx

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.knowledge.typical.card_context import build_card_context  # noqa: E402
from app.storage.migrations import apply_migrations  # noqa: E402
from scripts.prepare_claude_batch_compact import _compact_context  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("nvidia_nim_rebuild")

NIM_BASE = "https://integrate.api.nvidia.com/v1"
RESPONSES_DIR = (
    _BACKEND_ROOT.parent
    / ".planning"
    / "knowledge-layer-2026-05-24"
    / "phases"
    / "M-K2.5"
    / "claude-responses"
)
DB_PATH = _BACKEND_ROOT.parent / "data" / "pilot.db"

CHANNEL_DOMAIN = {
    "_bp30_138_24": "Бухгалтерия предприятия 3.0 (бухучёт, НУ, регл.отчётность, проводки, План счетов, регистры бухгалтерии, ЕНС/ЕНП)",
    "_ut115_17_226": "Управление торговлей 11.5 (продажи, закупки, склад, ценообразование, CRM, заказы, ВзаиморасчётыСКлиентами/Поставщиками)",
    "_ka2_25_92": "Комплексная автоматизация 2.5 (торговля+производство+бухучёт+кадры+казначейство, межфирменные операции)",
    "_erp25_21_118": "ERP Управление предприятием 2.5 (производство, MES, бюджетирование, МСФО, ремонты, ТОиР, ресурсные спецификации)",
}

SYSTEM_PROMPT = """Ты эксперт-методолог 1С. Получаешь метаданные одного объекта типовой конфигурации 1С и формируешь knowledge card в строгом JSON-формате.

Формат ответа — ТОЛЬКО валидный JSON, без markdown-обёрток:
{
  "summary": "100-200 символов кратко о назначении",
  "purpose": "200-500 символов: для чего, кто и когда использует, какое место в учётном контуре",
  "key_attributes": [{"name": "...", "role": "..."}],
  "movements": [{"register": "AccumulationRegister./AccountingRegister./InformationRegister./CalculationRegister.<имя>", "direction": "приход|расход|приход/расход|запись|", "condition": "..."}],
  "posting_flow": [],
  "typical_scenarios": ["..."],
  "preconditions": [],
  "related_objects": ["..."],
  "its_links": []
}

ПРАВИЛА:
- Всё на русском
- summary 100-200 chars
- purpose 200-500 chars
- movements ТОЛЬКО из item.writes_to (если writes_to пусто — movements []). Префикс канонический: AccumulationRegister./AccountingRegister./InformationRegister./CalculationRegister.
- direction строго один из: приход, расход, приход/расход, запись, пустая строка
- related_objects: top-3 из referenced_by
- key_attributes: топ-5 наиболее значимых атрибутов
- typical_scenarios: 2-3 кратких сценария использования
- Без преамбулы, БЕЗ объяснений, БЕЗ ```json — только JSON-объект."""


async def _resolve_mock_qnames(
    db: aiosqlite.Connection,
    channel_id: str,
    limit: int | None,
) -> list[str]:
    """Возвращает qname'ы mock-карточек в канале (отсортированные по приоритету)."""
    if limit is None:
        query = (
            "SELECT object_qualified_name FROM typical_object_cards "
            "WHERE channel_id = ? AND is_mock = 1"
        )
        args: tuple[Any, ...] = (channel_id,)
    else:
        query = (
            "SELECT object_qualified_name FROM typical_object_cards "
            "WHERE channel_id = ? AND is_mock = 1 LIMIT ?"
        )
        args = (channel_id, limit)
    cur = await db.execute(query, args)
    rows = await cur.fetchall()
    return [r[0] for r in rows]


def _build_user_prompt(compact: dict[str, Any], domain: str) -> str:
    """Компактный prompt: domain + JSON метаданных."""
    return (
        f"Конфигурация: {domain}\n\n"
        f"Метаданные объекта:\n{json.dumps(compact, ensure_ascii=False, separators=(',', ':'))}\n\n"
        f"Сгенерируй knowledge card."
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Достать JSON-объект из ответа LLM (с/без markdown)."""
    text = text.strip()
    if text.startswith("```"):
        # markdown fence
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.startswith("json"):
            text = text[4:].lstrip()
    # Найди первую { и последнюю }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _source_hash(compact: dict[str, Any]) -> str:
    """Стабильный hash для apply_claude_batch."""
    h = hashlib.sha256(json.dumps(compact, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:16]


async def _call_nim(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    user_prompt: str,
    *,
    max_retries: int = 3,
) -> str | None:
    """Один запрос к NIM. Возвращает текст ответа или None при провале."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await client.post(
                f"{NIM_BASE}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            if resp.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                log.warning("NIM %s — retry в %ds", resp.status_code, wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as e:
            last_err = e
            wait = 3 * (attempt + 1)
            log.warning("NIM call error: %s — retry в %ds", e, wait)
            await asyncio.sleep(wait)
    log.error("NIM exhausted retries: %s", last_err)
    return None


async def _process_one(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    api_key: str,
    model: str,
    channel_id: str,
    qname: str,
    domain: str,
) -> dict[str, Any] | None:
    """Обработать один объект: context -> NIM -> parse -> item."""
    async with sem:
        try:
            ctx = await build_card_context(
                db, channel_id=channel_id, object_qualified_name=qname
            )
        except Exception as e:
            log.error("build_card_context fail %s: %s", qname, e)
            return None
        if ctx is None:
            return None
        ctx_dict = dataclasses.asdict(ctx) if dataclasses.is_dataclass(ctx) else dict(ctx)
        compact = _compact_context(ctx_dict)
        user_prompt = _build_user_prompt(compact, domain)

        raw = await _call_nim(client, api_key, model, user_prompt)
        if raw is None:
            return None
        card = _extract_json(raw)
        if card is None:
            log.error("Bad JSON для %s: %s", qname, raw[:200])
            return None
        return {
            "qname": qname,
            "source_hash": _source_hash(compact),
            "card": card,
        }


async def amain(args: argparse.Namespace) -> int:
    api_key = os.environ.get("NVIDIA_NIM_KEY") or args.api_key
    if not api_key:
        log.error("Set $env:NVIDIA_NIM_KEY or --api-key")
        return 2

    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    try:
        await apply_migrations(db)

        channels = list(CHANNEL_DOMAIN.keys()) if args.all else [args.channel_id]
        if not channels or (not args.all and not args.channel_id):
            log.error("Need --channel-id or --all")
            return 2

        total_done = 0
        sem = asyncio.Semaphore(args.concurrency)

        async with httpx.AsyncClient() as client:
            for channel_id in channels:
                if channel_id not in CHANNEL_DOMAIN:
                    log.error("Unknown channel: %s", channel_id)
                    continue
                domain = CHANNEL_DOMAIN[channel_id]

                limit = args.limit if args.limit and not args.all else None
                qnames = await _resolve_mock_qnames(db, channel_id, limit)
                log.info("Channel %s: %d mock objects to process", channel_id, len(qnames))
                if not qnames:
                    continue

                # Чанки по chunk_size для частичной выгрузки
                chunk_size = args.chunk_size
                for chunk_idx in range(0, len(qnames), chunk_size):
                    chunk_qnames = qnames[chunk_idx : chunk_idx + chunk_size]
                    chunk_no = chunk_idx // chunk_size + 1
                    t0 = time.time()

                    tasks = [
                        _process_one(sem, client, db, api_key, args.model, channel_id, q, domain)
                        for q in chunk_qnames
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=False)
                    items = [r for r in results if r]
                    failed = len(chunk_qnames) - len(items)

                    out_path = (
                        RESPONSES_DIR
                        / f"response-nim-{channel_id.strip('_')}-chunk{chunk_no:04d}.json"
                    )
                    payload = {
                        "channel_id": channel_id,
                        "generated_by": f"nvidia-nim:{args.model}",
                        "prompt_version": "v3-nim-direct",
                        "items": items,
                    }
                    out_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    dt = time.time() - t0
                    total_done += len(items)
                    log.info(
                        "[%s chunk %d/%d] ok=%d fail=%d %.1fs total=%d",
                        channel_id,
                        chunk_no,
                        (len(qnames) + chunk_size - 1) // chunk_size,
                        len(items),
                        failed,
                        dt,
                        total_done,
                    )

                    if args.apply_immediately and items:
                        import subprocess

                        proc = subprocess.run(
                            [
                                sys.executable,
                                "-m",
                                "scripts.apply_claude_batch",
                                "--response",
                                str(out_path),
                                "--confirm",
                            ],
                            cwd=str(_BACKEND_ROOT),
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                        )
                        if proc.returncode == 0:
                            log.info("Applied chunk %d in DB", chunk_no)
                        else:
                            log.error("apply failed: %s", proc.stderr[-500:])

        log.info("DONE. Total %d carts processed.", total_done)
        return 0
    finally:
        await db.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db-path", default=str(DB_PATH))
    p.add_argument("--channel-id", help="_bp30_138_24 / _ut115_17_226 / _ka2_25_92 / _erp25_21_118")
    p.add_argument("--all", action="store_true", help="Все 4 канала подряд")
    p.add_argument("--limit", type=int, default=None, help="Тест-режим: только N объектов")
    p.add_argument("--model", default="qwen/qwen3-next-80b-a3b-instruct")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--chunk-size", type=int, default=50)
    p.add_argument(
        "--apply-immediately",
        action="store_true",
        help="После каждого chunk применить в БД (требует apply_response_file API)",
    )
    p.add_argument("--api-key", help="Если не задан env NVIDIA_NIM_KEY")
    args = p.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
