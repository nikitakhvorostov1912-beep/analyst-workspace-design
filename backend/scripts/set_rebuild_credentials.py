"""CLI управление credentials для real LLM rebuild карточек (M-K2.5.10.3).

Сохраняет endpoint + model + api_key через AES-GCM зашифрованное
хранилище `user_secrets` (P2.1). Ключ НИКОГДА не попадает в:
- argv (используется getpass для stdin без echo)
- логи (всегда маскируется первые/последние 4 символа)
- БД в plain text (AES-GCM с ключом из app_master_key)

## Использование

```bash
# Установить credentials (api-key вводится через stdin, не в argv):
python -m scripts.set_rebuild_credentials set \\
    --endpoint "https://api.deepseek.com/v1" \\
    --model "deepseek-chat"
# > Введите API ключ: ****

# Показать (с маской ключа):
python -m scripts.set_rebuild_credentials show

# Удалить:
python -m scripts.set_rebuild_credentials delete

# Тестовый call с сохранёнными credentials:
python -m scripts.set_rebuild_credentials test
```

## Контракт хранения

provider_id = "typical_cards_rebuild"
value = JSON {"endpoint": str, "model": str, "api_key": str}

Один provider_id, одна зашифрованная запись. Атомарная update.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

# Backend root в path для импортов при `python -m scripts.xxx`
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.storage.migrations import apply_migrations  # noqa: E402
from app.storage.user_secrets_store import (  # noqa: E402
    delete_secret,
    get_secret,
    save_secret,
)

logger = logging.getLogger("set_rebuild_credentials")


REBUILD_PROVIDER_ID = "typical_cards_rebuild"


@dataclass
class RebuildCredentials:
    endpoint: str
    model: str
    api_key: str

    def masked_api_key(self) -> str:
        """Маскированный ключ для отображения: «sk-xxx****ym49» (первые 5 + ****  + последние 4)."""
        if not self.api_key or len(self.api_key) < 12:
            return "****"
        return f"{self.api_key[:5]}****{self.api_key[-4:]}"

    def to_json(self) -> str:
        return json.dumps({
            "endpoint": self.endpoint,
            "model": self.model,
            "api_key": self.api_key,
        })

    @classmethod
    def from_json(cls, raw: str) -> "RebuildCredentials":
        d = json.loads(raw)
        return cls(endpoint=d["endpoint"], model=d["model"], api_key=d["api_key"])


async def load_rebuild_credentials(
    db: aiosqlite.Connection,
) -> RebuildCredentials | None:
    """Прочитать сохранённые credentials из user_secrets. None если нет."""
    raw = await get_secret(db, REBUILD_PROVIDER_ID)
    if raw is None:
        return None
    try:
        return RebuildCredentials.from_json(raw)
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Не удалось распарсить credentials: %s", e)
        return None


async def save_rebuild_credentials(
    db: aiosqlite.Connection,
    credentials: RebuildCredentials,
) -> None:
    """Сохранить credentials (AES-GCM шифрование)."""
    await save_secret(db, REBUILD_PROVIDER_ID, credentials.to_json())


# ─── CLI commands ────────────────────────────────────────────────────


async def cmd_set(args: argparse.Namespace) -> int:
    """Установить или обновить credentials."""
    api_key = getpass.getpass("Введите API ключ (не отображается): ")
    if not api_key.strip():
        print("ОШИБКА: пустой API ключ", file=sys.stderr)
        return 1
    creds = RebuildCredentials(
        endpoint=args.endpoint.rstrip("/"),
        model=args.model,
        api_key=api_key.strip(),
    )
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        await save_rebuild_credentials(db, creds)
        print(f"✓ Credentials сохранены для provider_id={REBUILD_PROVIDER_ID!r}")
        print(f"  Endpoint: {creds.endpoint}")
        print(f"  Model:    {creds.model}")
        print(f"  API key:  {creds.masked_api_key()}")
    finally:
        await db.close()
    return 0


async def cmd_show(args: argparse.Namespace) -> int:
    """Показать credentials (с маской ключа)."""
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        creds = await load_rebuild_credentials(db)
    finally:
        await db.close()

    if creds is None:
        print("Credentials не установлены. Используй 'set' чтобы добавить.")
        return 1

    print(f"provider_id = {REBUILD_PROVIDER_ID}")
    print(f"  Endpoint: {creds.endpoint}")
    print(f"  Model:    {creds.model}")
    print(f"  API key:  {creds.masked_api_key()}")
    return 0


async def cmd_delete(args: argparse.Namespace) -> int:
    """Удалить credentials."""
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        existed = await delete_secret(db, REBUILD_PROVIDER_ID)
    finally:
        await db.close()

    if existed:
        print(f"✓ Credentials удалены для {REBUILD_PROVIDER_ID!r}")
        return 0
    print("Credentials не были установлены. Ничего не удалено.")
    return 1


async def cmd_test(args: argparse.Namespace) -> int:
    """Тестовый вызов LLM с сохранёнными credentials."""
    db = await aiosqlite.connect(args.db_path)
    try:
        await apply_migrations(db)
        creds = await load_rebuild_credentials(db)
    finally:
        await db.close()

    if creds is None:
        print("Credentials не установлены. Используй 'set' сначала.", file=sys.stderr)
        return 1

    from app.knowledge.typical.openai_compat_llm_caller import (  # noqa: PLC0415
        LLMCallError,
        OpenAICompatLLMCaller,
    )

    print(f"Тестовый вызов:")
    print(f"  Endpoint: {creds.endpoint}")
    print(f"  Model:    {creds.model}")
    print(f"  API key:  {creds.masked_api_key()}")
    print()

    caller = OpenAICompatLLMCaller(
        endpoint=creds.endpoint,
        model=creds.model,
        api_key=creds.api_key,
        max_retries=1,  # Для быстрого теста — 1 попытка
        request_json_object=False,  # Не все провайдеры это поддерживают
    )
    try:
        response = await caller.complete([
            {"role": "system", "content": "Ты — ассистент. Отвечай кратко."},
            {"role": "user", "content": "Скажи 'тест успешен' одним предложением."},
        ])
        print(f"✓ Ответ получен ({response.tokens_in} in + {response.tokens_out} out tokens):")
        print(f"  {response.content!r}")
        print()
        print(f"Cost: ${caller.telemetry.total_cost_usd:.6f} USD")
        print(f"Latency: {caller.telemetry.avg_latency_s:.2f}s")
        return 0
    except LLMCallError as e:
        print(f"✗ ОШИБКА LLM call: {e}", file=sys.stderr)
        if e.status:
            print(f"  HTTP status: {e.status}", file=sys.stderr)
        if e.body:
            print(f"  Body: {e.body[:300]}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"✗ Неожиданная ошибка: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


# ─── Argparse ────────────────────────────────────────────────────────


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Управление LLM credentials для real card rebuild (M-K2.5.10).",
    )
    parser.add_argument(
        "--db-path",
        default="C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db",
        help="Путь к SQLite БД",
    )
    parser.add_argument("--log-level", default="WARNING")

    sub = parser.add_subparsers(dest="command", required=True)

    p_set = sub.add_parser("set", help="Установить endpoint+model+api_key (api_key через stdin)")
    p_set.add_argument("--endpoint", required=True, help="LLM endpoint URL")
    p_set.add_argument("--model", required=True, help="Имя модели")

    sub.add_parser("show", help="Показать текущие credentials (с маской api_key)")
    sub.add_parser("delete", help="Удалить credentials")
    sub.add_parser("test", help="Тестовый вызов LLM с сохранёнными credentials")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    handlers = {
        "set":    cmd_set,
        "show":   cmd_show,
        "delete": cmd_delete,
        "test":   cmd_test,
    }
    handler = handlers[args.command]
    return asyncio.run(handler(args))


if __name__ == "__main__":
    sys.exit(main())
