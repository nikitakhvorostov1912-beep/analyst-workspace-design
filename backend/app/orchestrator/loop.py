"""Главный tool-calling loop: NL → LLM → MCP → LLM → done.

КАРТА ФУНКЦИИ `run_chat_loop` (для будущей декомпозиции P1.2, отложен v1.4.0):

    1. Инициализация контекста (мог бы стать `_initialize_loop_context`):
       - settings + endpoint resolution
       - session ensure + history load
       - MCP pool + aux clients
       - SkillStore / SkillUsageStore / TodoRegistry
       - MemoryManager
       - LLMClient lifecycle

    2. System prompt сборка (`_build_system_prompt_with_context`):
       - memory_system_block
       - skills_block = skill_store.render_for_prompt
       - todos_block = render_todos_for_prompt
       - инжектится в messages[0]

    3. Main while loop — iteration budget + interrupt check:
       - LLM stream chunk-by-chunk → assistant message
       - если tool_calls — обрабатываем последовательно (`_handle_tool_call`):
         a. safety scan (dangerous keywords + SQL AST) → confirm_required
         b. routing memory/clarify/todo/MCP
         c. result_gate cap для больших results
         d. card building + accumulated_tool_calls + sanitize for prompt
       - если нет tool_calls → выход из loop

    4. Финализация (`_finalize_turn`):
       - save_assistant_message + accumulated_cards
       - persist card_states для load-more
       - generate_title (первое сообщение)
       - schedule_review fire-and-forget (Sprint 3 Hermes)
       - cleanup: mcp.aclose, aux_compressor_client.aclose, INTERRUPTS.clear

P1.2 — извлечь 4 функции и LoopContext dataclass.
Текущий размер: 1230+ строк. Цель: ≤400 строк в run_chat_loop.
"""

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
from app.config import get_settings
from app.learning.background_review import schedule_review
from app.learning.skill_store import SkillStore
from app.learning.skill_usage import SkillUsageStore
from app.memory.injection_scan import sanitize_for_prompt as scan_sanitize_for_prompt
from app.models import ChatRequest
from app.orchestrator.attachments import (
    build_user_message_content,
    extract_attachment,
    make_history_user_text,
)
from app.orchestrator.auxiliary import AuxiliaryClient
from app.orchestrator.cards import _extract_anon_tokens_from_payload, build_card_from_tool_result
from app.orchestrator.clarify import (
    CLARIFY,
    CLARIFY_TIMEOUT_S,
    CLARIFY_TOOL_SCHEMA,
    is_clarify_tool,
    new_clarify_id,
)
from app.orchestrator.clarify import validate_args as validate_clarify_args
from app.orchestrator.compressor import (
    compress,
    needs_compression,
)
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
from app.orchestrator.mentions_prefetch import prefetch_mentions
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
from app.orchestrator.sanitize import (
    repair_message_sequence,
    sanitize_messages,
)
from app.orchestrator.think_scrubber import ThinkScrubber
from app.orchestrator.title import generate_title
from app.orchestrator.todo import (
    TODO_TOOL_SCHEMAS,
    dispatch_todo_tool,
    is_todo_tool,
    render_todos_for_prompt,
)

logger = logging.getLogger(__name__)

# Модель которая поддерживает vision. Для Xiaomi MiMo — `mimo-v2-omni`.
# Если активная модель — text-only, и пользователь прикрепил картинку,
# orchestrator временно (для этого запроса) переключается на VISION_MODEL.
# Эту константу можно вынести в Settings когда появятся другие провайдеры.
VISION_MODEL = "mimo-v2-omni"


# BE-2 (M-K0.2, 2026-05-25): module-level set для fire-and-forget tasks.
# asyncio.create_task без сохранения ссылки → GC может собрать task до
# выполнения. Храним ссылку до завершения через add_done_callback(.discard).
# Сейчас используется для auto-title; расширяется по мере появления других
# background tasks (skill review, etc.).
_AUTO_TITLE_TASKS: set[asyncio.Task] = set()
_BACKGROUND_TASKS: set[asyncio.Task] = set()

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

═══════ ПРИМЕРЫ ВЫБОРА TOOL (few-shot) ═══════

Эти примеры показывают какой tool правильно выбрать для типового класса вопроса.
Если вопрос пользователя похож на один из примеров — действуй по аналогии.

──── СТРУКТУРА БАЗЫ (метаданные) → get_metadata ────

Q: «Какие документы есть в базе?»
A: get_metadata(meta_type="Документ")    [НЕ execute_query — это про структуру, не данные]

Q: «Какие справочники с именем Контр…?»
A: get_metadata(meta_type="Справочник", name_mask="Контр")

Q: «Покажи структуру документа РеализацияТоваровУслуг»
A: get_metadata(meta_type="Документ", name_mask="РеализацияТоваровУслуг")
   [Для деталей одного объекта — meta_type + точное имя в name_mask]

Q: «Что вообще в этой базе?» / «Сделай обзор конфигурации»
A: get_metadata(meta_type="Документ") → get_metadata(meta_type="Справочник") →
   get_metadata(meta_type="РегистрНакопления") → get_metadata(meta_type="РегистрСведений")
   [Параллельно или последовательно. НЕ execute_query — это discovery, не выборка]

──── ВЫБОРКА ДАННЫХ → execute_query ────

Q: «Сколько контрагентов в базе?»
A: execute_query("ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Кол ИЗ Справочник.Контрагенты")
   [Агрегат по данным — execute_query, НЕ get_metadata]

Q: «Покажи 10 последних документов реализации»
A: execute_query("ВЫБРАТЬ ПЕРВЫЕ 10 Ссылка, Дата, Номер, Контрагент ИЗ
                  Документ.РеализацияТоваровУслуг УПОРЯДОЧИТЬ ПО Дата УБЫВ")

Q: «Найди контрагента по ИНН 7707083893»
A: execute_query("ВЫБРАТЬ Ссылка, Наименование ИЗ Справочник.Контрагенты
                  ГДЕ ИНН = &ИНН", params={"ИНН": "7707083893"})

──── ДИАГНОСТИКА / СОБЫТИЯ → get_event_log ────

Q: «Что случилось вчера с базой?» / «Были ли ошибки за последний час?»
A: get_event_log(severity=["Ошибка"], date_from="<вчера>", date_to="<сейчас>")
   [НЕ execute_query — журнал регистрации это отдельный API, не таблица данных]

Q: «Кто провёл документ X 20.04.2026?»
A: get_event_log(metadata="Документ.РеализацияТоваровУслуг.<UUID>",
                  date_from="2026-04-20", date_to="2026-04-21",
                  event_name=["_$Data$_.Post"])

──── ЗАВИСИМОСТИ → find_references_to_object ────

Q: «Где используется справочник Контрагенты?»
A: find_references_to_object(object_path="Справочник.Контрагенты")
   [НЕ execute_query — это анализ метаданных-зависимостей, не выборка]

Q: «Что сломается если переименовать реквизит Сумма у документа Реализация?»
A: find_references_to_object(object_path="Документ.РеализацияТоваровУслуг.Реквизит.Сумма")
   [Impact analysis — find_references, потом анализ результата]

──── ПРАВА → get_access_rights ────

Q: «Какие права у роли БухгалтерУчёт на документ Реализация?»
A: get_access_rights(role="БухгалтерУчёт", object_path="Документ.РеализацияТоваровУслуг")
   [НЕ execute_query — права это отдельный API метаданных]

Q: «Почему Иванов не видит документ X?»
A: 1) get_access_rights(user="Иванов", object_path="Документ.X")
   2) Анализ результата: какое ограничение блокирует

──── ПЕРЕХОДЫ ССЫЛКА↔ОБЪЕКТ → get_object_by_link / get_link_of_object ────

Q: «Что лежит по ссылке e1cib/data/Документ.Реализация?...»
A: get_object_by_link(link="e1cib/...")

──── СПРАВКА ПО ЯЗЫКУ → get_bsl_syntax_help ────

Q: «Какие параметры у функции ОбщегоНазначения.ЗначениеРеквизитаОбъекта?»
A: get_bsl_syntax_help(query="ОбщегоНазначения.ЗначениеРеквизитаОбъекта")
   [НЕ execute_code — это документация платформы, не выполнение]

Q: «Как правильно открыть форму программно?»
A: get_bsl_syntax_help(query="ОткрытьФорму")

──── ПРОИЗВОЛЬНЫЙ BSL → execute_code (РЕДКО, только если нет другого пути) ────

Q: «Запусти регламентное задание X прямо сейчас»
A: execute_code("РегламентныеЗадания.НайтиПоИдентификатору(...).ВыполнитьВручную()")
   [Опасная операция — требует подтверждения пользователя]

Q: «Создай тестового контрагента с ИНН Y» (mutation!)
A: execute_code("Контрагент = Справочники.Контрагенты.СоздатьЭлемент();
                Контрагент.ИНН = '...'; Контрагент.Записать();")
   [Опасная — confirmation. Если возможно через UI 1С — лучше предложить туда]

──── КОГДА TOOL НЕ НУЖЕН ────

Q: «Что такое БСП?» / «Объясни RLS в 1С»
A: Ответ из общих знаний 1С. TOOL НЕ ЗВАТЬ — это методология, не данные базы.

Q: «Напиши шаблон запроса для остатков по складу»
A: Ответ — готовый BSL/Запрос в код-блоке из своих знаний.
   TOOL НЕ ЗВАТЬ — это code generation, не data fetch.

──── АНТИ-ПАТТЕРНЫ (НЕ ДЕЛАЙ ТАК) ────

❌ Q «Какие документы?» → execute_query("ВЫБРАТЬ ... ИЗ Документ.*") — нет такого синтаксиса.
   ✓ Корректно: get_metadata(meta_type="Документ")

❌ Q «Где используется регистр X?» → execute_query (нет таблицы зависимостей в 1С).
   ✓ Корректно: find_references_to_object(object_path="РегистрНакопления.X")

❌ Q «Сколько ошибок вчера?» → execute_query на несуществующую таблицу журнала.
   ✓ Корректно: get_event_log(severity=["Ошибка"], date_from=..., date_to=...)

❌ Q «Какие методы у Запрос?» → execute_code("Для Каждого метод Из Метаданные.Запрос...").
   ✓ Корректно: get_bsl_syntax_help(query="Запрос")

═══════ ПАМЯТЬ (memory_append / memory_remove) — КОГДА ЗАПИСЫВАТЬ ═══════

Если включена память (видишь блок <persistent-memory> в начале — это твой
долговременный контекст по каналу/пользователю), действуй по правилам:

──── 1. ЧИТАЙ ПАМЯТЬ ПЕРЕД ОТВЕТОМ ────

Перед каждым ответом — **сверься с <persistent-memory>**. Если там уже есть
ответ или релевантный факт — используй его, не переспрашивай пользователя
о том, что уже зафиксировано.

Пример:
  Память содержит: «База ut_rt_copy = копия Русского Транзита, не править»
  Q пользователя: «можно ли в этой базе изменить документ?»
  ✓ Корректно: «Эта база — копия Русского Транзита по твоей фиксации в памяти,
     писать не следует. Хочешь посмотреть данные read-only?»
  ❌ Неправильно: «А какая это база?» (игнорируешь известный факт)

──── 2. КОГДА ВЫЗЫВАТЬ memory_append (ЗАПИСАТЬ ФАКТ) ────

Записывай факт **только** если он отвечает ВСЕМ критериям:
  (a) Переиспользуем в будущих сессиях (не «здесь и сейчас»)
  (b) Не выводится из метаданных (то что можно получить через get_metadata
      — НЕ память, это live данные)
  (c) Конкретен и формулируем в 1-3 предложения

Хорошие примеры записи:

Q: «Запомни: эта база — копия продакшена, любые мутации запрещены»
A: memory_append(namespace="agent", content="База ut_rt_copy — read-only копия
   prod. Мутирующие операции (execute_code с записью, удаление) запрещены.",
   section="Режим работы")

Q: «У нас prefix всех новых объектов — РТ_, не АП_»
A: memory_append(namespace="agent", content="Префикс новых объектов в этой
   конфигурации — РТ_ (Русский Транзит). НЕ использовать АП_.",
   section="Конвенции базы")

Q: (после серии похожих запросов) «обычно я смотрю последние 30 дней»
A: memory_append(namespace="user", content="По умолчанию аналитик смотрит
   данные за последние 30 дней (не текущий месяц).",
   section="Предпочтения по периодам")

──── 3. КОГДА НЕ ВЫЗЫВАТЬ memory_append ────

❌ Сиюминутные факты: «сейчас 16:30», «текущий месяц апрель»
❌ Очевидное из get_metadata: «есть документ РеализацияТоваровУслуг»
   (можно перепроверить любой момент)
❌ Содержимое прошлого диалога: «пользователь спросил про контрагентов»
   (для этого есть session history, не память)
❌ Гипотезы: «возможно у пользователя проблема X» — не записывай предположения
❌ Дубликаты: если в памяти уже есть та же мысль — НЕ дублируй

──── 4. КОГДА ВЫЗЫВАТЬ memory_remove ────

Удаляй когда: (a) пользователь явно сказал «забудь X», или (b) ты только что
получил факт явно противоречащий существующей записи (refresh).

Q: «Забудь про prefix РТ_, теперь у нас АП_»
A: memory_remove(namespace="agent", match="префикс") +
   memory_append(namespace="agent", content="Префикс — АП_ (с 2026-05-25).",
   section="Конвенции базы")

Q: (узнал через get_metadata что версия БСП обновилась с 3.1.10 на 3.1.12)
A: memory_remove(namespace="agent", match="БСП 3.1.10") +
   memory_append(namespace="agent", content="Версия БСП в этой базе: 3.1.12
   (обновилось).", section="Версии")

──── 5. NAMESPACE — agent vs user ────

  • namespace="agent" — про **окружение, базу, паттерны кода, конвенции**.
    Будет видно во всех сессиях этого канала (любой аналитик).
  • namespace="user" — про **личные предпочтения** конкретного пользователя
    (рабочие периоды, любимые отчёты, стиль ответов).

Если непонятно куда — выбирай "agent" (общее) по умолчанию.

──── 6. АНТИ-ПАТТЕРНЫ memory ────

❌ Записывать каждый ответ — память не лог, это конденсат знаний
❌ Записывать без явного триггера от пользователя или явной пользы для
   будущих сессий
❌ Записывать «то что я предположил» — только подтверждённые факты
❌ Игнорировать <persistent-memory> блок и заново задавать вопросы
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


# Соответствие card.type → MCP tool который её произвёл. Используется при
# восстановлении args из accumulated_tool_calls для save_card_state.
_TOOL_FOR_CARD_TYPE: dict[str, str] = {
    "log": "get_event_log",
    "table": "execute_query",
    "object": "get_object_by_link",
    "metric": "execute_query",
    "references": "find_references_to_object",
    "code": "execute_code",
}


async def _load_history_safe(
    db: aiosqlite.Connection,
    session_id: str,
    fallback_message: str,
) -> list[dict]:
    """Загружает историю сессии для LLM с fallback на single-message при ошибке.

    Извлечено из run_chat_loop как часть P1.2 phase 3 step 3.

    Если load_history_for_llm падает или возвращает пустой список — возвращаем
    [{"role": "user", "content": fallback_message}] чтобы LLM получила хотя бы
    текущий запрос (save_user_message может не успеть commit'нуться на slow IO).
    """
    try:
        history_msgs = await load_history_for_llm(db, session_id)
    except Exception:
        logger.exception(
            "Не удалось загрузить историю сессии %s — продолжаем без неё", session_id
        )
        history_msgs = [{"role": "user", "content": fallback_message}]
    if not history_msgs:
        history_msgs = [{"role": "user", "content": fallback_message}]
    return history_msgs


def _render_skills_block(
    skill_store: SkillStore | None,
    skill_usage: SkillUsageStore | None,
) -> str:
    """Рендер skills блока + инкремент usage telemetry для активных skills.

    Sprint 3 A9: инкрементим counter для каждого skill_id найденного в
    отрендеренном prompt. Best-effort: ошибки render / increment логируются
    и не падают loop.

    Извлечено из run_chat_loop как часть P1.2 phase 3 step 3.
    """
    if skill_store is None:
        return ""
    try:
        skills_block = skill_store.render_for_prompt(max_chars=4_000)
    except Exception:
        logger.warning("Skill render failed", exc_info=True)
        return ""
    if skills_block and skill_usage is not None:
        for active_skill in skill_store.list_active():
            if active_skill.id in skills_block:
                try:
                    skill_usage.increment(active_skill.id)
                except Exception:
                    logger.debug("Skill usage increment failed for %s", active_skill.id)
    return skills_block


def _initialize_skill_store(
    settings: Any,
    channel_id: str,
) -> tuple[SkillStore | None, SkillUsageStore | None]:
    """Init SkillStore + SkillUsageStore per канал.

    Best-effort: при отсутствии настроек или ошибке init — возвращает
    (None, None) и loop продолжается без skills.

    Извлечено из run_chat_loop как часть P1.2 phase 3.
    """
    if not settings.memory_enabled:
        return None, None
    try:
        skills_root = settings.memory_root_path / "skills"
        skill_store = SkillStore(skills_root, channel_id)
        skill_usage = SkillUsageStore(skill_store.directory)
        return skill_store, skill_usage
    except Exception:
        logger.warning("Не удалось инициализировать SkillStore — продолжаем без skills")
        return None, None


def _build_openai_tools(
    mcp_tools: list[dict],
    memory_manager: Any,
) -> list[dict]:
    """Конвертирует MCP tools в OpenAI function format + добавляет internal tools.

    Объединяет:
    - MCP tools (через _mcp_tools_to_openai, фильтрует _DANGEROUS_MCP_TOOLS)
    - memory_* tools через memory_tool_schemas(memory_manager)
    - todo_* tools через TODO_TOOL_SCHEMAS
    - clarify_question tool

    Извлечено из run_chat_loop как часть P1.2 phase 3.
    """
    openai_tools = _mcp_tools_to_openai(mcp_tools)
    openai_tools = openai_tools + memory_tool_schemas(memory_manager)
    openai_tools = openai_tools + TODO_TOOL_SCHEMAS
    openai_tools = openai_tools + [CLARIFY_TOOL_SCHEMA]
    return openai_tools


def _resolve_effective_model(
    requested_model: str,
    has_image: bool,
) -> str:
    """Vision auto-switch: если есть картинка и модель text-only — VISION_MODEL.

    Извлечено из run_chat_loop как часть P1.2 phase 3.
    """
    if has_image and requested_model != VISION_MODEL:
        logger.info(
            "Vision attachment detected — переключаю модель %s → %s для этого запроса",
            requested_model, VISION_MODEL,
        )
        return VISION_MODEL
    return requested_model


async def _execute_mcp_tool(
    *,
    tool_client: Any,
    tool_id: str,
    tool_name: str,
    tool_args: dict,
    start_ts: float,
) -> tuple[
    ToolResultEvent,
    dict | None,
    dict,
    dict,
]:
    """Вызывает MCP tool с retry, применяет ResultSizeGate, собирает все
    структуры для main loop.

    Извлечено из run_chat_loop как часть P1.2 phase 3.

    Returns:
        (event, card_or_none, accumulated_entry, message_entry)
        - event: ToolResultEvent для yield format_sse
        - card_or_none: dict {"type", "payload"} для yield CardEvent
          (None если карточка не построена или tool упал)
        - accumulated_entry: dict для accumulated_tool_calls.append
        - message_entry: dict для messages.append (LLM history)

    Raises:
        MCPDisconnectedError — main loop ловит и yield-ит error event.

    Note: tool_content для LLM = GATED result + summary с total/kept.
    Полный original result сохраняется в accumulated_entry (для
    load-more / CSV download через tool_result_storage).
    """
    ok, tool_result, tool_error = await _call_tool_with_retry(
        tool_client, tool_name, tool_args
    )
    duration_ms = int((time.monotonic() - start_ts) * 1000)

    event = ToolResultEvent(
        id=tool_id,
        ok=ok,
        result=tool_result if ok else None,
        error=tool_error,
        duration_ms=duration_ms,
    )

    # P2.2 ResultSizeGate: режем result до MAX_ROWS_FOR_LLM=500 строк ДО
    # формирования карточки и LLM-context. Полный set остаётся в
    # accumulated_entry.
    gated_result, gate_info = (
        apply_row_gate(tool_name, tool_result) if ok else (tool_result, {"applied": False})
    )

    # Карточка — на основе gated (UI покажет 500 строк + баннер truncated)
    card: dict | None = None
    if ok and gated_result is not None:
        built = build_card_from_tool_result(tool_name, tool_args, gated_result)
        if built is not None:
            card = built
            # BE-5 (M-K0.2, 2026-05-25): инжектируем tool_call_id в payload
            # для точного матчинга в _persist_card_states. Раньше: при 2
            # execute_query в одном turn _TOOL_FOR_CARD_TYPE.get("table")
            # возвращал "execute_query" и брался ПЕРВЫЙ matching tc (break),
            # вторая карточка получала args первого → load-more показывал
            # неверные данные. Теперь: payload.tool_call_id уникален per card
            # → matching по id, не по имени tool.
            if isinstance(card.get("payload"), dict):
                card["payload"]["tool_call_id"] = tool_id

    accumulated_entry = {
        "id": tool_id,
        "name": tool_name,
        "args": tool_args,
        "result": tool_result,
        "error": tool_error,
        "duration_ms": duration_ms,
    }

    # tool_content для LLM: GATED result + scan_sanitize_for_prompt + summary.
    # F1: prompt injection scan на данных из 1С (Комментарии документа и т.п.).
    tool_content = (
        json.dumps(gated_result, ensure_ascii=False) if gated_result else (tool_error or "")
    )
    tool_content = scan_sanitize_for_prompt(tool_content)
    tool_content += build_llm_summary_for_truncated(tool_name, gate_info)
    message_entry = {
        "role": "tool",
        "tool_call_id": tool_id,
        "content": _cap_content(tool_content),
    }

    return event, card, accumulated_entry, message_entry


def _dispatch_sync_internal_tool(
    *,
    tool_name: str,
    tool_args: dict,
    tool_id: str,
    memory_manager: Any,
    session_id: str,
    start_ts: float,
) -> tuple[bool, ToolResultEvent, dict, dict] | None:
    """Обрабатывает synchronous internal tools — memory_* и todo_*.

    Извлечено из run_chat_loop как часть P1.2 phase 2. Эти инструменты НЕ
    идут в MCP-сервер и НЕ требуют await — pure dispatch + сборка
    готовых структур для main loop.

    Returns:
        None — если tool не internal (значит main loop должен пробовать
            MCP path).
        Tuple — (ok, event, accumulated_entry, message_entry):
            - ok: успех dispatch'а
            - event: ToolResultEvent для yield format_sse
            - accumulated_entry: dict для append в accumulated_tool_calls
            - message_entry: dict для append в messages

    Note: clarify_question НЕ обрабатывается тут — он требует await на
    pending.future (диалог с пользователем). Остаётся в run_chat_loop.
    """
    if is_memory_tool(tool_name):
        ok, tool_result, tool_error = dispatch_memory_tool(
            memory_manager, tool_name, tool_args
        )
    elif is_todo_tool(tool_name):
        ok, tool_result, tool_error = dispatch_todo_tool(
            session_id, tool_name, tool_args
        )
    else:
        return None

    duration_ms = int((time.monotonic() - start_ts) * 1000)
    event = ToolResultEvent(
        id=tool_id,
        ok=ok,
        result=tool_result if ok else None,
        error=tool_error,
        duration_ms=duration_ms,
    )
    accumulated_entry = {
        "id": tool_id,
        "name": tool_name,
        "args": tool_args,
        "result": tool_result,
        "error": tool_error,
        "duration_ms": duration_ms,
    }
    tool_content = (
        json.dumps(tool_result, ensure_ascii=False)
        if tool_result
        else (tool_error or "")
    )
    message_entry = {
        "role": "tool",
        "tool_call_id": tool_id,
        "content": _cap_content(tool_content),
    }
    return ok, event, accumulated_entry, message_entry


async def _persist_card_states(
    db: aiosqlite.Connection,
    *,
    accumulated_cards: list[dict],
    accumulated_tool_calls: list[dict],
    message_id: str,
    session_id: str,
    channel_id: str,
    x_anon_enabled: bool,
) -> None:
    """Сохраняет card_state для карточек чтобы load-more endpoint + deanonymize работали.

    Извлечено из run_chat_loop как часть P1.2 декомпозиции.

    Логика:
    - LogCard всегда сохраняется (нужен card_id для load-more, Plan 03-04)
    - Table/Object/Metric/References карточки — только если x_anon_enabled
      (для deanonymize, Plan 04-01)
    - Best-effort: исключения внутри loop'а не roняют orchestrator
    """
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

        # BE-5 (M-K0.2, 2026-05-25): сначала пытаемся точный матчинг по
        # tool_call_id (если payload был обогащён в _execute_mcp_tool).
        # Fallback на legacy матчинг по name — для backward compat со
        # старыми сессиями где payload.tool_call_id отсутствует.
        card_payload = card.get("payload", {}) if isinstance(card.get("payload"), dict) else {}
        target_tool_call_id = card_payload.get("tool_call_id")
        card_tool_args: dict = {}

        if target_tool_call_id:
            # Точный матчинг — нет race при 2× execute_query в одном turn.
            for tc in accumulated_tool_calls:
                if tc.get("id") == target_tool_call_id:
                    card_tool_args = tc.get("args", {})
                    # Также обновляем tool_name_for_card на актуальный из tc,
                    # на случай если _TOOL_FOR_CARD_TYPE неполный.
                    tool_name_for_card = tc.get("name") or tool_name_for_card
                    break
        else:
            # Legacy fallback — берём первый по имени.
            for tc in accumulated_tool_calls:
                if tc.get("name") == tool_name_for_card:
                    card_tool_args = tc.get("args", {})
                    break

        # Вычисляем anon_tokens если anon режим
        anon_tokens: list[str] | None = None
        if x_anon_enabled:
            anon_tokens = _extract_anon_tokens_from_payload(card.get("payload", {}))

        try:
            # BE-6 (M-K0.2, 2026-05-25): commit=False — батч commit в конце
            # цикла. Раньше: save_card_state делал db.commit() для каждой
            # карточки → при 5-10 cards в одном turn = 5-10 SQLite write
            # transactions, что под WAL даёт write contention с другими
            # вкладками. Теперь: одна транзакция на весь batch.
            await save_card_state(
                db,
                card_id=card_id,
                session_id=session_id,
                message_id=message_id,
                tool_name=tool_name_for_card,
                original_args=card_tool_args,
                channel_id=channel_id,
                anon_tokens=anon_tokens,
                commit=False,
            )
        except Exception:
            logger.warning("Не удалось сохранить card_state для card %s", card_id)

    # BE-6: единый commit для всех card_states этого turn'а.
    # try/except — если commit не нужен (ни одна карточка не сохранилась),
    # SQLite просто игнорирует commit без активной транзакции.
    try:
        await db.commit()
    except Exception:
        logger.warning("Не удалось закоммитить batch card_states", exc_info=True)


def _finalize_streamed_tool_calls(chunk_tool_calls: dict[int, dict]) -> list[dict]:
    """Парсит JSON arguments в накопленных tool_calls от streaming LLM.

    Извлечено из run_chat_loop как часть P1.2 декомпозиции. Pure function.

    Args:
        chunk_tool_calls: словарь {index: {"id": str, "name": str, "arguments": str}}
            из стрима LLM, где arguments — JSON-строка собранная по частям.

    Returns:
        Список [{"id": str, "name": str, "args": dict}], отсортированный по index.
        Невалидный JSON в arguments → пустой dict (fail-safe).
    """
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
    return finalized


def _compute_tool_signature(finalized: list[dict]) -> str:
    """Сериализует tool_calls в стабильную строку для duplicate detector.

    Извлечено из run_chat_loop как часть P1.2 декомпозиции. Pure function.

    `sort_keys=True` гарантирует что одинаковые args в разном порядке
    дадут одинаковую сигнатуру — иначе LLM могла бы обойти detector
    переставляя ключи.
    """
    return json.dumps(
        [(tc["name"], tc["args"]) for tc in finalized],
        ensure_ascii=False,
        sort_keys=True,
    )


def _build_full_system_prompt(
    mem_block: str,
    skills_block: str,
    todos_block: str,
    mentions_block: str = "",
) -> str:
    """Собирает финальный system prompt из статичного SYSTEM_PROMPT + опциональных блоков.

    Порядок: статика → memory → skills → mentions → todos. Mentions блок
    идёт ПЕРЕД todos — это контекст текущего запроса, должен быть рядом
    с самым свежим состоянием (todos), но до них чтобы LLM понимала
    «юзер упомянул эти объекты, паспорта переданы карточками».

    Mentions блок — M-K1.14, генерируется `mentions_prefetch.prefetch_mentions`
    из @-mentions в user-сообщении.

    Pure function. Извлечено из run_chat_loop как часть P1.2 декомпозиции.
    """
    prompt_parts = [SYSTEM_PROMPT]
    if mem_block:
        prompt_parts.append(mem_block)
    if skills_block:
        prompt_parts.append(skills_block)
    if mentions_block:
        prompt_parts.append(mentions_block)
    if todos_block:
        prompt_parts.append(todos_block)
    return "\n\n".join(prompt_parts)


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

        # ARCH-2 (M-K0.6): ставим session_id в contextvar — все логи внутри
        # run_chat_loop (а также все вложенные tool calls, persistence, и т.д.)
        # автоматически получат этот session_id в JSON-поле "session".
        # Reset не нужен — generator завершается → контекст async task'а
        # очищается автоматически.
        from app.context import session_id_var
        session_id_var.set(session_id)

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

        # P1.2 phase 3 (2026-05-24): vision auto-switch вынесен в helper.
        effective_llm_model = _resolve_effective_model(llm_model, has_image)

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

    # --- M-K1.14: prefetch object dossiers для @-mentions ---
    # Парсим `@Документ.ОПП` в сообщении, читаем dossiers из metadata_cache
    # (M-K1.12+1.13). Cards эмитим сразу — юзер видит карту ДО LLM-итерации.
    # System prompt дополняется списком найденных/ненайденных объектов —
    # LLM понимает контекст и не дублирует get_metadata для уже известных.
    #
    # Best-effort: при любой ошибке продолжаем без mention-фичи (никогда
    # не валим chat из-за knowledge layer).
    mentions_cards: list[dict] = []
    mentions_context_block: str = ""
    try:
        prefetch_result = await prefetch_mentions(
            db, request.channel_id, request.message
        )
        mentions_cards = prefetch_result.cards
        if prefetch_result.context_block:
            mentions_context_block = prefetch_result.context_block
    except Exception:
        logger.exception(
            "Mentions prefetch failed для канала %s — продолжаю без mention cards",
            request.channel_id,
        )

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
    # P1.1 verified (2026-05-23): runtime wired через 3 точки:
    #   - инициализация SkillStore/SkillUsageStore (через _initialize_skill_store)
    #   - render_for_prompt + usage.increment ниже (build_system_prompt секция)
    #   - schedule_review fire-and-forget после finally
    # P1.2 phase 3 (2026-05-24): init вынесен в _initialize_skill_store.
    skill_store, skill_usage = _initialize_skill_store(settings, request.channel_id)

    try:
        await pool.initialize_all()
        mcp_tools = await pool.list_all_tools()
        # P1.2 phase 3 (2026-05-24): сборка openai_tools вынесена в helper.
        # MCP + memory_* + todo_* + clarify_question — единый список для LLM.
        openai_tools = _build_openai_tools(mcp_tools, memory_manager)
    except Exception:
        logger.exception("Ошибка инициализации MCP pool")
        yield format_sse("error", ErrorEvent(
            message="Не удалось подключиться к 1С MCP",
            code="mcp_disconnected",
        ))
        await pool.aclose()
        return

    # P1.2 phase 3 step 3 (2026-05-24): history load + system prompt сборка
    # вынесены в _load_history_safe + _render_skills_block + _build_full_system_prompt.
    history_msgs = await _load_history_safe(db, session_id, request.message)

    # Vision: history содержит placeholder «[Картинка: name.png]», но модель
    # должна получить реальное изображение в image_url. Подменяем content
    # ПОСЛЕДНЕГО user-сообщения (это текущий запрос) на multimodal parts.
    if has_image and history_msgs and history_msgs[-1].get("role") == "user":
        history_msgs = list(history_msgs)
        history_msgs[-1] = {"role": "user", "content": user_message_content}

    # System prompt: статика → memory → skills → mentions → todo. Skills
    # блок включает инкремент usage telemetry для попавших в prompt активных
    # skills (Sprint 3 A9). Mentions блок (M-K1.14) — список dossiers,
    # уже отправленных юзеру карточками, чтобы LLM не дублировала get_metadata.
    full_system_prompt = _build_full_system_prompt(
        memory_system_block(memory_manager),
        _render_skills_block(skill_store, skill_usage),
        render_todos_for_prompt(session_id),
        mentions_block=mentions_context_block,
    )

    messages: list[dict] = [
        {"role": "system", "content": full_system_prompt},
        *history_msgs,
    ]

    accumulated_content = ""
    accumulated_tool_calls: list[dict] = []
    accumulated_cards: list[dict] = []

    # M-K1.14: emit mention cards (object dossiers из metadata_cache) ДО
    # первого `status: thinking`. Юзер видит карту мгновенно, ещё до того
    # как LLM начнёт работать. Cards также добавляются в accumulated_cards
    # — это критично для save_assistant_message (cards персистятся вместе
    # с финальным ответом, чтобы при перезагрузке сессии они отобразились).
    for card in mentions_cards:
        yield format_sse("card", CardEvent(type=card["type"], payload=card["payload"]))
        accumulated_cards.append(card)

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

    # PERF-2 (M-K0.3): один LLMClient на весь loop вместо нового на каждой
    # итерации. Tool-calling типично занимает 2-10 итераций; раньше каждая
    # пересоздавала httpx.AsyncClient (TCP handshake + TLS + connection pool
    # warmup) — заметная задержка на cold open. Endpoint и model константны
    # на всём loop'е (effective_llm_model вычисляется выше в _resolve_effective_model),
    # поэтому reuse безопасен.
    #
    # Lifecycle: создаём ДО outer try чтобы покрыть его finally — aclose()
    # выполнится при любом завершении generator'а (success, exception,
    # GeneratorExit при закрытии SSE на навигации браузера).
    llm = LLMClient(endpoint=llm_endpoint, model=effective_llm_model)

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
                # PERF-2: llm уже создан ДО outer try, переиспользуем connection
                # pool httpx на всех итерациях. aclose в outer finally.
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

            # P1.2 (2026-05-23): финализация tool_calls + вычисление сигнатуры
            # вынесены в pure helpers — _finalize_streamed_tool_calls и
            # _compute_tool_signature соответственно.
            finalized = _finalize_streamed_tool_calls(chunk_tool_calls)

            # Duplicate detector: считаем подряд одинаковые вызовы (имя + args).
            # >5 одинаковых = LLM зациклилась на одном tool, прерываем.
            current_signature = _compute_tool_signature(finalized)
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

                # P1.2 phase 2 (2026-05-23): memory_* и todo_* — synchronous
                # internal tools — обрабатываются одним dispatcher'ом.
                # Возвращает None если tool не internal (тогда дальше — MCP).
                # clarify_* остаётся в main loop, потому что требует await на
                # pending.future (диалог с юзером).
                sync_internal = _dispatch_sync_internal_tool(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_id=tool_id,
                    memory_manager=memory_manager,
                    session_id=session_id,
                    start_ts=start_ts,
                )
                if sync_internal is not None:
                    _ok, event, accum_entry, msg_entry = sync_internal
                    yield format_sse("tool_result", event)
                    accumulated_tool_calls.append(accum_entry)
                    messages.append(msg_entry)
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
                    # BE-4 (M-K0.2, 2026-05-25): try/finally вокруг wait_for.
                    # Раньше: только except (TimeoutError, CancelledError) →
                    # при GeneratorExit (browser tab close, AbortController)
                    # CancelledError поднимался до try-блока, CLARIFY.cancel
                    # НЕ вызывался, PendingClarify оставался в registry навсегда.
                    # CLARIFY.active_count() рос до restart backend.
                    # Теперь: finally гарантирует cleanup в любом исходе
                    # (success / timeout / cancel / GeneratorExit / unexpected).
                    # CLARIFY.cancel idempotent — повторный вызов после resolve
                    # вернёт False и не упадёт.
                    try:
                        try:
                            answer = await asyncio.wait_for(
                                pending.future, timeout=CLARIFY_TIMEOUT_S
                            )
                        except (TimeoutError, asyncio.CancelledError):
                            yield format_sse("error", ErrorEvent(
                                message=(
                                    f"Уточнение не получено за "
                                    f"{int(CLARIFY_TIMEOUT_S / 60)} минут."
                                ),
                                code="clarify_timeout",
                            ))
                            return
                    finally:
                        # ГАРАНТИРОВАННЫЙ cleanup — защита от leak при любом
                        # завершении (timeout / cancel / GeneratorExit /
                        # успешный resolve).
                        CLARIFY.cancel(clarify_id)

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

                # Маршрутизация tool_call → правильный MCP client (primary или aux).
                # P1.2 phase 3 (2026-05-23): MCP path вынесен в _execute_mcp_tool.
                # (memory_* и todo_* выше через _dispatch_sync_internal_tool).
                tool_client = pool.client_for(tool_name)
                try:
                    event, card, accum_entry, msg_entry = await _execute_mcp_tool(
                        tool_client=tool_client,
                        tool_id=tool_id,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        start_ts=start_ts,
                    )
                except MCPDisconnectedError:
                    logger.warning("MCP disconnected during tool call: %s", tool_name)
                    yield format_sse("error", ErrorEvent(
                        message="Соединение с 1С MCP потеряно.",
                        code="mcp_disconnected",
                    ))
                    return

                yield format_sse("tool_result", event)
                if card is not None:
                    yield format_sse("card", CardEvent(type=card["type"], payload=card["payload"]))
                    accumulated_cards.append(card)
                accumulated_tool_calls.append(accum_entry)
                messages.append(msg_entry)

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
        # PERF-2 (M-K0.3): закрываем переиспользуемый LLMClient (httpx pool).
        # Best-effort — если aclose упадёт, mcp/aux всё равно должны закрыться.
        try:
            await llm.aclose()
        except Exception:
            logger.debug("LLMClient.aclose() в finally упал — игнорируем", exc_info=True)
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

        # P1.2 (2026-05-23): card_state persist loop вынесен в _persist_card_states.
        # Выполняется ПОСЛЕ save_assistant_message чтобы иметь реальный message_id.
        await _persist_card_states(
            db,
            accumulated_cards=accumulated_cards,
            accumulated_tool_calls=accumulated_tool_calls,
            message_id=message_id,
            session_id=session_id,
            channel_id=request.channel_id,
            x_anon_enabled=x_anon_enabled,
        )

    except Exception as exc:
        # BE-3 (M-K0.2, 2026-05-25): silent failure → explicit error.
        # Раньше: message_id='unknown' тихо передавался в done event, frontend
        # молча работал с битым id. Теперь — явный SSE error для пользователя
        # + structured log с session_id для диагностики.
        logger.exception(
            "Failed to save assistant message (session=%s, channel=%s)",
            session_id,
            request.channel_id,
        )
        yield format_sse(
            "error",
            ErrorEvent(
                message=(
                    "Не удалось сохранить ответ. Попробуйте повторить запрос. "
                    f"Если повторится — пришлите session_id={session_id} разработчику."
                ),
                code="message_save_failed",
            ),
        )
        # Возврат — далее в коде есть auto-title / memory sync / schedule_review,
        # они опираются на корректный message_id. Без сохранения они тоже упадут
        # каскадом, поэтому return сразу — чище.
        return

    # --- Auto-title background task для первого сообщения ---
    # Шедулим здесь, а не на старте orchestrator-а: иначе async I/O ниже
    # (load_history_for_llm) даёт auto-title шанс запуститься раньше и
    # в тестах с FakeLLM (shared counter) съесть первый stub. После
    # завершения основного цикла LLMClient уже не используется — безопасно.
    #
    # BE-2 (M-K0.2, 2026-05-25): fire-and-forget task защищён от GC.
    # Раньше: asyncio.create_task(_run_auto_title()) без сохранения ссылки.
    # При SSE disconnect (browser tab close, AbortController) до запуска task —
    # Python GC мог собрать task до выполнения; auto-title тихо терялся.
    # Также db connection передавался через closure — мог быть закрыт к
    # моменту вызова.
    # Теперь: храним ссылку в module-level set; add_done_callback убирает её
    # после завершения. Это держит task живым до завершения независимо от GC.
    if schedule_auto_title:
        async def _run_auto_title() -> None:
            try:
                llm = LLMClient(endpoint=llm_endpoint, model=llm_model)
                try:
                    new_title = await generate_title(request.message, llm, api_key)
                    await update_session_title(db, session_id, new_title)
                finally:
                    # aclose в finally — даже если generate_title упал,
                    # httpx connection корректно закроется (не leak).
                    await llm.aclose()
            except Exception:
                logger.warning(
                    "Auto-title background task failed for session %s",
                    session_id,
                    exc_info=True,
                )

        task = asyncio.create_task(
            _run_auto_title(),
            name=f"auto_title_{session_id}",
        )
        # Защита от GC: храним ссылку до завершения task'а.
        _AUTO_TITLE_TASKS.add(task)
        task.add_done_callback(_AUTO_TITLE_TASKS.discard)

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
            # BE-3 (M-K0.2, 2026-05-25): logger.debug → warning.
            # Self-Learning skill pipeline критичен для качества — silent debug
            # скрывал регрессии (skills не создавались, никто не знал почему).
            # warning попадает в logs+Sentry в проде → быстрее ловим регрессии.
            logger.warning(
                "schedule_review failed (session=%s, channel=%s) — "
                "skill learning pipeline degraded for this turn",
                session_id,
                request.channel_id,
                exc_info=True,
            )

    yield format_sse("done", DoneEvent(
        message_id=message_id,
        total_duration_ms=total_duration_ms,
        interrupted=interrupted_by_user,
    ))
