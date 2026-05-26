"""Тесты для backend/app/orchestrator/mcp_cache.py (M-K2.4).

Покрытие:
- _canonical_args_hash: детерминизм + порядок ключей не важен
- is_cacheable_tool: whitelist
- MCPResultCache: get/set/expiry/eviction/invalidate
- Singleton lifecycle: get_mcp_cache, reset, set
- Integration с _execute_mcp_tool (cache hit/miss)
- Settings: defaults + custom
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.orchestrator.mcp_cache import (
    CACHEABLE_TOOLS,
    DEFAULT_MAX_SIZE,
    DEFAULT_TTL_S,
    CacheKey,
    MCPResultCache,
    _canonical_args_hash,
    get_mcp_cache,
    get_mcp_cache_settings,
    is_cacheable_tool,
    reset_mcp_cache_for_testing,
    set_mcp_cache_for_testing,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_mcp_cache_for_testing()
    yield
    reset_mcp_cache_for_testing()


# ---------- _canonical_args_hash ----------


def test_hash_deterministic():
    assert _canonical_args_hash({"a": 1}) == _canonical_args_hash({"a": 1})


def test_hash_independent_of_key_order():
    h1 = _canonical_args_hash({"a": 1, "b": 2})
    h2 = _canonical_args_hash({"b": 2, "a": 1})
    assert h1 == h2


def test_hash_different_for_different_values():
    h1 = _canonical_args_hash({"a": 1})
    h2 = _canonical_args_hash({"a": 2})
    assert h1 != h2


def test_hash_handles_none_and_empty():
    h_none = _canonical_args_hash(None)
    h_empty = _canonical_args_hash({})
    assert h_none == h_empty


def test_hash_supports_unicode_values():
    h = _canonical_args_hash({"меta": "значение"})
    assert len(h) == 64  # SHA-256 hex


def test_hash_handles_non_dict_args_gracefully():
    """Защитный fallback — не падаем на странных args."""
    h = _canonical_args_hash("string instead of dict")  # type: ignore[arg-type]
    assert len(h) == 64


# ---------- is_cacheable_tool ----------


def test_is_cacheable_whitelist():
    assert is_cacheable_tool("get_metadata")
    assert is_cacheable_tool("find_references_to_object")
    assert is_cacheable_tool("get_access_rights")
    assert is_cacheable_tool("get_bsl_syntax_help")


def test_is_cacheable_rejects_mutating_tools():
    assert not is_cacheable_tool("execute_code")
    assert not is_cacheable_tool("execute_query")
    assert not is_cacheable_tool("get_event_log")
    assert not is_cacheable_tool("submit_for_deanonymization")
    assert not is_cacheable_tool("")


def test_cacheable_tools_set_documented():
    assert "get_metadata" in CACHEABLE_TOOLS
    assert "execute_code" not in CACHEABLE_TOOLS


# ---------- MCPResultCache: основной API ----------


@pytest.mark.asyncio
async def test_cache_returns_none_on_miss():
    cache = MCPResultCache()
    key = cache.build_key("ch-1", "get_metadata", {"meta_type": "Документ"})
    assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_cache_hit_after_set():
    cache = MCPResultCache()
    key = cache.build_key("ch-1", "get_metadata", {})
    await cache.set(key, {"data": [1, 2, 3]})
    assert await cache.get(key) == {"data": [1, 2, 3]}


@pytest.mark.asyncio
async def test_cache_isolates_channels():
    cache = MCPResultCache()
    k1 = cache.build_key("ch-A", "get_metadata", {})
    k2 = cache.build_key("ch-B", "get_metadata", {})
    await cache.set(k1, "A-result")
    await cache.set(k2, "B-result")
    assert await cache.get(k1) == "A-result"
    assert await cache.get(k2) == "B-result"


@pytest.mark.asyncio
async def test_cache_isolates_tools():
    cache = MCPResultCache()
    k1 = cache.build_key("ch", "get_metadata", {})
    k2 = cache.build_key("ch", "find_references_to_object", {})
    await cache.set(k1, "meta-result")
    await cache.set(k2, "refs-result")
    assert await cache.get(k1) == "meta-result"
    assert await cache.get(k2) == "refs-result"


@pytest.mark.asyncio
async def test_cache_args_independent_of_order():
    cache = MCPResultCache()
    k1 = cache.build_key("ch", "get_metadata", {"a": 1, "b": 2})
    k2 = cache.build_key("ch", "get_metadata", {"b": 2, "a": 1})
    assert k1 == k2  # один и тот же ключ


# ---------- TTL expiry ----------


@pytest.mark.asyncio
async def test_cache_expires():
    cache = MCPResultCache(default_ttl_s=0.05)  # 50 ms
    key = cache.build_key("ch", "get_metadata", {})
    await cache.set(key, "x")
    assert await cache.get(key) == "x"
    await asyncio.sleep(0.1)
    assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_cache_custom_ttl_overrides_default():
    cache = MCPResultCache(default_ttl_s=1000)
    key = cache.build_key("ch", "get_metadata", {})
    await cache.set(key, "x", ttl_s=0.05)
    await asyncio.sleep(0.1)
    assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_cache_zero_ttl_skips_storage():
    cache = MCPResultCache()
    key = cache.build_key("ch", "get_metadata", {})
    await cache.set(key, "x", ttl_s=0)
    assert await cache.get(key) is None


# ---------- Eviction ----------


@pytest.mark.asyncio
async def test_cache_evicts_when_full():
    cache = MCPResultCache(max_size=10)
    # Заполняем больше max_size
    for i in range(15):
        key = cache.build_key("ch", "get_metadata", {"i": i})
        await cache.set(key, i)
    # size <= max_size
    assert cache.size <= 10
    # Часть записей выкинута → evictions > 0
    assert cache.stats["evictions"] > 0


@pytest.mark.asyncio
async def test_cache_does_not_evict_when_replacing():
    """Replace существующего ключа не должен вызывать eviction."""
    cache = MCPResultCache(max_size=3)
    for i in range(3):
        await cache.set(cache.build_key("ch", "get_metadata", {"i": i}), i)
    initial_evictions = cache.stats["evictions"]
    # Replace existing key — не должен evict
    await cache.set(cache.build_key("ch", "get_metadata", {"i": 0}), 999)
    assert cache.stats["evictions"] == initial_evictions
    assert cache.size == 3


# ---------- invalidate_channel ----------


@pytest.mark.asyncio
async def test_invalidate_channel_removes_only_target():
    cache = MCPResultCache()
    await cache.set(cache.build_key("ch-A", "get_metadata", {}), "a")
    await cache.set(cache.build_key("ch-A", "get_access_rights", {}), "a2")
    await cache.set(cache.build_key("ch-B", "get_metadata", {}), "b")

    removed = await cache.invalidate_channel("ch-A")
    assert removed == 2
    assert await cache.get(cache.build_key("ch-A", "get_metadata", {})) is None
    assert await cache.get(cache.build_key("ch-B", "get_metadata", {})) == "b"


@pytest.mark.asyncio
async def test_invalidate_channel_returns_zero_for_unknown():
    cache = MCPResultCache()
    removed = await cache.invalidate_channel("ch-ghost")
    assert removed == 0


# ---------- clear / stats ----------


@pytest.mark.asyncio
async def test_clear_removes_all():
    cache = MCPResultCache()
    for i in range(5):
        await cache.set(cache.build_key("ch", "get_metadata", {"i": i}), i)
    assert cache.size == 5
    await cache.clear()
    assert cache.size == 0


@pytest.mark.asyncio
async def test_stats_track_hits_and_misses():
    cache = MCPResultCache()
    key = cache.build_key("ch", "get_metadata", {})

    await cache.get(key)  # miss
    await cache.set(key, "x")
    await cache.get(key)  # hit
    await cache.get(key)  # hit

    assert cache.stats["hits"] == 2
    assert cache.stats["misses"] == 1


def test_reset_stats_zeros_counters():
    cache = MCPResultCache()
    cache._hits = 5
    cache._misses = 3
    cache._evictions = 2
    cache.reset_stats()
    assert cache.stats["hits"] == 0
    assert cache.stats["misses"] == 0
    assert cache.stats["evictions"] == 0


# ---------- Validation ----------


def test_cache_rejects_invalid_ttl():
    with pytest.raises(ValueError, match="ttl"):
        MCPResultCache(default_ttl_s=0)
    with pytest.raises(ValueError):
        MCPResultCache(default_ttl_s=-1)


def test_cache_rejects_invalid_max_size():
    with pytest.raises(ValueError, match="max_size"):
        MCPResultCache(max_size=0)


# ---------- Singleton ----------


@pytest.mark.asyncio
async def test_singleton_returns_same_instance():
    c1 = await get_mcp_cache()
    c2 = await get_mcp_cache()
    assert c1 is c2


def test_set_for_testing_replaces_singleton():
    custom = MCPResultCache(default_ttl_s=10)
    set_mcp_cache_for_testing(custom)
    # synchronous read via internal state — get_mcp_cache returns the set one
    from app.orchestrator.mcp_cache import _singleton
    assert _singleton is custom


def test_get_mcp_cache_settings_returns_tuple(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("MCP_CACHE_ENABLED", "true")
    monkeypatch.setenv("MCP_CACHE_TTL_S", "60")
    monkeypatch.setenv("MCP_CACHE_MAX_SIZE", "100")
    from app.config import get_settings
    get_settings.cache_clear()

    enabled, ttl, max_size = get_mcp_cache_settings()
    assert enabled is True
    assert ttl == 60.0
    assert max_size == 100


# ---------- Constants ----------


def test_default_ttl_sensible():
    assert 30 <= DEFAULT_TTL_S <= 600


def test_default_max_size_sensible():
    assert 100 <= DEFAULT_MAX_SIZE <= 10000


# ---------- Integration с _execute_mcp_tool ----------


@pytest.mark.asyncio
async def test_execute_mcp_tool_uses_cache_on_second_call(monkeypatch):
    """Second invocation of cacheable tool with same args → cache hit."""
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("MCP_CACHE_ENABLED", "true")
    monkeypatch.setenv("MCP_CACHE_TTL_S", "60")
    from app.config import get_settings
    get_settings.cache_clear()

    # Свежий singleton с большим TTL
    set_mcp_cache_for_testing(MCPResultCache(default_ttl_s=60, max_size=10))

    call_count = 0

    class FakeMCP:
        async def call_tool(self, name, args):
            nonlocal call_count
            call_count += 1
            return {"meta_type": args.get("meta_type"), "n": call_count}

    from app.orchestrator.loop import _execute_mcp_tool

    fake = FakeMCP()
    # 1-й вызов — miss → MCP call
    start = time.monotonic()
    e1, _, accum1, _ = await _execute_mcp_tool(
        tool_client=fake, tool_id="t1", tool_name="get_metadata",
        tool_args={"meta_type": "Документ"}, start_ts=start,
        channel_id="ch-1",
    )
    assert e1.ok
    assert call_count == 1

    # 2-й вызов с теми же args — должен быть cache hit, без MCP
    e2, _, accum2, _ = await _execute_mcp_tool(
        tool_client=fake, tool_id="t2", tool_name="get_metadata",
        tool_args={"meta_type": "Документ"}, start_ts=start,
        channel_id="ch-1",
    )
    assert e2.ok
    assert call_count == 1  # не увеличилось
    # Result совпадает
    assert accum1["result"] == accum2["result"]


@pytest.mark.asyncio
async def test_execute_mcp_tool_does_not_cache_non_cacheable(monkeypatch):
    """execute_query НЕ должен попадать в cache (даже повторно)."""
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("MCP_CACHE_ENABLED", "true")
    from app.config import get_settings
    get_settings.cache_clear()
    set_mcp_cache_for_testing(MCPResultCache(default_ttl_s=60, max_size=10))

    call_count = 0

    class FakeMCP:
        async def call_tool(self, name, args):
            nonlocal call_count
            call_count += 1
            return {"rows": []}

    from app.orchestrator.loop import _execute_mcp_tool
    fake = FakeMCP()
    start = time.monotonic()
    await _execute_mcp_tool(
        tool_client=fake, tool_id="t1", tool_name="execute_query",
        tool_args={"q": "ВЫБРАТЬ 1"}, start_ts=start,
        channel_id="ch-1",
    )
    await _execute_mcp_tool(
        tool_client=fake, tool_id="t2", tool_name="execute_query",
        tool_args={"q": "ВЫБРАТЬ 1"}, start_ts=start,
        channel_id="ch-1",
    )
    assert call_count == 2  # оба раза дошло до MCP


@pytest.mark.asyncio
async def test_execute_mcp_tool_disabled_via_settings(monkeypatch):
    monkeypatch.setenv("PYDANTIC_ENV_FILE", "")
    monkeypatch.setenv("MCP_CACHE_ENABLED", "false")
    from app.config import get_settings
    get_settings.cache_clear()
    set_mcp_cache_for_testing(MCPResultCache(default_ttl_s=60, max_size=10))

    call_count = 0

    class FakeMCP:
        async def call_tool(self, name, args):
            nonlocal call_count
            call_count += 1
            return {"x": 1}

    from app.orchestrator.loop import _execute_mcp_tool
    fake = FakeMCP()
    start = time.monotonic()
    await _execute_mcp_tool(
        tool_client=fake, tool_id="t1", tool_name="get_metadata",
        tool_args={}, start_ts=start, channel_id="ch-1",
    )
    await _execute_mcp_tool(
        tool_client=fake, tool_id="t2", tool_name="get_metadata",
        tool_args={}, start_ts=start, channel_id="ch-1",
    )
    assert call_count == 2  # cache disabled, оба раза MCP
