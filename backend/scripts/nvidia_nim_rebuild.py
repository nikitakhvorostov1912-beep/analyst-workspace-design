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
from scripts.apply_claude_batch import apply_batch  # noqa: E402
from scripts.prepare_claude_batch_compact import _compact_context  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("nvidia_nim_rebuild")

NIM_BASE = "https://integrate.api.nvidia.com/v1"

# Provider presets — OpenAI-compatible endpoints
PROVIDER_PRESETS = {
    "nim": {
        "endpoint": "https://integrate.api.nvidia.com/v1",
        "default_model": "qwen/qwen3.5-122b-a10b",
    },
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "endpoint": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat-v3:free",
    },
    "cerebras": {
        "endpoint": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
    },
    "gemini": {
        # OpenAI-compat shim
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
    },
    "huggingface": {
        # HuggingFace Inference Providers router (OpenAI-compat).
        # Модель формата "owner/model:provider" (provider: novita/together/fireworks/sambanova/etc).
        "endpoint": "https://router.huggingface.co/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct:novita",
    },
}
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
- summary МИНИМУМ 110 символов (не короче!), до 220
- purpose МИНИМУМ 240 символов (не короче!), до 500
- movements ТОЛЬКО из item.writes_to (если writes_to пусто — movements []). Префикс канонический: AccumulationRegister./AccountingRegister./InformationRegister./CalculationRegister.
- direction строго один из: приход, расход, приход/расход, запись, пустая строка

КРИТИЧНО — related_objects:
- Если input.referenced_by НЕ пуст — ОБЯЗАТЕЛЬНО скопируй первые 3 имени в related_objects.
- Пример: input.referenced_by=["Document.РеализацияТоваровУслуг","Document.ВозвратТоваровОтПокупателя","CommonModule.Продажи"] → related_objects=["Document.РеализацияТоваровУслуг","Document.ВозвратТоваровОтПокупателя","CommonModule.Продажи"].
- Если input.referenced_by пуст или отсутствует — related_objects:[].
- НЕ выдумывай имена которых нет в input.referenced_by.

КРИТИЧНО — key_attributes:
- key_attributes — это РЕАЛЬНЫЕ реквизиты объекта (из input.attrs), а не мета-поля JSON ("name", "kind", "qname", "handlers", "comment")
- Если input.attrs пустой → key_attributes:[]
- Для CommonCommand/CommonModule/CommonForm/Subsystem/Role/HTTPService и других объектов БЕЗ собственных реквизитов → key_attributes:[]
- НИКОГДА не выдумывай атрибуты («Имя», «Тип», «Доступность», «Ссылка», «Назначение») — если реальных нет, оставь массив пустым
- Топ-5 наиболее значимых реквизитов с осмысленной ролью (бизнес-смысл, не техническая роль)

- typical_scenarios: РОВНО 3 конкретных сценария использования (минимум 2, лучше 3)
- preconditions: 1-3 предусловия если уместно, иначе []
- Без преамбулы, БЕЗ объяснений, БЕЗ ```json — только JSON-объект."""

# Мета-поля JSON-payload, которые модель НЕ должна включать в key_attributes
_META_FIELDS_BLACKLIST = {
    "name",
    "kind",
    "qname",
    "handlers",
    "comment",
    "type",
    "имя",
    "тип",
    "комментарий",
    "обработчики",
}

# Типы метаданных БЕЗ собственных реквизитов — key_attributes ВСЕГДА пуст
_NO_ATTR_KINDS = {
    "CommonCommand",
    "CommonModule",
    "CommonForm",
    "CommandGroup",
    "Subsystem",
    "HTTPService",
    "WebService",
    "Style",
    "StyleItem",
    "FunctionalOption",
    "FunctionalOptionsParameter",
    "EventSubscription",
    "ScheduledJob",
    "Constant",
    "SessionParameter",
    "Language",
    "Interface",
    "Role",
    "WSReference",
    "XDTOPackage",
}


async def _resolve_mock_qnames(
    db: aiosqlite.Connection,
    channel_id: str,
    limit: int | None,
    offset: int = 0,
) -> list[str]:
    """Возвращает qname'ы mock-карточек в канале (отсортированные по приоритету).

    offset позволяет разделить работу между несколькими параллельными
    процессами на одном канале (SQLite требует LIMIT перед OFFSET, поэтому
    при offset>0 без limit используем LIMIT -1).
    """
    query = (
        "SELECT object_qualified_name FROM typical_object_cards "
        "WHERE channel_id = ? AND is_mock = 1 ORDER BY object_qualified_name"
    )
    params: list[Any] = [channel_id]
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    elif offset:
        query += " LIMIT -1"
    if offset:
        query += " OFFSET ?"
        params.append(offset)
    cur = await db.execute(query, tuple(params))
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
    max_tokens: int = 1100,
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
        "max_tokens": max_tokens,
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
                f"{_ENDPOINT}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120.0,
            )
            if resp.status_code in (429, 503):
                wait = 5 * (attempt + 1)
                log.warning("NIM %s — retry в %ds", resp.status_code, wait)
                await asyncio.sleep(wait)
                continue
            if resp.status_code in (500, 502, 504):
                wait = 3 * (attempt + 1)
                log.warning("NIM %s — retry в %ds", resp.status_code, wait)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                log.debug("NIM empty choices, skip: %s", str(data)[:200])
                return None
            msg = choices[0].get("message") or {}
            finish = choices[0].get("finish_reason", "")
            content = msg.get("content")
            if content is None or content == "":
                # content filter / refusal / empty completion — НЕ retry, объект пропускаем
                log.debug(
                    "NIM no content (finish=%s), skip", finish or "unknown"
                )
                return None
            return content
        except httpx.TimeoutException as e:
            last_err = e
            wait = 5 * (attempt + 1)
            log.warning("NIM timeout — retry в %ds", wait)
            await asyncio.sleep(wait)
        except httpx.HTTPError as e:
            last_err = e
            wait = 3 * (attempt + 1)
            log.warning("NIM HTTP error: %s — retry в %ds", type(e).__name__, wait)
            await asyncio.sleep(wait)
        except (KeyError, IndexError, ValueError) as e:
            # Парсинг JSON / неожиданный формат ответа — НЕ retry
            log.debug("NIM bad response shape: %s", e)
            return None
    log.error("NIM exhausted retries: %s", type(last_err).__name__ if last_err else "unknown")
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
    *,
    max_tokens: int = 1100,
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

        raw = await _call_nim(client, api_key, model, user_prompt, max_tokens=max_tokens)
        if raw is None:
            return None
        card = _extract_json(raw)
        if card is None:
            log.error("Bad JSON для %s: %s", qname, raw[:200])
            return None
        # Post-process key_attributes
        kind = compact.get("kind", "")
        if kind in _NO_ATTR_KINDS:
            # Для CommonCommand/Module/Form/Subsystem/etc. — атрибутов БЫТЬ НЕ МОЖЕТ
            card["key_attributes"] = []
        elif isinstance(card.get("key_attributes"), list):
            cleaned: list = []
            for kv in card["key_attributes"]:
                if not isinstance(kv, dict):
                    continue
                nm = (kv.get("name") or "").strip()
                if not nm:
                    continue
                low = nm.lower()
                if low in _META_FIELDS_BLACKLIST:
                    continue
                cleaned.append(kv)
            card["key_attributes"] = cleaned

        # Post-process related_objects (fix 2026-05-28):
        # NIM/qwen часто игнорирует правило "скопируй из referenced_by"
        # и оставляет [] даже когда вход непустой. Подстраховка: если модель
        # вернула пусто, а в input.referenced_by есть имена — берём top-3.
        ref_in = compact.get("referenced_by") or []
        related_out = card.get("related_objects")
        if isinstance(ref_in, list) and ref_in and (
            not isinstance(related_out, list) or len(related_out) == 0
        ):
            card["related_objects"] = list(ref_in[:3])
        return {
            "qname": qname,
            "source_hash": _source_hash(compact),
            "card": card,
        }


async def amain(args: argparse.Namespace) -> int:
    env_var = {
        "nim": "NVIDIA_NIM_KEY",
        "groq": "GROQ_KEY",
        "openrouter": "OPENROUTER_KEY",
        "cerebras": "CEREBRAS_KEY",
        "gemini": "GEMINI_KEY",
        "huggingface": "HF_KEY",
    }[args.provider]
    api_key = args.api_key or os.environ.get(env_var)
    if not api_key:
        log.error("Set $env:%s or --api-key", env_var)
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

        # HTTP/2 multiplexing + keepalive pool. NIM поддерживает HTTP/2.
        async with httpx.AsyncClient(
            http2=True,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=30,
                keepalive_expiry=30.0,
            ),
            timeout=httpx.Timeout(120.0, connect=10.0),
        ) as client:
            for channel_id in channels:
                if channel_id not in CHANNEL_DOMAIN:
                    log.error("Unknown channel: %s", channel_id)
                    continue
                domain = CHANNEL_DOMAIN[channel_id]

                limit = args.limit if args.limit and not args.all else None
                qnames = await _resolve_mock_qnames(db, channel_id, limit, args.offset)
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
                        _process_one(sem, client, db, api_key, args.model, channel_id, q, domain, max_tokens=args.max_tokens)
                        for q in chunk_qnames
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=False)
                    items = [r for r in results if r]
                    failed = len(chunk_qnames) - len(items)

                    out_path = (
                        RESPONSES_DIR
                        / f"response-{_PROVIDER_TAG}-{channel_id.strip('_')}-chunk{chunk_no:04d}.json"
                    )
                    payload = {
                        "channel_id": channel_id,
                        "generated_by": f"{_PROVIDER_TAG}:{args.model}",
                        "prompt_version": "v3-provider-direct",
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
                        # Bug A fix (2026-05-28): inline apply через общий db
                        # коннект — избегаем DB lock от concurrent subprocess.
                        try:
                            apply_stats = await apply_batch(db, out_path)
                            log.info(
                                "Applied chunk %d: ok=%d fail=%d valid=%d issues=%d",
                                chunk_no,
                                apply_stats["applied"],
                                apply_stats["failed"],
                                apply_stats["validation_valid"],
                                apply_stats["validation_issues"],
                            )
                        except Exception as exc:  # noqa: BLE001
                            log.error("apply failed chunk %d: %s", chunk_no, exc)

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
    p.add_argument("--offset", type=int, default=0, help="Смещение в mock-списке (для split между процессами)")
    p.add_argument(
        "--provider",
        default="nim",
        choices=list(PROVIDER_PRESETS.keys()),
        help="OpenAI-compat провайдер: nim/groq/openrouter/cerebras/gemini/huggingface",
    )
    p.add_argument("--model", default=None, help="Если не задан — берёт default_model провайдера")
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--chunk-size", type=int, default=50)
    p.add_argument("--max-tokens", type=int, default=1100, help="max completion tokens (tradeoff: latency vs cutoff)")
    p.add_argument(
        "--apply-immediately",
        action="store_true",
        help="После каждого chunk применить в БД через apply_claude_batch",
    )
    p.add_argument(
        "--api-key",
        help="Если не задан, читаем из env: NVIDIA_NIM_KEY / GROQ_KEY / OPENROUTER_KEY / CEREBRAS_KEY / GEMINI_KEY",
    )
    args = p.parse_args()

    # Init globals для _call_nim
    global _ENDPOINT, _PROVIDER_TAG
    preset = PROVIDER_PRESETS[args.provider]
    _ENDPOINT = preset["endpoint"]
    _PROVIDER_TAG = args.provider
    if args.model is None:
        args.model = preset["default_model"]

    return asyncio.run(amain(args))


_ENDPOINT: str = NIM_BASE
_PROVIDER_TAG: str = "nim"


if __name__ == "__main__":
    sys.exit(main())
