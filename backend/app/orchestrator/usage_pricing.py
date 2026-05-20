"""Usage pricing — $/M tokens registry + cost compute per turn.

Sprint 5 (Hermes I4): расчёт стоимости каждого turn'а.

Цены берутся из локального registry (PRICES_PER_M_TOKENS) — никаких сетевых
вызовов на каждый turn. Регистр расширяется через add_model_price().

Модели без записанной цены → cost = None (а не 0) — это сигнал «не знаем».
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


CostStatus = Literal["actual", "estimated", "unknown"]


@dataclass(frozen=True)
class ModelPrice:
    """Цена за миллион токенов в долларах США."""

    input_per_m: float
    output_per_m: float
    cached_input_per_m: float | None = None  # Anthropic prompt caching discount

    @property
    def input_per_token(self) -> float:
        return self.input_per_m / 1_000_000.0

    @property
    def output_per_token(self) -> float:
        return self.output_per_m / 1_000_000.0


# Цены на 2026-05 (актуальные на момент Sprint 5).
# Источник: вендорские прайсы. Обновлять регистр через add_model_price.
PRICES_PER_M_TOKENS: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o": ModelPrice(input_per_m=2.50, output_per_m=10.00),
    "gpt-4o-mini": ModelPrice(input_per_m=0.15, output_per_m=0.60),
    "gpt-4.1": ModelPrice(input_per_m=2.00, output_per_m=8.00),
    "gpt-4.1-mini": ModelPrice(input_per_m=0.40, output_per_m=1.60),
    # Anthropic Claude
    "claude-sonnet-4-5": ModelPrice(
        input_per_m=3.00, output_per_m=15.00, cached_input_per_m=0.30
    ),
    "claude-sonnet-4-6": ModelPrice(
        input_per_m=3.00, output_per_m=15.00, cached_input_per_m=0.30
    ),
    "claude-opus-4": ModelPrice(
        input_per_m=15.00, output_per_m=75.00, cached_input_per_m=1.50
    ),
    "claude-haiku-4-5": ModelPrice(
        input_per_m=1.00, output_per_m=5.00, cached_input_per_m=0.10
    ),
    # Xiaomi MiMo (наша основная модель)
    "mimo-v2.5-pro": ModelPrice(input_per_m=0.15, output_per_m=0.60),
    "mimo-v2-omni": ModelPrice(input_per_m=0.50, output_per_m=2.00),
    "mimo-v2-flash": ModelPrice(input_per_m=0.075, output_per_m=0.30),
}


@dataclass(frozen=True)
class TurnCost:
    """Стоимость одного turn'а."""

    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    cached_input_cost_usd: float
    total_cost_usd: float
    status: CostStatus

    def as_dict(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "input_cost_usd": round(self.input_cost_usd, 6),
            "output_cost_usd": round(self.output_cost_usd, 6),
            "cached_input_cost_usd": round(self.cached_input_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "status": self.status,
        }


def add_model_price(model: str, price: ModelPrice) -> None:
    """Добавить/обновить цену модели в runtime registry."""
    PRICES_PER_M_TOKENS[model] = price


def get_price(model: str) -> ModelPrice | None:
    """Точное совпадение, либо префикс-fallback (например claude-sonnet-4-6-20250929)."""
    if model in PRICES_PER_M_TOKENS:
        return PRICES_PER_M_TOKENS[model]
    # Префикс-поиск: иногда вендоры добавляют date-suffix к имени.
    for key, price in PRICES_PER_M_TOKENS.items():
        if model.startswith(key):
            return price
    return None


def compute_turn_cost(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> TurnCost:
    """Вычисляет TurnCost. Если модель неизвестна → status='unknown', все costs=0.

    Args:
        model: имя модели.
        input_tokens: prompt tokens (не cached).
        output_tokens: completion tokens.
        cached_input_tokens: tokens которые попали в prompt cache (Anthropic).

    Returns:
        TurnCost.
    """
    price = get_price(model)
    if price is None:
        return TurnCost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            cached_input_cost_usd=0.0,
            total_cost_usd=0.0,
            status="unknown",
        )

    input_cost = price.input_per_token * input_tokens
    output_cost = price.output_per_token * output_tokens
    cached_cost = 0.0
    if cached_input_tokens > 0 and price.cached_input_per_m is not None:
        cached_cost = (price.cached_input_per_m / 1_000_000.0) * cached_input_tokens

    total = input_cost + output_cost + cached_cost
    return TurnCost(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        cached_input_cost_usd=cached_cost,
        total_cost_usd=total,
        status="actual",
    )


def aggregate_costs(turns: list[TurnCost]) -> TurnCost:
    """Суммирует список TurnCost в один (для session/period). model='aggregated'."""
    if not turns:
        return TurnCost(
            model="empty",
            input_tokens=0, output_tokens=0, cached_input_tokens=0,
            input_cost_usd=0.0, output_cost_usd=0.0, cached_input_cost_usd=0.0,
            total_cost_usd=0.0, status="actual",
        )
    return TurnCost(
        model="aggregated",
        input_tokens=sum(t.input_tokens for t in turns),
        output_tokens=sum(t.output_tokens for t in turns),
        cached_input_tokens=sum(t.cached_input_tokens for t in turns),
        input_cost_usd=sum(t.input_cost_usd for t in turns),
        output_cost_usd=sum(t.output_cost_usd for t in turns),
        cached_input_cost_usd=sum(t.cached_input_cost_usd for t in turns),
        total_cost_usd=sum(t.total_cost_usd for t in turns),
        status="actual" if all(t.status == "actual" for t in turns) else "estimated",
    )
