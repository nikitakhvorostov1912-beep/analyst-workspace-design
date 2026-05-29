"""Response guardrails для ИТС-KB ответов (M-K4, G2/G3 из AI-SPEC).

Детерминированные пост-проверки финального ответа ассистента, которые fit под
СУЩЕСТВУЮЩИЙ free-text + tool-calling оркестратор (не требуют structured
RAGResponse). Не блокируют ответ — помечают предупреждением (флаг в UI):

- **G2 phantom** — выдуманные методы БСП (через `phantom_check`). Главный
  детерминированный сигнал галлюцинации сигнатур (FM-1).
- **G3 unsupported** — ответ ссылается на методы БСП, но knowledge-retrieval
  был пуст (0 чанков) → утверждение не подкреплено источником («должно было
  быть "не нашёл"»).

Полное принуждение **G1 (citation-required)** требует контракта `RAGResponse`
с полем `citations[]` — это отдельный архитектурный шаг (см. AI-SPEC §6),
здесь намеренно НЕ форсится в работающий оркестратор. Текущие сигналы
(phantom + unsupported) дают анти-галлюцинацию уже сейчас, без риска.
"""

from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from app.knowledge.phantom_check import check_phantom_methods, extract_bsl_calls


@dataclass(frozen=True, slots=True)
class GuardrailReport:
    """Результат пост-проверки ответа.

    phantom_methods — `Модуль.Метод`, известные корпусу по модулю, но
        отсутствующие (вероятная выдумка).
    unsupported_claim — ответ упоминает методы БСП, но retrieval был пуст.
    """

    phantom_methods: tuple[str, ...]
    unsupported_claim: bool

    @property
    def has_warning(self) -> bool:
        return bool(self.phantom_methods) or self.unsupported_claim

    def to_dict(self) -> dict:
        return {
            "phantom_methods": list(self.phantom_methods),
            "unsupported_claim": self.unsupported_claim,
        }


async def evaluate_response(
    db: aiosqlite.Connection,
    *,
    answer: str,
    retrieved_count: int,
    version_filter: str | None = None,
) -> GuardrailReport:
    """Пост-проверка финального ответа ассистента.

    Args:
        db: aiosqlite connection (bsp_chunks доступна)
        answer: финальный текст ответа ассистента
        retrieved_count: сколько знаниевых чанков подняли search_its/search_bsp
            за turn (0 → retrieval пуст)
        version_filter: ограничить phantom-проверку версией БСП

    Returns:
        GuardrailReport (не блокирует — для UI-флага/телеметрии).
    """
    phantom = await check_phantom_methods(db, answer, version_filter=version_filter)
    has_calls = len(extract_bsl_calls(answer)) > 0
    unsupported = retrieved_count == 0 and has_calls
    return GuardrailReport(
        phantom_methods=phantom.phantom,
        unsupported_claim=unsupported,
    )
