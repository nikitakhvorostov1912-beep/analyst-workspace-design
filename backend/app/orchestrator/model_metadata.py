"""Model metadata — context window + capabilities per модель.

Sprint 5 (Hermes H5): per-model context length tracking.

Используется compressor чтобы знать какое окно у активной модели.
До этого мы держали MAX_CONTEXT_TOKENS=128_000 константой — теперь
можно динамически.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelMetadata:
    """Capabilities + лимиты модели."""

    name: str
    context_window: int          # max input tokens
    max_output: int              # max output tokens
    supports_vision: bool = False
    supports_reasoning: bool = False   # thinking-mode (MiMo / R1 / Sonnet 4.5+)
    supports_caching: bool = False     # Anthropic prompt caching


REGISTRY: dict[str, ModelMetadata] = {
    # OpenAI
    "gpt-4o": ModelMetadata(
        name="gpt-4o", context_window=128_000, max_output=16_384, supports_vision=True,
    ),
    "gpt-4o-mini": ModelMetadata(
        name="gpt-4o-mini", context_window=128_000, max_output=16_384, supports_vision=True,
    ),
    "gpt-4.1": ModelMetadata(
        name="gpt-4.1", context_window=1_000_000, max_output=32_768, supports_vision=True,
    ),
    "gpt-4.1-mini": ModelMetadata(
        name="gpt-4.1-mini", context_window=1_000_000, max_output=32_768, supports_vision=True,
    ),
    # Anthropic
    "claude-sonnet-4-5": ModelMetadata(
        name="claude-sonnet-4-5", context_window=200_000, max_output=8_192,
        supports_vision=True, supports_reasoning=True, supports_caching=True,
    ),
    "claude-sonnet-4-6": ModelMetadata(
        name="claude-sonnet-4-6", context_window=200_000, max_output=8_192,
        supports_vision=True, supports_reasoning=True, supports_caching=True,
    ),
    "claude-opus-4": ModelMetadata(
        name="claude-opus-4", context_window=200_000, max_output=4_096,
        supports_vision=True, supports_reasoning=True, supports_caching=True,
    ),
    "claude-haiku-4-5": ModelMetadata(
        name="claude-haiku-4-5", context_window=200_000, max_output=4_096,
        supports_vision=True, supports_caching=True,
    ),
    # Xiaomi MiMo
    "mimo-v2.5-pro": ModelMetadata(
        name="mimo-v2.5-pro", context_window=128_000, max_output=8_192,
        supports_reasoning=True,
    ),
    "mimo-v2-omni": ModelMetadata(
        name="mimo-v2-omni", context_window=128_000, max_output=8_192,
        supports_vision=True,
    ),
    "mimo-v2-flash": ModelMetadata(
        name="mimo-v2-flash", context_window=64_000, max_output=4_096,
    ),
}


# Fallback по умолчанию для неизвестной модели.
DEFAULT_FALLBACK = ModelMetadata(
    name="unknown", context_window=8_000, max_output=2_048,
)


def get_metadata(model: str) -> ModelMetadata:
    """Точное совпадение или префикс-поиск, иначе DEFAULT_FALLBACK."""
    if model in REGISTRY:
        return REGISTRY[model]
    for key, meta in REGISTRY.items():
        if model.startswith(key):
            return meta
    return DEFAULT_FALLBACK


def register_model(meta: ModelMetadata) -> None:
    REGISTRY[meta.name] = meta


def estimate_remaining_budget(
    *,
    model: str,
    used_tokens: int,
    desired_output: int = 2_048,
) -> int:
    """Сколько токенов ещё можно положить в prompt.

    budget = context_window - used_tokens - desired_output - safety_margin.
    Safety margin = 5% от окна.
    """
    meta = get_metadata(model)
    safety = int(meta.context_window * 0.05)
    return max(0, meta.context_window - used_tokens - desired_output - safety)
