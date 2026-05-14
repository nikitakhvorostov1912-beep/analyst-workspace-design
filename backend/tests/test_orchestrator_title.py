"""Тесты auto-title генерации (Plan 2.3)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.orchestrator.title import FALLBACK_TITLE, generate_title, heuristic_title


class TestHeuristicTitle:
    def test_short_message(self):
        result = heuristic_title("Покажи документы ОПП за вчера")
        # 5 слов, без знаков препинания — возвращает как есть (≤7 слов)
        assert result == "Покажи документы ОПП за вчера"

    def test_empty_string(self):
        assert heuristic_title("") == FALLBACK_TITLE

    def test_only_whitespace(self):
        assert heuristic_title("   ") == FALLBACK_TITLE

    def test_long_message_truncated(self):
        # Одно очень длинное слово без пробелов и знаков препинания
        long_msg = "А" * 100
        result = heuristic_title(long_msg)
        # Должно быть ≤ 60 символов (с "...")
        assert len(result) <= 60
        assert result.endswith("...")

    def test_cuts_at_exclamation(self):
        result = heuristic_title("Привет! Как дела?")
        # До первого ! → "Привет"
        assert result == "Привет"

    def test_cuts_at_question(self):
        result = heuristic_title("Что делать? Непонятно")
        assert result == "Что делать"

    def test_cuts_at_period(self):
        result = heuristic_title("Ответь. И ещё раз ответь пожалуйста")
        assert result == "Ответь"

    def test_cuts_at_comma(self):
        result = heuristic_title("Раз, два, три, четыре, пять")
        assert result == "Раз"

    def test_max_7_words(self):
        result = heuristic_title("один два три четыре пять шесть семь восемь девять десять")
        words = result.split()
        assert len(words) <= 7

    def test_returns_string(self):
        assert isinstance(heuristic_title("тест"), str)


class TestGenerateTitle:
    @pytest.mark.asyncio
    async def test_no_llm_client_uses_heuristic(self):
        result = await generate_title("Покажи ОПП документы", None, None)
        assert result == heuristic_title("Покажи ОПП документы")

    @pytest.mark.asyncio
    async def test_no_api_key_uses_heuristic(self):
        mock_llm = MagicMock()
        result = await generate_title("Покажи ОПП документы", mock_llm, None)
        assert result == heuristic_title("Покажи ОПП документы")

    @pytest.mark.asyncio
    async def test_llm_returns_title(self):
        """Мок LLM возвращает чанки с контентом."""
        mock_llm = MagicMock()

        async def fake_stream(*args, **kwargs):
            yield {"delta": {"content": "Запрос"}}
            yield {"delta": {"content": " ОПП"}}

        mock_llm.stream_chat_completion = fake_stream

        result = await generate_title("Покажи ОПП документы", mock_llm, "sk-test")
        assert result == "Запрос ОПП"

    @pytest.mark.asyncio
    async def test_llm_error_fallback_to_heuristic(self):
        """При ошибке LLM — fallback на heuristic."""
        import httpx

        mock_llm = MagicMock()

        async def failing_stream(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "rate limited",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
            # unreachable но нужно для AsyncGenerator
            yield {}  # type: ignore[misc]

        mock_llm.stream_chat_completion = failing_stream

        result = await generate_title("Покажи документы ОПП", mock_llm, "sk-test")
        # Должен вернуть heuristic
        assert result == heuristic_title("Покажи документы ОПП")

    @pytest.mark.asyncio
    async def test_llm_returns_empty_fallback_to_heuristic(self):
        """LLM возвращает пустую строку — fallback на heuristic."""
        mock_llm = MagicMock()

        async def empty_stream(*args, **kwargs):
            yield {"delta": {"content": ""}}
            yield {"delta": {}}

        mock_llm.stream_chat_completion = empty_stream

        result = await generate_title("Расскажи про базу данных клиента", mock_llm, "sk-test")
        assert result == heuristic_title("Расскажи про базу данных клиента")
