"""Jittered exponential backoff retry — защита от thundering-herd.

Sprint 2 (Hermes E2): retry с jitter.

Без jitter сотни одновременно стартанувших клиентов при 429 синхронно
ретраят через одни и те же интервалы → второй раунд тоже 429.
Jitter (рандомизация задержки) разносит retry во времени.

Алгоритм (full jitter — Pete Cordell / AWS recommendation):
    delay = random.uniform(0, base * 2 ** attempt)
    delay = min(delay, max_delay)

Используем для:
- LLM 429 / 5xx — повтор после короткой паузы
- MCP timeout / connect error
- Любых transient ошибок которые могут пройти "сами"
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    """Параметры jittered retry."""

    max_attempts: int = 3
    base_delay_s: float = 0.2
    max_delay_s: float = 5.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.base_delay_s < 0:
            raise ValueError(f"base_delay_s must be >= 0, got {self.base_delay_s}")
        if self.max_delay_s < self.base_delay_s:
            raise ValueError(
                f"max_delay_s ({self.max_delay_s}) must be >= base_delay_s ({self.base_delay_s})"
            )


def compute_jittered_delay(
    attempt: int,
    base_delay_s: float,
    max_delay_s: float,
    rng: random.Random | None = None,
) -> float:
    """Полный jitter: delay ∈ [0, min(max, base * 2^attempt)).

    attempt — 0-indexed (первый retry = 0, второй = 1, …).
    """
    if attempt < 0:
        raise ValueError(f"attempt must be >= 0, got {attempt}")
    rnd = rng or random
    ceiling = min(max_delay_s, base_delay_s * (2 ** attempt))
    if ceiling <= 0:
        return 0.0
    return rnd.uniform(0, ceiling)


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig = RetryConfig(),
    should_retry: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: random.Random | None = None,
) -> T:
    """Запускает fn() с retry под jittered backoff.

    Args:
        fn: async callable без аргументов.
        config: RetryConfig (max_attempts, base, max).
        should_retry: предикат "стоит ли ретраить эту exception?".
            None → ретраим любое исключение (default).
        sleep: подменяемая функция сна (для тестов).
        rng: подменяемый random (для тестов).

    Raises:
        Последнее перехваченное исключение если все попытки исчерпаны
        или should_retry вернул False.
    """
    last_exc: Exception | None = None
    for attempt in range(config.max_attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — повторно бросаем
            last_exc = exc
            if should_retry is not None and not should_retry(exc):
                raise
            if attempt == config.max_attempts - 1:
                break
            delay = compute_jittered_delay(
                attempt, config.base_delay_s, config.max_delay_s, rng=rng
            )
            await sleep(delay)
    assert last_exc is not None  # noqa: S101 — defensive, выше break только когда exc was caught
    raise last_exc


def retry_sync(
    fn: Callable[[], T],
    config: RetryConfig = RetryConfig(),
    should_retry: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    """Синхронная версия — для не-async вызовов (memory provider, например).

    Симметрично retry_async.
    """
    last_exc: Exception | None = None
    for attempt in range(config.max_attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if should_retry is not None and not should_retry(exc):
                raise
            if attempt == config.max_attempts - 1:
                break
            delay = compute_jittered_delay(
                attempt, config.base_delay_s, config.max_delay_s, rng=rng
            )
            sleep(delay)
    assert last_exc is not None  # noqa: S101
    raise last_exc
