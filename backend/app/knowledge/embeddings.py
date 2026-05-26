"""Embedding Pipeline — клиент для генерации embeddings (M-K2.6).

Слой L3 Knowledge Layer: преобразует текст (presentation / описание объекта /
ИТС-фрагмент / БСП-сниппет) → float vector для vector_store.

**Стратегия провайдера:**
- `OpenAIEmbeddingClient` — основной (cloud, OpenAI-compatible API через
  тот же endpoint что и LLM). Модель `text-embedding-3-small` (1536-D)
  по умолчанию.
- `MockEmbeddingClient` — детерминированный для тестов (hash-based).
- `BGEM3EmbeddingClient` — отложен на M-K3 (FastEmbed local model, 570 MB
  download, требует bundling-стратегии в M-K5 Distribution).

**Protocol:** `EmbeddingClient` — async batch embed.
**Settings:** `embedding_provider` env (`openai` | `mock`, default `openai`).
**Default model:** `BAAI/bge-m3` (1024-D) — заложено в vector_store, но
M-K2.6 шипит OpenAI как primary. Смена модели = ALTER vec0 (см. vector_store).

**Что НЕ делает M-K2.6:**
- Не интегрируется с indexer pipeline (M-K3 будет добавлять embedding к
  каждому объекту во время bulk_refresh).
- Не делает chunking длинных текстов — single string in, single vector out.
- Не делает retry/backoff (это в M-K3 retry layer как для LLM).
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Protocol, Sequence

import httpx

logger = logging.getLogger(__name__)


# OpenAI text-embedding-3-small — 1536 dimensions
OPENAI_DEFAULT_MODEL = "text-embedding-3-small"
OPENAI_DEFAULT_DIM = 1536


class EmbeddingError(Exception):
    """Базовая ошибка embedding pipeline."""


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Результат embed() — vectors + metadata."""

    embeddings: list[list[float]]
    model: str
    dim: int

    def __len__(self) -> int:
        return len(self.embeddings)


class EmbeddingClient(Protocol):
    """Контракт embedding-клиента: async batch embed.

    Реализации:
    - OpenAIEmbeddingClient — cloud API
    - MockEmbeddingClient — для тестов (детерминированный)
    """

    @property
    def model(self) -> str: ...

    @property
    def dim(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult: ...

    async def aclose(self) -> None: ...


class MockEmbeddingClient:
    """Детерминированный mock — хэширует текст в bytes, разбивает на float.

    НЕ для production: эмбеддинги не семантические, только для unit-тестов
    и SDK smoke. Стабильность гарантирована: один и тот же текст → один
    и тот же вектор, всегда.

    `dim` настраивается под нужный vec0 размер. Дефолт 4 для unit-тестов
    (compatible с test_vector_store.py).
    """

    def __init__(self, dim: int = 4, model: str = "mock-deterministic"):
        if dim <= 0:
            raise EmbeddingError(f"dim должен быть > 0, получено {dim}")
        self._dim = dim
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> list[float]:
        """SHA-256 → bytes → нормализованный float vector нужной размерности."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Размножаем digest если dim > 32, отрезаем если меньше
        needed = self._dim * 4  # каждый float = 4 bytes
        buf = (digest * ((needed // len(digest)) + 1))[:needed]
        # Распакуем как int32, нормализуем в [-1, 1]
        floats: list[float] = []
        for i in range(0, needed, 4):
            value = int.from_bytes(buf[i:i + 4], "little", signed=True)
            floats.append(value / (2**31))
        # L2-нормализация (для cosine-friendly distances в vec0)
        norm = math.sqrt(sum(v * v for v in floats))
        if norm == 0:
            return floats
        return [v / norm for v in floats]

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            raise EmbeddingError("texts пустой")
        embeddings = [self._embed_one(t) for t in texts]
        return EmbeddingResult(embeddings=embeddings, model=self._model, dim=self._dim)

    async def aclose(self) -> None:
        # Ничего не делаем — нет ресурсов
        return None


class OpenAIEmbeddingClient:
    """OpenAI-compatible embedding клиент.

    Работает с любым endpoint поддерживающим `/v1/embeddings` (OpenAI,
    Azure OpenAI, OpenRouter, Together, Together AI, NVIDIA NIM, etc.).
    """

    def __init__(
        self,
        *,
        endpoint: str = "https://api.openai.com/v1",
        api_key: str,
        model: str = OPENAI_DEFAULT_MODEL,
        dim: int = OPENAI_DEFAULT_DIM,
        timeout_s: float = 30.0,
    ):
        if not api_key:
            raise EmbeddingError("api_key обязателен для OpenAIEmbeddingClient")
        if dim <= 0:
            raise EmbeddingError(f"dim должен быть > 0, получено {dim}")
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._dim = dim
        self._client = httpx.AsyncClient(timeout=timeout_s)

    @property
    def model(self) -> str:
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            raise EmbeddingError("texts пустой")

        url = f"{self._endpoint}/embeddings"
        payload: dict = {
            "model": self._model,
            "input": list(texts),
        }
        # OpenAI text-embedding-3-* поддерживает параметр `dimensions`
        # для понижения размерности. Если запрошенная dim != default,
        # просим backend усечь.
        if self._model.startswith("text-embedding-3-") and self._dim != OPENAI_DEFAULT_DIM:
            payload["dimensions"] = self._dim

        try:
            response = await self._client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.RequestError as exc:
            raise EmbeddingError(f"Сетевая ошибка embedding: {exc}") from exc

        if response.status_code != 200:
            raise EmbeddingError(
                f"OpenAI embedding API вернул {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise EmbeddingError(f"Невалидный JSON в response: {exc}") from exc

        items = data.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise EmbeddingError(
                f"OpenAI response: ожидалось data[{len(texts)}], получено "
                f"data[{len(items) if isinstance(items, list) else '?'}]"
            )

        embeddings: list[list[float]] = []
        for item in items:
            embedding = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingError(
                    "OpenAI response: отсутствует / пустое поле 'embedding'"
                )
            embeddings.append([float(v) for v in embedding])

        # Sanity-check: фактическая размерность совпадает с заявленной
        actual_dim = len(embeddings[0]) if embeddings else 0
        if actual_dim != self._dim:
            logger.warning(
                "OpenAI embedding dim mismatch: ожидали %d, получили %d. "
                "Возможно модель/endpoint игнорируют параметр dimensions.",
                self._dim,
                actual_dim,
            )

        return EmbeddingResult(
            embeddings=embeddings,
            model=data.get("model", self._model),
            dim=actual_dim,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
