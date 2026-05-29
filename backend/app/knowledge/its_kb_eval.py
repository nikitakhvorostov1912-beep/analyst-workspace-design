"""ИТС-KB eval — измерение анти-галлюцинации (D1 из AI-SPEC, M-K4).

Прогоняет golden dataset (`eval/its_kb/golden.jsonl`) через phantom-детектор и
считает precision/recall/F1 детекции выдуманных методов БСП. Ground truth в
golden — на РЕАЛЬНЫХ сигнатурах из исходников БСП (ssl_3_2), phantom-кейсы
верифицированы grep'ом как несуществующие.

Цель AI-SPEC: hallucination rate <5%. Здесь — обратная метрика: детектор должен
ловить фантомы (recall) и не флагать реальные методы (precision).

Использование (на живом корпусе с проиндексированным bsp_chunks):
    python -m scripts.run_its_kb_eval
Тест (на засеянном in-memory корпусе): tests/test_its_kb_eval.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite

from app.knowledge.phantom_check import check_phantom_methods

DEFAULT_GOLDEN_PATH = Path(__file__).resolve().parents[2] / "eval" / "its_kb" / "golden.jsonl"


def load_golden(path: str | Path = DEFAULT_GOLDEN_PATH) -> list[dict]:
    """Читает golden.jsonl (по одному JSON-объекту на строку)."""
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@dataclass(frozen=True, slots=True)
class PhantomEvalResult:
    """Агрегированные метрики phantom-детекции по golden-сету.

    tp/fp/fn считаются по-методно (один пропущенный/ложный метод = 1 fn/fp),
    failures — кейсы где набор флагнутых методов != ожидаемого.
    """

    total: int
    tp: int
    fp: int
    fn: int
    failures: list[dict] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 1.0

    def summary(self) -> str:
        return (
            f"phantom eval: {self.total} cases | "
            f"precision={self.precision:.3f} recall={self.recall:.3f} f1={self.f1:.3f} | "
            f"tp={self.tp} fp={self.fp} fn={self.fn} | failures={len(self.failures)}"
        )


async def evaluate_phantom_detection(
    db: aiosqlite.Connection,
    golden: list[dict],
) -> PhantomEvalResult:
    """Прогоняет check_phantom_methods на answer каждого кейса, сверяет с
    expected_phantom. Требует засеянный/проиндексированный bsp_chunks."""
    tp = fp = fn = 0
    failures: list[dict] = []
    for entry in golden:
        expected = set(entry.get("expected_phantom", []))
        report = await check_phantom_methods(db, entry.get("answer", ""))
        got = set(report.phantom)
        tp += len(expected & got)
        fp += len(got - expected)
        fn += len(expected - got)
        if got != expected:
            failures.append({
                "id": entry.get("id"),
                "category": entry.get("category"),
                "expected": sorted(expected),
                "got": sorted(got),
            })
    return PhantomEvalResult(total=len(golden), tp=tp, fp=fp, fn=fn, failures=failures)
