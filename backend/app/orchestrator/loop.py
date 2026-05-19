"""Главный tool-calling loop: NL → LLM → MCP → LLM → done."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import aiosqlite
import httpx

from app.clients.llm import LLMClient, LLMRateLimitError
from app.clients.mcp import MCPClient, MCPDisconnectedError, MCPError
from app.orchestrator.attachments import (
    build_user_message_content,
    extract_attachment,
    make_history_user_text,
)

# Модель которая поддерживает vision. Для Xiaomi MiMo — `mimo-v2-omni`.
# Если активная модель — text-only, и пользователь прикрепил картинку,
# orchestrator временно (для этого запроса) переключается на VISION_MODEL.
# Эту константу можно вынести в Settings когда появятся другие провайдеры.
VISION_MODEL = "mimo-v2-omni"
from app.orchestrator.mcp_pool import MCPPool, build_aux_clients
from app.config import get_settings
from app.models import ChatRequest
from app.orchestrator.cards import _extract_anon_tokens_from_payload, build_card_from_tool_result
from app.orchestrator.events import (
    CardEvent,
    ConfirmRequiredEvent,
    DeltaEvent,
    DoneEvent,
    ErrorEvent,
    StatusEvent,
    ToolCallEvent,
    ToolResultEvent,
    format_sse,
)
from app.orchestrator.persistence import (
    count_session_messages,
    ensure_session,
    load_history_for_llm,
    lookup_mcp_endpoint,
    save_assistant_message,
    save_card_state,
    save_user_message,
    touch_session,
    update_session_title,
)
from app.orchestrator.safety import (
    CONFIRMATION_TIMEOUT_S,
    register_pending_confirmation,
    scan_for_dangerous,
    wait_for_confirmation,
)
from app.orchestrator.title import generate_title

logger = logging.getLogger(__name__)

# Tool iterations — фактически unlimited для аналитика.
# 100 — soft safety net, обычно не достигается (сложные find_references
# укладываются в 20-30). Главная защита — DUPLICATE_TOOL_CALL_THRESHOLD ниже.
MAX_TOOL_ITERATIONS = 100

# Если LLM подряд делает > N одинаковых tool_call (имя + args) — break:
# это infinite loop, дальнейшие итерации не приблизят к ответу.
DUPLICATE_TOOL_CALL_THRESHOLD = 5
RETRY_DELAY_S = 0.2
TOOL_CONTENT_CAP = 50_000  # байт — cap для payload в LLM context

SYSTEM_PROMPT = """Ты — аналитик 1С. Работаешь ТОЛЬКО с живой базой клиента через MCP-инструменты. Отвечаешь по-русски.

═══════ ЖЁСТКИЕ ПРАВИЛА ═══════

1. НИКОГДА не отвечай по «общим знаниям» о 1С. У тебя НЕТ права упоминать «типовые документы», «обычные справочники», «стандартные регистры» — даже если уверен. Только то что вернул инструмент.

2. Любой вопрос про КОНКРЕТНУЮ базу («какие документы», «сколько контрагентов», «есть ли регистр X», «покажи структуру», «найди в журнале», «когда было последнее проведение») = ОБЯЗАТЕЛЬНЫЙ вызов инструмента. Без исключений. Без «думаю что это…».

3. Если вопрос неоднозначный (например «покажи последние документы» — каких? за какой период?) — задай 1 короткий уточняющий вопрос вместо угадывания. НЕ запускай tool на угадай.

4. Если инструмент вернул пустой результат — так и пиши «не нашёл», не дополняй из «знаний».

5. Если инструмент дал большой payload (>50 строк) — покажи срез (первые 20-30) + общее число + предложи уточнить.

6. После каждого tool-вызова — короткий TL;DR на русском. Цифры из tool result, не из памяти.

═══════ ИНСТРУМЕНТЫ И КОГДА ИХ ЗВАТЬ ═══════

• get_metadata — структура конфигурации. Параметр meta_type ОБЯЗАТЕЛЕН для конкретики:
    «какие документы» / «список документов»  → meta_type="Документ"
    «справочники»                              → meta_type="Справочник"
    «регистры сведений»                        → meta_type="РегистрСведений"
    «регистры накопления»                      → meta_type="РегистрНакопления"
    «отчёты»                                   → meta_type="Отчет"
    «обработки»                                → meta_type="Обработка"
    «перечисления»                             → meta_type="Перечисление"
    «константы»                                → meta_type="Константа"
    «роли»                                     → meta_type="Роль"
    «подсистемы»                               → meta_type="Подсистема"
    «общие модули»                             → meta_type="ОбщийМодуль"
    «бизнес-процессы»                          → meta_type="БизнесПроцесс"
  Для общего обзора («что в базе вообще») — вызывай ПОСЛЕДОВАТЕЛЬНО get_metadata для каждого ключевого meta_type (минимум: Справочник + Документ + РегистрНакопления + РегистрСведений).
  name_mask — для поиска по подстроке имени (например, ИНН-документы → name_mask="Реализация").

• execute_query — реальный 1С-запрос к данным. Использовать для: количество записей, выборка строк, агрегаты, поиск по реквизитам. ВСЕГДА с лимитом (ВЫБРАТЬ ПЕРВЫЕ 100 …).

• execute_code — BSL-код для случаев которые нельзя выразить запросом. Опасные операции требуют подтверждения.

• get_event_log — журнал регистрации. Фильтры: severity, even_name, user, time range, metadata, data. Для «что случилось вчера / есть ошибки» — обязательно с фильтром по периоду.

• get_object_by_link — получить объект по навигационной ссылке (e:1cv8s://… или Документ.X:UUID).

• get_link_of_object — обратное.

• find_references_to_object — где используется объект метаданных (для рефакторинга / анализа зависимостей).

• get_access_rights — права роли или пользователя на объект.

• get_bsl_syntax_help — справочник встроенного языка / API платформы. Для вопросов «как вызвать», «какие параметры у X».

• submit_for_deanonymization — раскрытие анонимизированных значений в режиме маскировки.

═══════ ЭКСПЕРТНАЯ БАЗА ЗНАНИЙ 1С (ОБЯЗАТЕЛЬНО при составлении запросов и кода) ═══════

ЗАПРОСЫ — антипаттерны (НЕ делай так):
  ❌ Запрос в цикле — N+1 удар по БД. Используй пакетный запрос с «В (&Список)».
  ❌ Подзапрос в SELECT — выполняется на каждую строку. Замени на ЛЕВОЕ СОЕДИНЕНИЕ + группировку.
  ❌ Фильтр виртуальной таблицы в ГДЕ. Корректно — в параметрах ВТ:
      ИЗ РегистрНакопления.ТоварыНаСкладах.Остатки(, Склад = &Склад) КАК Остатки
  ❌ Точка к реквизитам ссылки (`Контрагент.ИНН`) — загружает весь объект. Используй
      ОбщегоНазначения.ЗначениеРеквизитаОбъекта() / ЗначенияРеквизитовОбъекта().
  ❌ Тернарный `?(условие, A, B)` — заменяй на ВЫБОР … КОГДА … ТОГДА … КОНЕЦ в запросе или Если…Иначе в BSL.
  ❌ ВЫРАЗИТЬ слева от ГДЕ — отключает индексы.

ЗАПРОСЫ — правила:
  ✓ ВСЕГДА `ВЫБРАТЬ ПЕРВЫЕ <N>` для проверки существования / превью / отчёта с пагинацией.
  ✓ Псевдонимы полей через `КАК`: `Контрагенты.ИНН КАК ИНН`.
  ✓ Временные таблицы — обязательно префикс `ВТ_`: `ПОМЕСТИТЬ ВТ_Товары`.
  ✓ Параметры через `&Имя`, передавай явно `Запрос.УстановитьПараметр("Имя", Значение)`.

BSL — критические правила:
  ❌ `ТекущаяДата()` — нарушает TZ. Используй `ТекущаяДатаСеанса()`.
  ❌ `Сообщить("...")` — устаревший паттерн. Server: `ОбщегоНазначения.СообщитьПользователю()`. Client: `ОбщегоНазначенияКлиент.СообщитьПользователю()`.
  ❌ `Если А = Истина Тогда` — пиши `Если А Тогда`.
  ❌ Hardcoded пути/пароли. Используй `ПолучитьИмяВременногоФайла()` и константы.
  ❌ `Выполнить(<строка>)` — запрещено в production.
  ✓ `ЗначениеЗаполнено(X)` универсальная проверка пустоты (вместо `= Неопределено` / `= Null`).
  ✓ Поиск в коллекции с >100 элементами — индекс через `Соответствие`, не `Найти()` в цикле.

БСП (Библиотека стандартных подсистем) — упоминай когда уместно:
  • Длительные операции — `ДлительныеОперации.ВыполнитьФункцию()` для фоновых задач.
  • Безопасное хранилище — для паролей/токенов интеграций.
  • Журнал регистрации — структурированные события через event_name «Подсистема.Операция.Исход».
  • Подписки на события — предпочитай прямым модификациям типового кода.

ТИПЫ МЕТАДАННЫХ — точные значения meta_type для get_metadata:
  Документ, Справочник, РегистрСведений, РегистрНакопления, РегистрБухгалтерии, РегистрРасчета,
  Отчет, Обработка, Перечисление, Константа, ОбщийМодуль, Подсистема, Роль, БизнесПроцесс,
  ПланВидовХарактеристик, ПланСчетов, ПланВидовРасчета, Задача, Последовательность, ЖурналДокументов.

═══════ ФОРМАТ ОТВЕТА ═══════

— Markdown: заголовки H3 максимум, таблицы только когда строк <30, иначе списки.
— Цитировать поля 1С как `Документ.РеализацияТоваровУслуг` (моно).
— Никаких эмодзи в заголовках и таблицах.
— TL;DR в 1 строке в конце ответа когда есть таблицы/списки.

═══════ ГРАФИКИ ═══════

Когда числовых данных много (≥4 точек) И их полезно сравнить визуально —
ВСТРАИВАЙ ГРАФИК прямо в ответ markdown-блоком ```chart\n{...JSON spec...}\n```.

Когда использовать график:
  • Сравнение количеств между категориями (>4 категорий) → bar
  • Изменение во времени (даты / периоды) → line
  • Доли от целого (части бюджета, распределение долей) → pie
  • Топ-N по показателю → bar
НЕ использовать график когда строк <4 или это просто справка/описание.

Формат spec (строго JSON, никаких комментариев):
```chart
{
  "type": "bar",
  "title": "Документы по типам",
  "description": "Топ-10 типов документов по количеству",
  "xKey": "тип",
  "yKeys": ["количество"],
  "data": [
    {"тип": "РеализацияТоваровУслуг", "количество": 1245},
    {"тип": "ПриходныйКассовыйОрдер", "количество": 890}
  ]
}
```

Для pie:
```chart
{
  "type": "pie",
  "title": "Доли по складам",
  "nameKey": "склад",
  "valueKey": "сумма",
  "data": [{"склад": "Центральный", "сумма": 1500}, {"склад": "Резервный", "сумма": 500}]
}
```

Для line (с несколькими сериями):
```chart
{
  "type": "line",
  "title": "Продажи по месяцам",
  "xKey": "месяц",
  "yKeys": ["январь", "февраль"],
  "data": [{"месяц": "1", "январь": 100, "февраль": 120}, ...]
}
```

ПРАВИЛА:
  ✓ Данные ТОЛЬКО реальные — из результатов tool_call, не выдумывать.
  ✓ После графика можешь дать TL;DR и комментарий.
  ✓ Если данные сами по себе наглядны (1-3 числа) — графиком НЕ перегружай, дай метрику текстом.
  ✗ Не вставляй пустой график-заглушку.
  ✗ Не используй комментарии (`//`) в JSON spec — это сломает парсинг.
"""


# Tools которые LLM НЕ ДОЛЖНА вызывать — destructive runtime management.
# Аналитику не нужно перезапускать или закрывать 1С-сессию. Если потребуется —
# это action пользователя через UI, не автоматическое решение модели.
_DANGEROUS_MCP_TOOLS = frozenset({
    "restart_1c_session",
    "close_1c_session",
})


def _mcp_tools_to_openai(mcp_tools: list[dict]) -> list[dict]:
    """Конвертирует MCP-схемы инструментов в OpenAI function format.

    Опасные runtime-tools (restart/close session) фильтруются — модель не должна
    иметь возможность рубануть 1С-сессию пользователя.
    """
    result = []
    for tool in mcp_tools:
        name = tool.get("name", "")
        if name in _DANGEROUS_MCP_TOOLS:
            continue
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        })
    return result


def _cap_content(content: str) -> str:
    """Обрезает строку до TOOL_CONTENT_CAP с маркером."""
    if len(content) <= TOOL_CONTENT_CAP:
        return content
    return content[:TOOL_CONTENT_CAP] + "...truncated"


def _safe_error_message(exc: Exception) -> str:
    """Возвращает безопасное сообщение об ошибке: только первая строка, ≤200 символов.

    Исключает Python traceback из сообщения — T-03-01.
    """
    raw = str(exc)
    # Берём только первую строку — отрезаем traceback
    first_line = raw.splitlines()[0] if raw else "Неизвестная ошибка"
    return first_line[:200]


async def _call_tool_with_retry(
    mcp,  # MCPClient | StdioMCPClient — единый интерфейс call_tool/aclose
    name: str,
    args: dict,
) -> tuple[bool, Any, str | None]:
    """Вызывает MCP-инструмент с 1 retry на сетевые ошибки и 5xx.

    Returns:
        (ok, result, error_message)

    Raises:
        MCPDisconnectedError: если ConnectError/Timeout не устраняется после retry.
    """
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = await mcp.call_tool(name, args)
            return True, result, None
        except MCPError as e:
            # JSON-RPC ошибка — 0 retry
            return False, None, str(e)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status < 500:
                # 4xx — 0 retry
                return False, None, f"HTTP {status}: {_safe_error_message(e)}"
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(RETRY_DELAY_S)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            # Сетевая ошибка — 1 retry; после 2 попыток → MCPDisconnectedError
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(RETRY_DELAY_S)
            else:
                raise MCPDisconnectedError("MCP недоступен") from e
        except httpx.RequestError as e:
            # Прочие сетевые ошибки — 1 retry
            last_exc = e
            if attempt == 0:
                await asyncio.sleep(RETRY_DELAY_S)
        except Exception as e:
            return False, None, f"Ошибка вызова инструмента: {_safe_error_message(e)}"

    error_msg = f"Ошибка после повтора: {_safe_error_message(last_exc) if last_exc else 'неизвестно'}"
    return False, None, error_msg


async def run_chat_loop(
    db: aiosqlite.Connection,
    request: ChatRequest,
    api_key: str,
    llm_endpoint: str,
    llm_model: str,
    x_anon_enabled: bool = False,
) -> AsyncIterator[str]:
    """Async-генератор SSE-событий: tool-calling loop.

    Args:
        x_anon_enabled: если True — MCPClient инициализируется с заголовком X-Anon-Enabled: true.

    Yields:
        SSE-строки в формате event: <name>\\ndata: <json>\\n\\n
    """
    loop_start = time.monotonic()

    # Первый байт ≤ 500 мс (NFR-1) — до всех I/O операций
    yield format_sse("status", StatusEvent(stage="thinking"))

    # --- Инициализация ---
    try:
        session_id = await ensure_session(
            db, request.session_id, request.channel_id, request.message[:60]
        )

        # Считаем сообщения ДО сохранения нового — чтобы знать первое ли это
        msg_count_before = await count_session_messages(db, session_id)

        # Извлекаем содержимое прикреплённых файлов. Текстовые (PDF/DOCX/XLSX/...)
        # склеиваются в string content. Изображения (PNG/JPG/...) — отдельные
        # image_url parts для multimodal LLM (mimo-v2-omni).
        extracted_attachments = (
            [
                extract_attachment(att.name, att.mime, att.content_base64)
                for att in request.attachments
            ]
            if request.attachments
            else []
        )
        user_message_content, has_image = build_user_message_content(
            request.message, extracted_attachments
        )

        # В БД сохраняем history-friendly текст — для картинок placeholder
        # (полное base64 в SQLite не нужно, follow-up видит «[Картинка: …]»).
        history_text = make_history_user_text(request.message, extracted_attachments)
        await save_user_message(db, session_id, history_text)

        # Vision auto-switch: если есть картинка и активная модель — text-only,
        # для текущего запроса используем VISION_MODEL. Конфиг backend не меняем.
        effective_llm_model = llm_model
        if has_image and llm_model != VISION_MODEL:
            logger.info(
                "Vision attachment detected — переключаю модель %s → %s для этого запроса",
                llm_model, VISION_MODEL,
            )
            effective_llm_model = VISION_MODEL

        mcp_endpoint = await lookup_mcp_endpoint(db, request.channel_id)
    except Exception:
        logger.exception("Ошибка инициализации loop")
        yield format_sse("error", ErrorEvent(message="Внутренняя ошибка", code="init_error"))
        return

    # Auto-title scheduled flag — реальный планировщик задачи переехал
    # в самый конец orchestrator-а (после yield done), чтобы:
    # 1) не съедать первый LLM-stub в тестах (FakeLLM share counter между
    #    auto-title и main loop) — async I/O ниже (load_history) даёт шанс
    #    auto-title запуститься раньше;
    # 2) UX: заголовок появляется уже после ответа модели — это даже логичнее.
    schedule_auto_title = msg_count_before == 0

    if mcp_endpoint is None:
        yield format_sse("error", ErrorEvent(
            message=f"Канал '{request.channel_id}' не найден. Настройте MCP-подключение.",
            code="unknown_channel",
        ))
        return

    # --- Получаем список инструментов (primary + aux MCPs) ---
    anon_headers = {"X-Anon-Enabled": "true"} if x_anon_enabled else None
    primary_mcp = MCPClient(mcp_endpoint, headers=anon_headers)
    settings = get_settings()
    aux_clients = build_aux_clients(settings)
    pool = MCPPool(primary_mcp, aux_clients)
    # Алиас для совместимости с finally блоком ниже и code paths которые
    # ссылаются на mcp напрямую (call_tool через router).
    mcp = pool

    try:
        await pool.initialize_all()
        mcp_tools = await pool.list_all_tools()
        openai_tools = _mcp_tools_to_openai(mcp_tools)
    except Exception:
        logger.exception("Ошибка инициализации MCP pool")
        yield format_sse("error", ErrorEvent(
            message="Не удалось подключиться к 1С MCP",
            code="mcp_disconnected",
        ))
        await pool.aclose()
        return

    # Подгружаем историю сессии — текущий user-message уже сохранён в БД
    # save_user_message() выше, поэтому войдёт в history. Модели нужно видеть
    # предыдущие user/assistant/tool обмены, иначе follow-up («покажи подотчётника
    # в них») теряет контекст.
    try:
        history_msgs = await load_history_for_llm(db, session_id)
    except Exception:
        logger.exception("Не удалось загрузить историю сессии %s — продолжаем без неё", session_id)
        history_msgs = [{"role": "user", "content": request.message}]

    if not history_msgs:
        # Защита от пустой истории (например, save_user_message не успел зафиксироваться)
        history_msgs = [{"role": "user", "content": request.message}]

    # Vision: history содержит placeholder «[Картинка: name.png]», но модель
    # должна получить реальное изображение в image_url. Подменяем content
    # ПОСЛЕДНЕГО user-сообщения (это текущий запрос) на multimodal parts.
    if has_image and history_msgs and history_msgs[-1].get("role") == "user":
        history_msgs = list(history_msgs)
        history_msgs[-1] = {"role": "user", "content": user_message_content}

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history_msgs,
    ]

    accumulated_content = ""
    accumulated_tool_calls: list[dict] = []
    accumulated_cards: list[dict] = []
    # Reasoning из ПОСЛЕДНЕЙ итерации LLM. MiMo / R1 в thinking mode требуют
    # вернуть reasoning_content при follow-up запросе с этим assistant
    # сообщением в history, иначе 400 «must be passed back to the API».
    final_reasoning_content: str = ""

    # Duplicate tool_call detector — защита от LLM-зацикливания на одном вызове.
    # Храним сигнатуры (name + JSON args) последних вызовов и считаем подряд.
    last_tool_signature: str | None = None
    duplicate_count: int = 0

    try:
        for _iteration in range(MAX_TOOL_ITERATIONS):
            yield format_sse("status", StatusEvent(stage="thinking"))

            # Накапливаем tool_calls из streaming chunks
            chunk_tool_calls: dict[int, dict] = {}
            chunk_content = ""
            chunk_reasoning = ""  # reasoning-content (Xiaomi MiMo, DeepSeek R1 и др.)
            finish_reason: str | None = None

            try:
                llm = LLMClient(endpoint=llm_endpoint, model=effective_llm_model)
                try:
                    async for chunk in llm.stream_chat_completion(
                        messages=messages,
                        api_key=api_key,
                        tools=openai_tools if openai_tools else None,
                    ):
                        delta = chunk.get("delta", {})

                        # Накапливаем текстовый контент
                        content_piece = delta.get("content")
                        if content_piece:
                            chunk_content += content_piece
                            yield format_sse("delta", DeltaEvent(content=content_piece))

                        # Reasoning-content (Xiaomi MiMo, DeepSeek R1) — для thinking mode:
                        # модель требует вернуть свой reasoning обратно в следующем round
                        # вместе с tool_calls (иначе 400 "Param Incorrect").
                        # Юзеру не показываем — это внутренняя цепь рассуждений.
                        reasoning_piece = delta.get("reasoning_content")
                        if reasoning_piece:
                            chunk_reasoning += reasoning_piece

                        # Накапливаем tool_calls по index (arguments приходят частями).
                        # `or []` — некоторые LLM (Xiaomi MiMo, reasoning-модели)
                        # возвращают `"tool_calls": null` в delta вместо отсутствующего ключа.
                        tool_calls_delta = delta.get("tool_calls") or []
                        for tc in tool_calls_delta:
                            idx = tc.get("index", 0)
                            if idx not in chunk_tool_calls:
                                chunk_tool_calls[idx] = {
                                    "id": tc.get("id", ""),
                                    "name": tc.get("function", {}).get("name", ""),
                                    "arguments": "",
                                }
                            if tc.get("id"):
                                chunk_tool_calls[idx]["id"] = tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                chunk_tool_calls[idx]["name"] = fn["name"]
                            if fn.get("arguments"):
                                chunk_tool_calls[idx]["arguments"] += fn["arguments"]

                        fr = chunk.get("finish_reason")
                        if fr:
                            finish_reason = fr
                finally:
                    await llm.aclose()
            except LLMRateLimitError as exc:
                logger.warning("LLM rate limit (429): retry_after_s=%s", exc.retry_after_s)
                yield format_sse("error", ErrorEvent(
                    message="Превышен лимит запросов к LLM. Попробуйте позже.",
                    code="llm_rate_limit",
                    retry_after_s=exc.retry_after_s,
                ))
                return
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    logger.warning("LLM auth error (%s)", status)
                    yield format_sse("error", ErrorEvent(
                        message="Неверный API-ключ или нет доступа к LLM.",
                        code="llm_invalid_key",
                    ))
                    return
                logger.warning("LLM HTTP error %s: %s", status, _safe_error_message(exc))
                yield format_sse("error", ErrorEvent(
                    message=f"Ошибка LLM-сервера (HTTP {status}).",
                    code="llm_server_error",
                ))
                return
            except httpx.RequestError as exc:
                logger.warning("LLM network error: %s", _safe_error_message(exc))
                yield format_sse("error", ErrorEvent(
                    message="Сетевая ошибка при обращении к LLM.",
                    code="llm_network_error",
                ))
                return

            accumulated_content += chunk_content
            # Сохраняем reasoning последней итерации (thinking-mode моделей).
            # Перезаписывает значение из предыдущей итерации намеренно —
            # для follow-up важен reasoning финального ответа, не промежуточных.
            if chunk_reasoning:
                final_reasoning_content = chunk_reasoning

            # Нет tool_calls — обычный финальный ответ
            if not chunk_tool_calls or finish_reason == "stop":
                break

            # Финализируем tool_calls: парсим JSON arguments
            finalized: list[dict] = []
            for idx in sorted(chunk_tool_calls.keys()):
                tc = chunk_tool_calls[idx]
                raw_args = tc.get("arguments", "{}")
                try:
                    args_dict = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    args_dict = {}
                finalized.append({
                    "id": tc["id"],
                    "name": tc["name"],
                    "args": args_dict,
                })

            # Duplicate detector: считаем подряд одинаковые вызовы (имя + args).
            # >5 одинаковых = LLM зациклилась на одном tool, прерываем.
            current_signature = json.dumps(
                [(tc["name"], tc["args"]) for tc in finalized],
                ensure_ascii=False,
                sort_keys=True,
            )
            if current_signature == last_tool_signature:
                duplicate_count += 1
                if duplicate_count >= DUPLICATE_TOOL_CALL_THRESHOLD:
                    logger.warning(
                        "LLM зациклилась на одинаковом tool_call (%d подряд), прерываю",
                        duplicate_count,
                    )
                    yield format_sse("error", ErrorEvent(
                        message=(
                            f"Модель повторяет один и тот же вызов "
                            f"{DUPLICATE_TOOL_CALL_THRESHOLD} раз подряд. "
                            "Похоже на зацикливание — уточните запрос."
                        ),
                        code="duplicate_tool_loop",
                    ))
                    return
            else:
                duplicate_count = 1
                last_tool_signature = current_signature

            # Добавляем assistant-сообщение с tool_calls в историю
            assistant_tool_calls = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc.get("arguments", "{}")},
                }
                for tc in chunk_tool_calls.values()
            ]
            assistant_msg: dict = {
                "role": "assistant",
                "content": chunk_content or None,
                "tool_calls": assistant_tool_calls,
            }
            # Reasoning-модели (Xiaomi MiMo thinking, DeepSeek R1) требуют вернуть
            # `reasoning_content` обратно в следующем round, иначе 400 Param Incorrect.
            if chunk_reasoning:
                assistant_msg["reasoning_content"] = chunk_reasoning
            messages.append(assistant_msg)

            # Вызываем каждый tool
            yield format_sse("status", StatusEvent(stage="calling_tool"))

            for tc in finalized:
                tool_id = tc["id"]
                tool_name = tc["name"]
                tool_args = tc["args"]

                yield format_sse("tool_call", ToolCallEvent(
                    id=tool_id, name=tool_name, args=tool_args
                ))

                # SEC-01: проверяем dangerous keywords для execute_code
                if tool_name == "execute_code":
                    danger_reason = scan_for_dangerous(tool_args)
                    if danger_reason:
                        register_pending_confirmation(tool_id)
                        yield format_sse("confirm_required", ConfirmRequiredEvent(
                            tool_call_id=tool_id,
                            name=tool_name,
                            args=tool_args,
                            reason=danger_reason,
                        ))
                        approved = await wait_for_confirmation(tool_id, CONFIRMATION_TIMEOUT_S)
                        if approved is None:
                            yield format_sse("error", ErrorEvent(
                                message=f"Подтверждение не получено за {int(CONFIRMATION_TIMEOUT_S)} секунд",
                                code="dangerous_keyword_blocked",
                            ))
                            return
                        if approved is False:
                            yield format_sse("error", ErrorEvent(
                                message="Пользователь отменил выполнение",
                                code="user_declined",
                            ))
                            return
                        # approved is True — продолжаем как обычно

                start_ts = time.monotonic()
                # Маршрутизация tool_call → правильный MCP client (primary или aux).
                tool_client = pool.client_for(tool_name)
                try:
                    ok, tool_result, tool_error = await _call_tool_with_retry(tool_client, tool_name, tool_args)
                except MCPDisconnectedError:
                    logger.warning("MCP disconnected during tool call: %s", tool_name)
                    yield format_sse("error", ErrorEvent(
                        message="Соединение с 1С MCP потеряно.",
                        code="mcp_disconnected",
                    ))
                    return
                duration_ms = int((time.monotonic() - start_ts) * 1000)

                yield format_sse("tool_result", ToolResultEvent(
                    id=tool_id,
                    ok=ok,
                    result=tool_result if ok else None,
                    error=tool_error,
                    duration_ms=duration_ms,
                ))

                # Детектируем карточку
                if ok and tool_result is not None:
                    card = build_card_from_tool_result(tool_name, tool_args, tool_result)
                    if card is not None:
                        yield format_sse("card", CardEvent(type=card["type"], payload=card["payload"]))
                        accumulated_cards.append(card)

                # Сохраняем для последующей персистенции
                accumulated_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "error": tool_error,
                    "duration_ms": duration_ms,
                })

                # Добавляем tool-результат в историю для LLM
                tool_content = json.dumps(tool_result, ensure_ascii=False) if tool_result else (tool_error or "")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": _cap_content(tool_content),
                })

            yield format_sse("status", StatusEvent(stage="formatting"))

        else:
            # Вышли по лимиту итераций
            yield format_sse("error", ErrorEvent(
                message="Превышен лимит вызовов tools (10)",
                code="tool_loop_limit",
            ))
            return

    except Exception as exc:
        logger.exception("Непредвиденная ошибка в tool-calling loop")
        yield format_sse("error", ErrorEvent(
            message=_safe_error_message(exc) or "Внутренняя ошибка обработки запроса",
            code="internal_error",
        ))
        return
    finally:
        await mcp.aclose()

    # --- Сохраняем результат в БД ---
    total_duration_ms = int((time.monotonic() - loop_start) * 1000)
    try:
        message_id = await save_assistant_message(
            db,
            session_id,
            accumulated_content,
            accumulated_tool_calls,
            accumulated_cards,
            total_duration_ms,
            reasoning_content=final_reasoning_content or None,
        )
        await touch_session(db, session_id)

        # Сохраняем card_state для карточек (load-more endpoint + deanonymize)
        # Выполняется ПОСЛЕ save_assistant_message чтобы иметь реальный message_id
        #
        # - LogCard всегда сохраняется (нужен card_id для load-more, Plan 03-04)
        # - Table/Object карточки сохраняются только если x_anon_enabled (для deanonymize, Plan 04-01)
        _TOOL_FOR_CARD_TYPE = {
            "log": "get_event_log",
            "table": "execute_query",
            "object": "get_object_by_link",
            "metric": "execute_query",
            "references": "find_references_to_object",
            "code": "execute_code",
        }
        for card in accumulated_cards:
            card_type = card.get("type")
            card_id = card.get("payload", {}).get("card_id")
            if not card_id:
                continue
            # Determine если надо сохранять
            save_this = card_type == "log" or x_anon_enabled
            if not save_this:
                continue

            tool_name_for_card = _TOOL_FOR_CARD_TYPE.get(card_type, "")
            # Находим соответствующий tool_call для args
            card_tool_args: dict = {}
            for tc in accumulated_tool_calls:
                if tc.get("name") == tool_name_for_card:
                    card_tool_args = tc.get("args", {})
                    break

            # Вычисляем anon_tokens если anon режим
            anon_tokens: list[str] | None = None
            if x_anon_enabled:
                anon_tokens = _extract_anon_tokens_from_payload(card.get("payload", {}))

            try:
                await save_card_state(
                    db,
                    card_id=card_id,
                    session_id=session_id,
                    message_id=message_id,
                    tool_name=tool_name_for_card,
                    original_args=card_tool_args,
                    channel_id=request.channel_id,
                    anon_tokens=anon_tokens,
                )
            except Exception:
                logger.warning("Не удалось сохранить card_state для card %s", card_id)

    except Exception:
        logger.exception("Ошибка сохранения assistant message")
        message_id = "unknown"

    # --- Auto-title background task для первого сообщения ---
    # Шедулим здесь, а не на старте orchestrator-а: иначе async I/O ниже
    # (load_history_for_llm) даёт auto-title шанс запуститься раньше и
    # в тестах с FakeLLM (shared counter) съесть первый stub. После
    # завершения основного цикла LLMClient уже не используется — безопасно.
    if schedule_auto_title:
        async def _run_auto_title() -> None:
            try:
                llm = LLMClient(endpoint=llm_endpoint, model=llm_model)
                new_title = await generate_title(request.message, llm, api_key)
                await update_session_title(db, session_id, new_title)
                await llm.aclose()
            except Exception:
                logger.warning("Auto-title background task failed for session %s", session_id)

        asyncio.create_task(_run_auto_title())

    yield format_sse("done", DoneEvent(
        message_id=message_id,
        total_duration_ms=total_duration_ms,
    ))
