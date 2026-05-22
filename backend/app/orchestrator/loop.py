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
from app.learning.background_review import schedule_review
from app.learning.skill_store import SkillStore
from app.learning.skill_usage import SkillUsageStore
from app.memory.injection_scan import sanitize_for_prompt as scan_sanitize_for_prompt
from app.orchestrator.auxiliary import AuxiliaryClient
from app.orchestrator.clarify import (
    CLARIFY,
    CLARIFY_TIMEOUT_S,
    CLARIFY_TOOL_SCHEMA,
    is_clarify_tool,
    new_clarify_id,
    validate_args as validate_clarify_args,
)
from app.orchestrator.compressor import (
    compress,
    needs_compression,
)
from app.orchestrator.error_classifier import Action, classify
from app.orchestrator.interrupt import INTERRUPTS
from app.orchestrator.iteration_budget import BudgetExhausted, IterationBudget
from app.orchestrator.mcp_pool import MCPPool, build_aux_clients
from app.orchestrator.memory_integration import (
    build_memory_manager,
    build_trajectory_logger,
    dispatch_memory_tool,
    is_memory_tool,
    log_trajectory,
    memory_system_block,
    memory_tool_schemas,
    sync_memory_post_turn,
)
from app.orchestrator.sanitize import (
    repair_message_sequence,
    sanitize_messages,
)
from app.orchestrator.think_scrubber import ThinkScrubber
from app.orchestrator.todo import (
    TODO_TOOL_SCHEMAS,
    dispatch_todo_tool,
    is_todo_tool,
    render_todos_for_prompt,
)
from app.config import get_settings
from app.models import ChatRequest
from app.orchestrator.cards import _extract_anon_tokens_from_payload, build_card_from_tool_result
from app.orchestrator.events import (
    CardEvent,
    ClarifyRequiredEvent,
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
from app.orchestrator.result_gate import (
    apply_row_gate,
    build_llm_summary_for_truncated,
)
from app.orchestrator.safety import (
    CONFIRMATION_TIMEOUT_S,
    is_dangerous_tool,
    register_pending_confirmation,
    scan_for_dangerous,
    scan_query_ast,
    wait_for_confirmation,
)
from app.orchestrator.title import generate_title

logger = logging.getLogger(__name__)

# Tool iterations — фактически unlimited для аналитика.
# 100 — soft safety net, обычно не достигается (сложные find_references
# укладываются в 20-30). Главная защита — DUPLICATE_TOOL_CALL_THRESHOLD ниже.
# Sprint 2: используется IterationBudget из settings.iteration_budget,
# константа оставлена для обратной совместимости с тестами.
MAX_TOOL_ITERATIONS = 100

# Если LLM подряд делает > N одинаковых tool_call (имя + args) — break:
# это infinite loop, дальнейшие итерации не приблизят к ответу.
DUPLICATE_TOOL_CALL_THRESHOLD = 5
RETRY_DELAY_S = 0.2
TOOL_CONTENT_CAP = 50_000  # байт — cap для payload в LLM context

# Sprint 2: максимум попыток recompress+retry при ошибке context_overflow от LLM.
MAX_COMPRESS_RETRIES = 2

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

    # Sprint 1 (Hermes): персистентная память + trajectory log.
    # Failures здесь — best-effort: loop продолжается без memory если что-то ломается.
    memory_manager = build_memory_manager(settings, request.channel_id)
    trajectory_logger = build_trajectory_logger(settings)

    # Sprint 3 (Hermes A8/A9/D3): skill store + usage telemetry per канал.
    # Best-effort: при отсутствии настроек или ошибке init — продолжаем без skills.
    # P1.1 verified (2026-05-23): runtime wired через 3 точки:
    #   - инициализация SkillStore/SkillUsageStore (этот блок)
    #   - render_for_prompt + usage.increment ниже (build_system_prompt секция)
    #   - schedule_review fire-and-forget после _finalize_turn
    # См. .planning/COMMERCE-PLAN-2026-05-23.md → P1.1 verified false positive.
    skill_store: SkillStore | None = None
    skill_usage: SkillUsageStore | None = None
    if settings.memory_enabled:
        try:
            skills_root = settings.memory_root_path / "skills"
            skill_store = SkillStore(skills_root, request.channel_id)
            skill_usage = SkillUsageStore(skill_store.directory)
        except Exception:
            logger.warning("Не удалось инициализировать SkillStore — продолжаем без skills")
            skill_store = None
            skill_usage = None

    try:
        await pool.initialize_all()
        mcp_tools = await pool.list_all_tools()
        openai_tools = _mcp_tools_to_openai(mcp_tools)
        # Добавляем memory tool schemas (memory_append, memory_remove) к OpenAI tools.
        # LLM видит их в едином списке вместе с MCP-инструментами.
        openai_tools = openai_tools + memory_tool_schemas(memory_manager)
        # Sprint 3: todo_add / todo_complete / todo_list — internal tools.
        openai_tools = openai_tools + TODO_TOOL_SCHEMAS
        # Sprint 4: clarify_question — структурированные уточнения вместо free-text.
        openai_tools = openai_tools + [CLARIFY_TOOL_SCHEMA]
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

    # Собираем system prompt — статичный SYSTEM_PROMPT + memory block (если есть)
    # + skills block (Sprint 3) + todo block (Sprint 3).
    # Порядок: статика → memory → skills → todo. Todo последний — самый свежий контекст.
    mem_block = memory_system_block(memory_manager)
    skills_block = ""
    if skill_store is not None:
        try:
            skills_block = skill_store.render_for_prompt(max_chars=4_000)
            # Sprint 3 (A9): инкрементим usage для всех активных skills попавших в prompt.
            if skills_block and skill_usage is not None:
                for active_skill in skill_store.list_active():
                    if active_skill.id in skills_block:
                        try:
                            skill_usage.increment(active_skill.id)
                        except Exception:
                            logger.debug("Skill usage increment failed for %s", active_skill.id)
        except Exception:
            logger.warning("Skill render failed", exc_info=True)
            skills_block = ""

    todos_block = render_todos_for_prompt(session_id)

    prompt_parts = [SYSTEM_PROMPT]
    if mem_block:
        prompt_parts.append(mem_block)
    if skills_block:
        prompt_parts.append(skills_block)
    if todos_block:
        prompt_parts.append(todos_block)
    full_system_prompt = "\n\n".join(prompt_parts)

    messages: list[dict] = [
        {"role": "system", "content": full_system_prompt},
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

    # Sprint 2 (Hermes C1): thread-safe iteration budget вместо
    # range(MAX_TOOL_ITERATIONS). Бюджет из настроек env.
    budget = IterationBudget(total=max(1, settings.iteration_budget))

    # W1.3: бюджет MCP tool-call'ов на весь turn (user-message). Защита от
    # runaway parallel tool_calls: даже если LLM пройдёт все iterations,
    # каждая итерация с 5 parallel tools = 500 запросов в 1С. Лимит дефолтом 50.
    tool_calls_this_turn: int = 0
    max_tool_calls = max(1, settings.max_tool_calls_per_turn)

    # Sprint 2 (Hermes C9): scope cleanup interrupt registry для этой сессии.
    INTERRUPTS.clear(session_id)
    interrupted_by_user = False

    # Aux client — единая инстанция на loop. Используется:
    # - ContextCompressor (Sprint 2 / compression_enabled)
    # - background_review (Sprint 3 / learning_enabled) — fire-and-forget после turn
    #
    # W1.8 fix (2026-05-22): раньше aux client создавался ТОЛЬКО при
    # compression_enabled. Если compression выключена — schedule_review
    # тихо skip'ался (нет aux), и Sprint 3 «самообучение» не работало.
    # Теперь aux создаётся если включена ХОТЯ БЫ ОДНА из двух фич — это
    # развязывает зависимость learning от compression.
    aux_compressor_client: AuxiliaryClient | None = None
    needs_aux = settings.compression_enabled or settings.learning_enabled
    if needs_aux:
        try:
            aux_compressor_client = AuxiliaryClient(
                base_url=llm_endpoint,
                api_key=api_key,
                model=settings.aux_model or effective_llm_model,
                main_model=effective_llm_model,
            )
        except Exception:
            logger.warning(
                "Не удалось инициализировать aux client — compression "
                "и background_review будут работать в fallback режиме"
            )
            aux_compressor_client = None

    # W1.5 verified (2026-05-22): аудит подозревал утечку LLMClient при
    # GeneratorExit (закрытие SSE — навигация / browser tab close / AbortController).
    # Проверено:
    # - LLMClient инстанцируется per-iteration (loop.py:654) и закрывается
    #   в inner try/finally (loop.py:704-705) — даже при exception/cancel
    #   соответствующий .aclose() гарантированно вызывается.
    # - AuxiliaryClient (auxiliary.py:87) использует `async with httpx.AsyncClient`
    #   per-call — state не хранит, утечки нет.
    # - outer finally (loop.py:1056-1059) закрывает только mcp; этого достаточно
    #   потому что LLMClient уже закрыт в inner блоке.
    # Если в будущем AuxiliaryClient перейдёт на reuse httpx (W3.4 perf
    # optimization) — обязательно добавить здесь outer finally блок для его
    # aclose().
    try:
        while True:
            # --- Iteration budget gate ---
            try:
                budget.consume()
            except BudgetExhausted:
                logger.warning("Iteration budget exhausted (total=%d)", budget.total)
                yield format_sse("error", ErrorEvent(
                    message=f"Превышен бюджет итераций ({budget.total}). Уточните запрос.",
                    code="tool_loop_limit",
                ))
                return

            # --- User interrupt check (C9) ---
            if INTERRUPTS.should_interrupt(session_id):
                logger.info("Loop interrupted by user (session=%s)", session_id)
                interrupted_by_user = True
                break

            # --- Context compression pre-pass (B1/B5) ---
            if settings.compression_enabled and needs_compression(
                messages,
                max_context_tokens=settings.max_context_tokens,
                threshold_ratio=settings.compression_threshold_ratio,
            ):
                try:
                    comp = await compress(messages, aux_client=aux_compressor_client)
                    logger.info(
                        "Context compressed: %d→%d msgs, %d→%d tokens, pruned=%d",
                        comp.stats.messages_before,
                        comp.stats.messages_after,
                        comp.stats.tokens_before,
                        comp.stats.tokens_after,
                        comp.stats.pruned_tool_calls,
                    )
                    messages = comp.new_messages
                except Exception:
                    logger.exception("Ошибка ContextCompressor — продолжаю без сжатия")

            # --- Sanitize messages перед отправкой LLM (E6) ---
            messages = repair_message_sequence(sanitize_messages(messages))

            yield format_sse("status", StatusEvent(stage="thinking"))

            # Накапливаем tool_calls из streaming chunks
            chunk_tool_calls: dict[int, dict] = {}
            chunk_content = ""
            chunk_reasoning = ""  # reasoning-content (Xiaomi MiMo, DeepSeek R1 и др.)
            finish_reason: str | None = None
            # Sprint 4 (G7): thinking-tag scrubber для streamed content.
            think_scrubber = ThinkScrubber()

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
                            # Sprint 4 (G7): прячем <think>/<thinking>/<reasoning> теги
                            # из streamed view; в accumulated_content тоже идёт уже clean.
                            safe_piece = think_scrubber.feed(content_piece)
                            chunk_content += safe_piece
                            if safe_piece:
                                yield format_sse("delta", DeltaEvent(content=safe_piece))

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

            # Sprint 4 (G7): финальный flush — если поток оборвался не в think,
            # подбираем хвост; внутри think — отбрасываем.
            tail = think_scrubber.flush()
            if tail:
                chunk_content += tail
                yield format_sse("delta", DeltaEvent(content=tail))

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
                # W1.3: per-turn tool call budget gate.
                tool_calls_this_turn += 1
                if tool_calls_this_turn > max_tool_calls:
                    logger.warning(
                        "Tool call budget exhausted: turn=%d, limit=%d",
                        tool_calls_this_turn, max_tool_calls,
                    )
                    yield format_sse("error", ErrorEvent(
                        message=(
                            f"Слишком много обращений к 1С за один запрос "
                            f"(>{max_tool_calls}). Переформулируйте вопрос — "
                            f"возможно нужно сузить область или уточнить условия."
                        ),
                        code="tool_call_budget_exceeded",
                    ))
                    return

                tool_id = tc["id"]
                tool_name = tc["name"]
                tool_args = tc["args"]

                yield format_sse("tool_call", ToolCallEvent(
                    id=tool_id, name=tool_name, args=tool_args
                ))

                # SEC-01 / W1.2: проверяем dangerous keywords для опасных инструментов.
                # Раньше — только execute_code. С 2026-05-22 распространено на
                # execute_query (защита от SQL-DML инъекций через MCP Toolkit).
                # См. is_dangerous_tool() / _DANGEROUS_TOOL_NAMES в safety.py.
                #
                # P2.3 (2026-05-23): для execute_query поверх keyword-scan ещё
                # AST-валидация через sqlparse. Поймает то что keyword regex
                # пропустил (encoded/concatenated DELETE, комментарий-обходка).
                if is_dangerous_tool(tool_name):
                    danger_reason = scan_for_dangerous(tool_args) or scan_query_ast(
                        tool_name, tool_args
                    )
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
                # Sprint 1 (Hermes): memory_* tools → MemoryManager, не MCP.
                # Это internal tools — они не доходят до MCP-сервера.
                if is_memory_tool(tool_name):
                    ok, tool_result, tool_error = dispatch_memory_tool(
                        memory_manager, tool_name, tool_args
                    )
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    yield format_sse("tool_result", ToolResultEvent(
                        id=tool_id,
                        ok=ok,
                        result=tool_result if ok else None,
                        error=tool_error,
                        duration_ms=duration_ms,
                    ))
                    accumulated_tool_calls.append({
                        "id": tool_id,
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                        "error": tool_error,
                        "duration_ms": duration_ms,
                    })
                    tool_content = json.dumps(tool_result, ensure_ascii=False) if tool_result else (tool_error or "")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": _cap_content(tool_content),
                    })
                    continue

                # Sprint 4 (Hermes D1): clarify_question — диалог с пользователем
                # через SSE clarify_required. Loop ждёт ответ через future,
                # затем возвращает в LLM как tool result.
                if is_clarify_tool(tool_name):
                    try:
                        question, options, multi = validate_clarify_args(tool_args)
                    except ValueError as exc:
                        duration_ms = int((time.monotonic() - start_ts) * 1000)
                        yield format_sse("tool_result", ToolResultEvent(
                            id=tool_id, ok=False, error=str(exc), duration_ms=duration_ms,
                        ))
                        messages.append({
                            "role": "tool", "tool_call_id": tool_id,
                            "content": f"Невалидные args clarify_question: {exc}",
                        })
                        continue

                    clarify_id = new_clarify_id()
                    pending = CLARIFY.register(
                        clarify_id, question, options, multi=multi, allow_custom=True,
                    )
                    yield format_sse("clarify_required", ClarifyRequiredEvent(
                        clarify_id=clarify_id,
                        question=question,
                        options=options,
                        multi=multi,
                        allow_custom=True,
                    ))
                    try:
                        answer = await asyncio.wait_for(
                            pending.future, timeout=CLARIFY_TIMEOUT_S
                        )
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        CLARIFY.cancel(clarify_id)
                        yield format_sse("error", ErrorEvent(
                            message=(
                                f"Уточнение не получено за "
                                f"{int(CLARIFY_TIMEOUT_S / 60)} минут."
                            ),
                            code="clarify_timeout",
                        ))
                        return

                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    answer_str = (
                        ", ".join(answer) if isinstance(answer, list) else str(answer)
                    )
                    yield format_sse("tool_result", ToolResultEvent(
                        id=tool_id, ok=True,
                        result={"answer": answer_str},
                        duration_ms=duration_ms,
                    ))
                    accumulated_tool_calls.append({
                        "id": tool_id, "name": tool_name, "args": tool_args,
                        "result": {"answer": answer_str}, "error": None,
                        "duration_ms": duration_ms,
                    })
                    messages.append({
                        "role": "tool", "tool_call_id": tool_id,
                        "content": f"Пользователь выбрал: {answer_str}",
                    })
                    continue

                # Sprint 3 (Hermes D3): todo_* tools → TodoRegistry, не MCP.
                if is_todo_tool(tool_name):
                    ok, tool_result, tool_error = dispatch_todo_tool(
                        session_id, tool_name, tool_args
                    )
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    yield format_sse("tool_result", ToolResultEvent(
                        id=tool_id,
                        ok=ok,
                        result=tool_result if ok else None,
                        error=tool_error,
                        duration_ms=duration_ms,
                    ))
                    accumulated_tool_calls.append({
                        "id": tool_id,
                        "name": tool_name,
                        "args": tool_args,
                        "result": tool_result,
                        "error": tool_error,
                        "duration_ms": duration_ms,
                    })
                    tool_content = json.dumps(tool_result, ensure_ascii=False) if tool_result else (tool_error or "")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": _cap_content(tool_content),
                    })
                    continue

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

                # P2.2 ResultSizeGate (2026-05-23): для execute_query режем result
                # до MAX_ROWS_FOR_LLM=500 строк ДО формирования карточки и LLM-context.
                # Полный tool_result остаётся в accumulated_tool_calls (для
                # persist'а в tool_result_storage), но и LLM, и UI карточка
                # видят только capped версию с пометкой truncated=True.
                gated_result, gate_info = apply_row_gate(tool_name, tool_result) if ok else (tool_result, {"applied": False})

                # Детектируем карточку (на основе gated, не original — UI
                # покажет 500 строк + баннер «truncated»)
                if ok and gated_result is not None:
                    card = build_card_from_tool_result(tool_name, tool_args, gated_result)
                    if card is not None:
                        yield format_sse("card", CardEvent(type=card["type"], payload=card["payload"]))
                        accumulated_cards.append(card)

                # Сохраняем для последующей персистенции (используем original
                # tool_result — полный set, на случай load-more / CSV download).
                accumulated_tool_calls.append({
                    "id": tool_id,
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result,
                    "error": tool_error,
                    "duration_ms": duration_ms,
                })

                # Добавляем tool-результат в историю для LLM.
                # Sprint 4 (F1): tool output sanitize — данные из 1С могут содержать
                # prompt injection patterns (например, в Комментарии документа).
                #
                # P2.2: для LLM используем GATED result + summary с total/kept,
                # чтобы LLM знала что данные неполные и не сочиняла «всего N
                # строк» когда реально N+++.
                tool_content = json.dumps(gated_result, ensure_ascii=False) if gated_result else (tool_error or "")
                tool_content = scan_sanitize_for_prompt(tool_content)
                tool_content += build_llm_summary_for_truncated(tool_name, gate_info)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": _cap_content(tool_content),
                })

            yield format_sse("status", StatusEvent(stage="formatting"))

    except Exception as exc:
        logger.exception("Непредвиденная ошибка в tool-calling loop")
        yield format_sse("error", ErrorEvent(
            message=_safe_error_message(exc) or "Внутренняя ошибка обработки запроса",
            code="internal_error",
        ))
        return
    finally:
        # Sprint 2 (C9): снимаем флаг interrupt — даже если loop завершился сам.
        INTERRUPTS.clear(session_id)
        await mcp.aclose()
        # W3.4 (2026-05-22): aux_compressor_client теперь реально stateful
        # (переиспользуемый httpx). Закрываем в finally чтобы httpx connection
        # pool не оставался открытым после завершения loop.
        if aux_compressor_client is not None:
            try:
                await aux_compressor_client.aclose()
            except Exception:
                pass  # cleanup best-effort

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

    # Sprint 1 (Hermes): post-turn memory sync + trajectory log.
    # Best-effort — exceptions logged, не roняют ответ пользователю.
    sync_memory_post_turn(memory_manager, request.message, accumulated_content)
    log_trajectory(
        trajectory_logger,
        session_id=session_id,
        channel_id=request.channel_id,
        messages=messages,
        tool_calls=accumulated_tool_calls,
        completed=True,
        model=effective_llm_model,
        latency_ms=total_duration_ms,
    )

    # Sprint 3 (Hermes A5): background review fork — fire-and-forget.
    # Aux LLM решит, сохранить ли skill, не блокирует ответ пользователю.
    # Skip если: interrupted (turn неполный), skill_store отсутствует, нет accumulated_content.
    if (
        not interrupted_by_user
        and skill_store is not None
        and aux_compressor_client is not None
        and accumulated_content.strip()
    ):
        try:
            schedule_review(
                user_msg=request.message,
                assistant_msg=accumulated_content,
                tool_calls=accumulated_tool_calls,
                skill_store=skill_store,
                aux_client=aux_compressor_client,
            )
        except Exception:
            logger.debug("schedule_review failed", exc_info=True)

    yield format_sse("done", DoneEvent(
        message_id=message_id,
        total_duration_ms=total_duration_ms,
        interrupted=interrupted_by_user,
    ))
