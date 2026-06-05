"""Тесты live-проб детекции (Phase 3, Multi-base онбординг)."""
from __future__ import annotations

import pytest

from app.knowledge.config_detection import KNOWN_CONFIGURATIONS
from app.knowledge.config_probe import (
    ALL_MARKERS,
    collect_marker_presence,
    detect_from_live,
)
from app.knowledge.indexer import NormalizedMetadata


def test_all_markers_is_union_of_signatures():
    expected = set()
    for sig in KNOWN_CONFIGURATIONS:
        expected |= set(sig.characteristic_objects)
        expected |= set(sig.discriminative_objects)
    assert ALL_MARKERS == expected
    assert "Документ.РасчетСебестоимостиТоваров" in ALL_MARKERS


@pytest.mark.asyncio
async def test_collect_marker_presence_returns_only_present(monkeypatch):
    """Проба возвращает объект → маркер «присутствует»; пусто → отсутствует."""
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    present_paths = set(ka.characteristic_objects) | set(ka.discriminative_objects)

    async def fake_probe(endpoint, name_mask, limit, *, anon_headers=None):
        # эмулируем 1C name_mask substring: вернуть объект, если какой-то
        # present-маркер содержит маску в short-name.
        out = []
        for path in present_paths:
            short = path.split(".")[-1]
            if name_mask.lower() in short.lower():
                out.append(NormalizedMetadata(
                    object_path=path, object_type=path.split(".")[0],
                    name=short, presentation=None,
                ))
        return out

    # collect_marker_presence ссылается на live_metadata_suggest как на global
    # модуля config_probe (импортирован на уровне модуля) — патчим там.
    monkeypatch.setattr(
        "app.knowledge.config_probe.live_metadata_suggest", fake_probe,
    )
    found = await collect_marker_presence("http://x/mcp", concurrency=4)
    # все КА-маркеры найдены, ERP-МСФО — нет
    assert "Документ.РасчетСебестоимостиТоваров" in found
    assert "РегистрБухгалтерии.МеждународныйУчет" not in found


@pytest.mark.asyncio
async def test_detect_from_live_detects_ka(monkeypatch):
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    present = set(ut.characteristic_objects) | set(ka.characteristic_objects) \
        | set(ka.discriminative_objects)

    async def fake_collect(endpoint, *, anon_headers=None, concurrency=10):
        return present

    monkeypatch.setattr(
        "app.knowledge.config_probe.collect_marker_presence", fake_collect,
    )
    result = await detect_from_live("http://x/mcp")
    assert result.configuration_key == "ka_2_5"
