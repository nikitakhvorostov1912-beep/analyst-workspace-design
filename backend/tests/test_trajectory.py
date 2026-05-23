"""Tests for app.learning.trajectory (Sprint 1)."""

from __future__ import annotations

import json
from pathlib import Path

from app.learning import TrajectoryLogger


def test_logger_writes_to_sample_file_when_completed(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path)
    logger.log_turn(
        session_id="s1",
        channel_id="ch1",
        messages=[
            {"role": "system", "content": "You are an agent"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ],
        tool_calls=[],
        completed=True,
        model="mimo-v2.5-pro",
    )
    sample = tmp_path / "trajectory_samples.jsonl"
    assert sample.exists()
    lines = sample.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["metadata"]["session_id"] == "s1"
    assert entry["metadata"]["completed"] is True
    assert len(entry["conversations"]) == 3


def test_logger_writes_to_failed_file_when_not_completed(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path)
    logger.log_turn(
        session_id="s1",
        channel_id="ch1",
        messages=[{"role": "user", "content": "Hi"}],
        tool_calls=[],
        completed=False,
        model="mimo-v2.5-pro",
    )
    assert not (tmp_path / "trajectory_samples.jsonl").exists()
    assert (tmp_path / "failed_trajectories.jsonl").exists()


def test_logger_appends_multiple_entries(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path)
    for i in range(5):
        logger.log_turn(
            session_id=f"s{i}",
            channel_id="ch1",
            messages=[{"role": "user", "content": f"Msg {i}"}],
            tool_calls=[],
            completed=True,
            model="m",
        )
    stats = logger.stats()
    assert stats["sample_count"] == 5


def test_logger_disabled_is_noop(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path, enabled=False)
    logger.log_turn(
        session_id="s1",
        channel_id="ch1",
        messages=[],
        tool_calls=[],
        completed=True,
        model="m",
    )
    # Не должно ничего записать
    assert not (tmp_path / "trajectory_samples.jsonl").exists()


def test_logger_handles_multimodal_content(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path)
    logger.log_turn(
        session_id="s1",
        channel_id="ch1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Что на картинке?"},
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                ],
            },
            {"role": "assistant", "content": "Это диаграмма"},
        ],
        tool_calls=[],
        completed=True,
        model="m",
    )
    entry = json.loads((tmp_path / "trajectory_samples.jsonl").read_text(encoding="utf-8").strip())
    # Image part пропущена, текст сохранён
    user_msg = entry["conversations"][0]
    assert user_msg["from"] == "human"
    assert "Что на картинке" in user_msg["value"]
    # image_url не должен попасть в value
    assert "image_url" not in user_msg["value"]


def test_logger_stats_empty(tmp_path: Path) -> None:
    logger = TrajectoryLogger(tmp_path)
    stats = logger.stats()
    assert stats == {"sample_count": 0, "failed_count": 0}
