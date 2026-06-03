"""MCP Result Cache — TTL-кеш повторных MCP-вызовов (M-K2.4).

Knowledge Foundation Phase 4: легковесный in-memory cache для
get_metadata / find_references_to_object / get_access_rights — типичных
MCP-вызовов которые LLM может повторить в той же сессии при rephrasing
или follow-up вопросах.

**Зачем:**
- LLM при follow-up «а ещё какие документы?» часто заново зовёт
  get_metadata. MCP вызов + парсинг занимает 200-2000 ms — кеш делает
  это near-instant.
- get_metadata детерминирован (для одной базы в одну секунду) — безопасно
  кешировать на 60-300 сек.

**Что НЕ кешируем:**
- execute_code — побочные эффекты, никогда не кеш.
- execute_query — может быть SELECT, но детект SQL DML/DDL сложно без
  парсера → консервативно не кешируем (риск показать устаревшие данные
  выше profит'а).
- get_event_log — журнал растёт постоянно, кеш дал бы false negative.
- restart/close_session — runtime control, не data.

**Концепция ключа:** `CacheKey(channel_id, tool_name, args_hash)` где
`args_hash` — SHA-256 от sorted JSON dict args. Это гарантирует:
- разные каналы изолированы
- семантически идентичные args (разный порядок ключей) дают тот же hit
- небольшой ключ (32 bytes хеш) → не хранится весь JSON

**LRU eviction:** при достижении `max_size` — удаляем 10% самых старых
(по expires_at). Простая стратегия, без deque/OrderedDict — у нас не
hot path, овеhead приемлем.

**Threading:** singleton + asyncio.Lock на mutations. Cache живёт между
запросами (process-wide). При restart backend — теряется (acceptable —
кеш по природе ephemeral).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Tools которые безопасно кешировать. Для остальных — passthrough.
CACHEABLE_TOOLS: frozenset[str] = frozenset({
    "get_metadata",
    "find_references_to_object",
    "get_access_rights",
    "get_bsl_syntax_help",
    "get_link_of_object",
    "get_object_by_link",
    # 2026-06-03 (ИТС-латентность): живой Напарник 1С отвечает ~15с/вызов.
    # Модель часто повторяет search_its с теми же args в одном turn → кешируем
    # на TTL (2 мин), чтобы идентичный повтор не бил по its.1c.ru снова.
    # ИТС-контент в пределах 2 мин не «протухает» материально.
    "buddy.search_its",
    "buddy.fetch_its",
})


DEFAULT_TTL_S = 120.0
"""По умолчанию запись живёт 2 минуты — баланс «не показывать stale»
и «не дёргать MCP лишний раз»."""

DEFAULT_MAX_SIZE = 500
"""Максимум записей в кеше — typical user session не должна выйти за
это. При превышении срабатывает LRU-like eviction."""

# Сколько записей выкидываем за раз при eviction (10% от max_size).
_EVICTION_BATCH_RATIO = 0.1


@dataclass(frozen=True, slots=True)
class CacheKey:
    """Ключ записи: канал + tool + хеш аргументов."""

    channel_id: str
    tool_name: str
    args_hash: str


@dataclass(slots=True)
class CacheEntry:
    """Запись с timestamp создания и expiry.

    Mutable: при hit мы не обновляем (touch) — простой TTL без LRU-touch.
    """

    result: Any
    expires_at: float


def _canonical_args_hash(args: dict | None) -> str:
    """SHA-256 hex от canonical JSON args.

    - sort_keys=True → независим от порядка ключей
    - ensure_ascii=False → кириллица не превращается в \\u-escapes
      (короче hash content → лучше cache hit rate)
    - separators=(',',':') → нет пробелов

    None args → стабильный хеш пустого dict.
    """
    if args is None:
        args = {}
    if not isinstance(args, dict):
        # Защитный fallback — args нестандартного типа кладём str-репрезентацию
        args = {"_repr": str(args)}
    payload = json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_cacheable_tool(tool_name: str) -> bool:
    """True если tool безопасно кешировать (см. CACHEABLE_TOOLS)."""
    return tool_name in CACHEABLE_TOOLS


class MCPResultCache:
    """TTL cache MCP результатов.

    Не threadsafe для sync операций — все mutations через async-методы
    с lock'ом. Используется как process-singleton через `get_mcp_cache()`.
    """

    def __init__(
        self,
        *,
        default_ttl_s: float = DEFAULT_TTL_S,
        max_size: int = DEFAULT_MAX_SIZE,
    ) -> None:
        if default_ttl_s <= 0:
            raise ValueError(f"default_ttl_s должен быть > 0, получено {default_ttl_s}")
        if max_size <= 0:
            raise ValueError(f"max_size должен быть > 0, получено {max_size}")
        self._default_ttl = default_ttl_s
        self._max_size = max_size
        self._store: dict[CacheKey, CacheEntry] = {}
        self._lock = asyncio.Lock()
        # Telemetry-friendly counters (для будущего /admin/cache-stats)
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def stats(self) -> dict:
        return {
            "size": self.size,
            "max_size": self._max_size,
            "default_ttl_s": self._default_ttl,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
        }

    def build_key(
        self,
        channel_id: str,
        tool_name: str,
        tool_args: dict | None,
    ) -> CacheKey:
        return CacheKey(
            channel_id=channel_id,
            tool_name=tool_name,
            args_hash=_canonical_args_hash(tool_args),
        )

    async def get(self, key: CacheKey) -> Any | None:
        """Возвращает cached result или None (miss или expired)."""
        now = time.monotonic()
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if now >= entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.result

    async def set(
        self,
        key: CacheKey,
        result: Any,
        *,
        ttl_s: float | None = None,
    ) -> None:
        """Кладёт result в кеш с TTL. None ttl = default_ttl_s."""
        effective_ttl = ttl_s if ttl_s is not None else self._default_ttl
        if effective_ttl <= 0:
            return  # отрицательный/нулевой TTL = не кешируем
        expires_at = time.monotonic() + effective_ttl
        async with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_oldest_unsafe()
            self._store[key] = CacheEntry(result=result, expires_at=expires_at)

    def _evict_oldest_unsafe(self) -> None:
        """Выкидывает 10% самых старых (по expires_at). Caller владеет lock'ом."""
        if not self._store:
            return
        evict_count = max(1, int(self._max_size * _EVICTION_BATCH_RATIO))
        # sort by expires_at ASC — самые рано истекающие первые
        sorted_keys = sorted(
            self._store.keys(),
            key=lambda k: self._store[k].expires_at,
        )
        for k in sorted_keys[:evict_count]:
            del self._store[k]
            self._evictions += 1

    async def invalidate_channel(self, channel_id: str) -> int:
        """Удаляет все записи для канала (на случай реиндексации / disconnect).

        Returns: количество удалённых записей.
        """
        async with self._lock:
            to_remove = [k for k in self._store if k.channel_id == channel_id]
            for k in to_remove:
                del self._store[k]
            return len(to_remove)

    async def clear(self) -> None:
        """Полная очистка (для тестов / admin reset)."""
        async with self._lock:
            self._store.clear()
            # Не сбрасываем hits/misses/evictions — они кумулятивные для
            # лайфтайма процесса. Сбросить через `reset_stats()` если нужно.

    def reset_stats(self) -> None:
        """Обнуляет hit/miss/eviction counters (для тестов)."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0


# ===========================================================================
# Singleton
# ===========================================================================

_singleton: MCPResultCache | None = None
_singleton_lock = asyncio.Lock()


def get_mcp_cache_settings() -> tuple[bool, float, int]:
    """Возвращает (enabled, ttl_s, max_size) из текущих Settings.

    Lazy import чтобы избежать circular между config <-> mcp_cache.
    """
    from app.config import get_settings
    settings = get_settings()
    return (
        getattr(settings, "mcp_cache_enabled", True),
        float(getattr(settings, "mcp_cache_ttl_s", DEFAULT_TTL_S)),
        int(getattr(settings, "mcp_cache_max_size", DEFAULT_MAX_SIZE)),
    )


async def get_mcp_cache() -> MCPResultCache:
    """Lazy singleton. Создаёт cache при первом вызове по текущим settings."""
    global _singleton
    if _singleton is None:
        async with _singleton_lock:
            if _singleton is None:
                _, ttl_s, max_size = get_mcp_cache_settings()
                _singleton = MCPResultCache(
                    default_ttl_s=ttl_s,
                    max_size=max_size,
                )
                logger.info(
                    "MCP result cache initialized: ttl=%.0fs max_size=%d",
                    ttl_s, max_size,
                )
    return _singleton


def reset_mcp_cache_for_testing() -> None:
    """Сбрасывает singleton (только для тестов — обходит lock)."""
    global _singleton
    _singleton = None


def set_mcp_cache_for_testing(cache: MCPResultCache | None) -> None:
    """Прямая инъекция cache для тестов (без async lock)."""
    global _singleton
    _singleton = cache
