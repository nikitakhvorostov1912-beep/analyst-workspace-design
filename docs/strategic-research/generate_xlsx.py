"""
Генератор Excel-отчёта по 3 стратегическим направлениям развития
analyst-workspace-design (2026-05-23).

Источник данных: три параллельных deep-research отчёта Claude:
  1. ИТС интеграция (Researcher 1)
  2. Цепочки документов + runtime-диагностика (Researcher 2)
  3. Самообучающаяся система + база решений (Researcher 3)
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


OUTPUT_PATH = Path(
    r"C:/CLOUDE_PR/projects/analyst-workspace-design/docs/strategic-research/Analyst_Workspace_Strategy_2026-05-23.xlsx"
)


# ──────────────────────────────── Стили ──────────────────────────────────
COLOR_HEADER_BG = "1F2937"      # темно-серый (брутальный)
COLOR_HEADER_FG = "FFFFFF"
COLOR_ACCENT_BG = "FF6A3D"      # Signal orange — фирменный
COLOR_SECTION_BG = "374151"     # средний серый для секций
COLOR_ROW_ALT = "F3F4F6"        # светлый зебра-фон
COLOR_PRIORITY_HIGH = "EF4444"  # красный
COLOR_PRIORITY_MED = "F59E0B"   # янтарный
COLOR_PRIORITY_LOW = "10B981"   # зелёный
COLOR_RECOMMENDED = "FFE7DA"    # светло-оранжевый — рекомендация

FONT_HEADER = Font(name="Calibri", size=11, bold=True, color=COLOR_HEADER_FG)
FONT_SECTION = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
FONT_TITLE = Font(name="Calibri", size=16, bold=True, color="111827")
FONT_NORMAL = Font(name="Calibri", size=10)
FONT_SMALL = Font(name="Calibri", size=9, color="6B7280")
FONT_MONO = Font(name="Consolas", size=9)

FILL_HEADER = PatternFill("solid", fgColor=COLOR_HEADER_BG)
FILL_SECTION = PatternFill("solid", fgColor=COLOR_SECTION_BG)
FILL_ACCENT = PatternFill("solid", fgColor=COLOR_ACCENT_BG)
FILL_ALT = PatternFill("solid", fgColor=COLOR_ROW_ALT)
FILL_RECOMMENDED = PatternFill("solid", fgColor=COLOR_RECOMMENDED)
FILL_HIGH = PatternFill("solid", fgColor="FEE2E2")
FILL_MED = PatternFill("solid", fgColor="FEF3C7")
FILL_LOW = PatternFill("solid", fgColor="D1FAE5")

THIN = Side(border_style="thin", color="D1D5DB")
BORDER_ALL = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

ALIGN_TOP_WRAP = Alignment(vertical="top", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)


# ──────────────────────────────── Helpers ──────────────────────────────────
def style_header_row(ws: Worksheet, row: int, num_cols: int) -> None:
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_ALL
    ws.row_dimensions[row].height = 32


def style_title_row(ws: Worksheet, row: int, num_cols: int, text: str) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_cols)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = FONT_TITLE
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 28


def style_section_row(ws: Worksheet, row: int, num_cols: int, text: str) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_cols)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = FONT_SECTION
    cell.fill = FILL_SECTION
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 22


def style_accent_row(ws: Worksheet, row: int, num_cols: int, text: str) -> None:
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_cols)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(name="Calibri", size=11, bold=True, color="111827")
    cell.fill = FILL_ACCENT
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 22


def fill_data_rows(ws: Worksheet, start_row: int, rows: list[list], zebra: bool = True) -> int:
    for i, row in enumerate(rows):
        excel_row = start_row + i
        for j, val in enumerate(row):
            cell = ws.cell(row=excel_row, column=j + 1, value=val)
            cell.font = FONT_NORMAL
            cell.alignment = ALIGN_TOP_WRAP
            cell.border = BORDER_ALL
            if zebra and i % 2 == 1:
                cell.fill = FILL_ALT
        ws.row_dimensions[excel_row].height = max(18, 14 * max(str(c).count("\n") + 1 for c in row))
    return start_row + len(rows)


def set_col_widths(ws: Worksheet, widths: list[int]) -> None:
    for i, w in enumerate(widths):
        ws.column_dimensions[get_column_letter(i + 1)].width = w


def apply_priority_color(ws: Worksheet, row: int, col: int, value: str) -> None:
    val = value.upper()
    cell = ws.cell(row=row, column=col)
    if val in {"CRITICAL", "ВЫСОКИЙ", "HIGH", "★★★★★", "P1"}:
        cell.fill = FILL_HIGH
    elif val in {"MEDIUM", "СРЕДНИЙ", "★★★☆☆", "P2"}:
        cell.fill = FILL_MED
    elif val in {"LOW", "НИЗКИЙ", "P3"}:
        cell.fill = FILL_LOW


# ──────────────────────────────── ЛИСТЫ ──────────────────────────────────


def sheet_00_summary(wb: Workbook) -> None:
    ws = wb.create_sheet("00_Сводка")
    set_col_widths(ws, [4, 38, 50, 18, 18, 18])

    style_title_row(ws, 1, 6, "Стратегический план развития analyst-workspace-design")
    ws.cell(row=2, column=1, value="Дата:")
    ws.cell(row=2, column=2, value="2026-05-24 · версия 2.0 · Claude Opus 4.7 (5 параллельных deep-research)")
    ws.cell(row=2, column=2).font = FONT_SMALL

    # ── Контекст
    style_section_row(ws, 4, 6, "Контекст проекта (snapshot на 2026-05-23)")
    fill_data_rows(ws, 5, [
        ["1", "Проект", "analyst-workspace-design — веб-чат для бизнес-аналитика 1С (multi-tenant)", "", "", ""],
        ["2", "Активная фаза", "Phase 11 Design v2 Import — 69% (Milestone M5)", "", "", ""],
        ["3", "Стек", "Next.js 15 + React 19 + FastAPI + Pydantic v2 + SSE + SQLite + Electron 33", "", "", ""],
        ["4", "MCP-канал", "1С MCP Toolkit v1.7.0 на :6010 (10 операций)", "", "", ""],
        ["5", "Локальные ресурсы", "БСП 3.2 (77.5MB BSL, CC-BY-4.0), HBK платформы 82MB, comol/ai_rules_1c", "", "", ""],
        ["6", "Уже в roadmap", "Phase 10 — sqlite-vec + embeddings + RAG", "", "", ""],
    ])

    # ── Три направления
    style_section_row(ws, 12, 6, "Три стратегических направления")
    style_header_row(ws, 13, 6)
    for col, val in enumerate(["#", "Направление", "Что даёт пользователю", "MVP, дни", "Полный, недели", "Стоимость/мес"]):
        ws.cell(row=13, column=col + 1, value=val)

    fill_data_rows(ws, 14, [
        ["I", "ИТС / экспертные знания 1С",
         "AI отвечает на уровне эксперта по стандартам, API платформы, БСП-паттернам. Снижает галлюцинации с ~30% до &lt;5%.",
         "1-2 дня", "3-4 недели", "$0-54"],
        ["II", "Цепочки документов + runtime-диагностика",
         "Граф связанных документов за &lt;5 сек, объяснение ошибок в момент появления, drill-into-code прямо в чате.",
         "5-7 дней", "3 месяца (Phase 12-14)", "$0-30"],
        ["III", "Самообучающаяся система + база решений",
         "Каждый разрешённый кейс становится знанием. Через 90 дней — 50-200 готовых решений, повторных вопросов на 40-60% меньше.",
         "3-5 дней", "6-8 недель", "$5-25"],
    ])

    # ── Приоритеты
    style_section_row(ws, 18, 6, "Рекомендуемая последовательность (что сначала)")
    style_header_row(ws, 19, 6)
    for col, val in enumerate(["Приоритет", "Шаг", "Описание", "Срок", "Зачем сначала", "Зависимости"]):
        ws.cell(row=19, column=col + 1, value=val)

    priority_rows = [
        ["P0", "ИТС·MVP", "Подключить v8std MCP публичный + comol/ai_rules_1c + prompt caching 1h",
         "1-2 дня", "Самый дешёвый и быстрый прирост качества AI прямо сейчас", "—"],
        ["P0", "RAG·Phase10", "sqlite-vec + embedding job + hybrid retrieval над messages",
         "3-5 дней", "База для самообучения; уже в roadmap; messages_fts уже есть",
         "Embedding API (OpenAI text-embedding-3-small)"],
        ["P1", "Цепочки·MVP", "Новая MCP-операция get_document_chain через execute_code + React Flow карточка",
         "5-7 дней", "Меняет восприятие продукта от \"чата\" к \"аналитическому инструменту\"", "MCP Toolkit"],
        ["P1", "ИТС·Sprint1", "Self-hosted onec-help-mcp (HBK платформы через Docker+Qdrant)",
         "1-2 недели", "Закрывает вопросы по API платформы (галлюцинации методов)",
         "Docker, Qdrant ~4GB RAM"],
        ["P1", "Errors·Phase13", "SSE event stream + ErrorDiagnosisCard + LLM-объяснение ошибки",
         "2-3 недели", "\"Понимает ошибку в ту же секунду\" — прямой запрос пользователя", "—"],
        ["P2", "Cases·Phase12", "Case Repository (структурированные решения) поверх существующего SkillStore",
         "2-3 недели", "Сохраняет накопленный опыт между сессиями", "RAG Phase 10"],
        ["P2", "Feedback·Phase14", "Thumbs UI + implicit signals + confidence recalc",
         "1-2 недели", "Без обратной связи кейсы не созревают до confidence 4-5", "Cases Phase 12"],
        ["P2", "BSL-LSP·Phase14", "Monaco + monaco-languageclient + BSL Language Server WebSocket bridge",
         "3-4 недели", "Inline-диагностики прямо в показанном коде", "Phase 13 ready"],
        ["P3", "GrowthDash·Phase15", "Dashboard метрик \"как система становится умнее\"",
         "1 неделя", "Видимость прогресса для пользователя и для будущих клиентов", "Phase 14 ready"],
        ["P3", "ImpactAnalysis", "bsl-graph + ImpactAnalysisCard для анализа конфигурации клиента",
         "4-5 недель", "Сильная фича для франчайзи/внедренцев", "Phase 14"],
    ]
    end = fill_data_rows(ws, 20, priority_rows)
    for i in range(20, end):
        apply_priority_color(ws, i, 1, ws.cell(row=i, column=1).value)

    # ── Бюджет
    style_section_row(ws, end + 1, 6, "Ориентировочный бюджет")
    style_header_row(ws, end + 2, 6)
    for col, val in enumerate(["Категория", "MVP (1 неделя)", "Sprint 1 (1 мес)", "Full plan (3 мес)", "Прим.", ""]):
        ws.cell(row=end + 2, column=col + 1, value=val)

    fill_data_rows(ws, end + 3, [
        ["LLM (Anthropic Claude Sonnet 4.6)", "$50/мес", "$150/мес", "$300/мес", "С prompt caching 1h — экономия 60-90%", ""],
        ["Embeddings (text-embedding-3-small)", "$0.50/мес", "$2/мес", "$5/мес", "1M токенов = $0.02; малозаметно", ""],
        ["Инфраструктура (Qdrant + Docker)", "$0", "$10/мес", "$10-30/мес", "Локально бесплатно, VPS $10-30", ""],
        ["Разработка (часы Claude Code)", "10 ч", "60 ч", "180 ч", "Текущий темп проекта позволяет", ""],
        ["ИТОГО месяц", "$50-100", "$160-200", "$315-350", "С прибылью от инструмента — отбивается за 1 клиента", ""],
    ])

    style_accent_row(ws, end + 9, 6,
        "Главный вывод: 80% результата достигается за 5 дней работы (P0 шаги). "
        "Полный план — 3 месяца последовательных фаз без рисков для текущего MVP."
    )

    # ── Блок цели "заменить аналитика" + ссылки на новые листы (v2.0) ──
    style_section_row(ws, end + 11, 6, "🎯 ЦЕЛЬ продукта: заменить аналитика 1С на 60%+ (или полностью)")

    style_header_row(ws, end + 12, 6)
    for col, val in enumerate(["#", "Метрика", "Сейчас", "Phase 15", "Phase 20", "Потолок"]):
        ws.cell(row=end + 12, column=col + 1, value=val)

    fill_data_rows(ws, end + 13, [
        ["1", "Coverage Score (% времени аналитика)", "~5%", "~24%", "~51%", "~58%"],
        ["2", "Топ-3 ценности (по часам)",
         "—", "Инциденты + журнал + цепочки", "+ ТЗ + инструкции + code review", "+ voice + skill catalog"],
        ["3", "Quarter milestone", "Q2 2026", "Q4 2026", "Q3 2027", "—"],
    ])

    style_section_row(ws, end + 17, 6, "Новые листы (v2.0 — деталный конкурентный + декомпозиция)")
    fill_data_rows(ws, end + 18, [
        ["15", "Конкуренты Landscape", "19 продуктов (РФ + зарубеж), scorecard 9 критериев, угрозы", "", "", ""],
        ["16", "SWOT 1С:Напарник", "Главный конкурент через 12-18 мес. План дифференциации.", "", "", ""],
        ["17", "Best Practices зарубеж", "15 паттернов из SAP/Salesforce/Hex/Cursor/Notion AI", "", "", ""],
        ["18", "Декомпозиция аналитика", "44 задачи · % времени · AI-feasibility · gap", "", "", ""],
        ["19", "Путь к 60%+ (Phase 16-20)", "19 модулей: ТЗ-генератор, BSL-аудитор, voice, skills…", "", "", ""],
        ["20", "Pricing + Go-to-Market", "3 модели pricing, 90д/6м/1г roadmap, fin прогноз", "", "", ""],
        ["21", "Этика и правовые границы", "Где AI не должен, escalation rules, 152-ФЗ, EULA 1С", "", "", ""],
    ])

    style_accent_row(ws, end + 26, 6,
        "Окно возможностей до того как 1С:Напарник пойдёт в аналитика — 12-18 месяцев. "
        "Наша подушка: multi-tenant + workflow аналитика + история клиента — это лет 2 разработки для 1С."
    )


def sheet_01_its_sources(wb: Workbook) -> None:
    ws = wb.create_sheet("01_ИТС_Источники")
    set_col_widths(ws, [4, 30, 16, 14, 22, 18, 16, 40])

    style_title_row(ws, 1, 8, "I.1 Источники экспертных знаний 1С — карта возможностей")
    style_header_row(ws, 3, 8)
    for col, val in enumerate(["#", "Источник", "Лицензия", "Объём", "Сложность доступа",
                                "Качество", "Подходит для RAG", "Где взять / комментарий"]):
        ws.cell(row=3, column=col + 1, value=val)

    rows = [
        ["1", "HBK-файлы платформы (shcntx_ru.hbk и др.)", "Proprietary 1С (локально у вас)",
         "82 МБ raw, ~25 МБ текста", "Средняя — нужен парсер",
         "Высокое", "Да, локально",
         "C:\\Program Files\\1cv8\\8.3.27.1989\\bin — уже на машине. Парсер: alkoleft/hbk-viewer (MIT)"],
        ["2", "v8std стандарты разработки", "CC0 (public domain)",
         "~800 стандартов, 5-8 МБ", "Низкая — GitHub + публичный MCP",
         "Очень высокое", "Да, без ограничений",
         "github.com/zeegin/v8std + публичный MCP https://ai.v8std.ru/mcp — РАБОТАЕТ ПРЯМО СЕЙЧАС"],
        ["3", "comol/ai_rules_1c — правила AI-разработки", "Без лицензии (free to use)",
         "2000+ правил, ~3 МБ", "Низкая — git clone",
         "Высокое (боевые практики)", "Да, немедленно",
         "github.com/comol/ai_rules_1c — клонировать в tools/ai_rules_1c"],
        ["4", "БСП 3.2 исходники (ssl_3_2)", "CC-BY-4.0 (атрибуция)",
         "2184 BSL-файла, 77.5 МБ", "Низкая — уже локально",
         "Очень высокое — эталонные паттерны", "Да, с атрибуцией",
         "C:\\CLOUDE_PR\\tools\\ssl_3_2\\src — уже на машине"],
        ["5", "onec-help-mcp (Docker+Qdrant+BM25+dense)", "MIT",
         "HBK 8.3.x многих версий", "Средняя — Docker, Qdrant ~4GB RAM",
         "Высокое (hybrid поиск)", "Да, через MCP",
         "github.com/rzateev/onec-help-mcp — self-hosted MCP сервер"],
        ["6", "mcp-bsl-platform-context (bsl-context)", "MIT",
         "API объектной модели платформы", "Низкая — уже установлен",
         "Высокое", "Да, через MCP",
         "github.com/alkoleft/mcp-bsl-platform-context — УЖЕ В .mcp.json (Java)"],
        ["7", "ИТС its.1c.ru web-парсинг", "Proprietary — ToS запрещает",
         "Тысячи страниц", "ВЫСОКАЯ — юридический риск",
         "Очень высокое", "НЕТ — запрещено",
         "Нарушение пользовательского соглашения. Прямой запрет."],
        ["8", "ИТС full subscription (50-60 тыс. ₽/год)", "Proprietary",
         "Весь ИТС", "Очень высокая — нет API",
         "Наивысшее", "Только UI чтение",
         "Только для авторизованного чтения, нет интеграции"],
        ["9", "Infostart статьи (30 000+)", "Авторское право (разное)",
         "Огромный объём", "Высокая — нет API, парсинг = нарушение",
         "Среднее (community)", "НЕТ без разрешения",
         "Требует индивидуального разрешения каждого автора"],
        ["10", "1С:Напарник (code.1c.ai)", "Proprietary — коммерческое ЗАПРЕЩЕНО",
         "н/д", "н/д — нет публичного API",
         "Высокое", "НЕТ — явный запрет",
         "EULA запрещает интеграцию в сторонние продукты"],
    ]
    fill_data_rows(ws, 4, rows)

    style_section_row(ws, 16, 8, "Ключевые наблюдения")
    fill_data_rows(ws, 17, [
        ["💡", "У вас уже локально 165+ МБ знаний 1С", "БСП 77.5 МБ + HBK 82 МБ + правила. Это больше чем у большинства консультантов.",
         "", "", "", "", ""],
        ["💡", "Бесплатные пути закрывают 80% потребности", "v8std MCP + bsl-context (уже подключён) + comol/ai_rules_1c — без подписки.",
         "", "", "", "", ""],
        ["⚠️", "ИТС подписка не даёт API", "Платить 60К/год чтобы получить только UI чтение — нерационально для AI-инструмента.",
         "", "", "", "", ""],
        ["⚠️", "1С:Напарник заблокирован EULA", "Не пытаться парсить — риск блокировки и судебных рисков.",
         "", "", "", "", ""],
    ])


def sheet_02_its_approaches(wb: Workbook) -> None:
    ws = wb.create_sheet("02_ИТС_Подходы")
    set_col_widths(ws, [4, 28, 32, 28, 28, 14, 14, 14])

    style_title_row(ws, 1, 8, "I.2 Технические подходы интеграции знаний — сравнение 7 вариантов")
    style_header_row(ws, 3, 8)
    for col, val in enumerate(["#", "Подход", "Плюсы", "Минусы", "Сложность", "Срок до MVP", "Стоимость/мес", "Вердикт"]):
        ws.cell(row=3, column=col + 1, value=val)

    rows = [
        ["1",
         "Prompt Caching (статический контекст 1h TTL)",
         "Нулевое время разработки\nГарантированный контекст без retrieval-ошибок\nCache hit = 10% цены\nЦентральное место для правил проекта",
         "Лимит ~150K слов (200K токенов)\nПри cache miss первый запрос дороже 2x\nНе масштабируется на полный HBK 82МБ",
         "Низкая", "1-2 дня", "$50-54", "MVP — да"],
        ["2",
         "MCP-based знания (v8std + onec-help-mcp + bsl-context)",
         "v8std — zero-config\nМодульная архитектура\nАвтоматическое обновление\nonec-help-mcp: BM25+RRF+semantic",
         "Публичный v8std не для конфиденциального кода\nonec-help-mcp требует Docker+Qdrant\nЗависимость от внешних MCP",
         "Низкая-Средняя", "1-3 дня", "$0-30", "MVP — да"],
        ["3",
         "Hybrid RAG (sqlite-vec + BM25 + reranker)",
         "Полный контроль над данными\nНет внешних зависимостей в prod\nsqlite-vec уже locked в стеке Phase 10\nГибрид BM25+dense даёт +15-20% качества",
         "Pipeline 2-3 недели разработки\nГibrid требует reranker\nОбновление данных — ручной re-index",
         "Высокая", "3-4 недели", "$1-10", "Phase 10 — да"],
        ["4",
         "GraphRAG (Neo4j + vector)",
         "Лучший для вопросов о зависимостях\nMulti-hop reasoning (A→B→C)\nПонимание архитектуры клиента",
         "Высочайшая сложность\nNeo4j ~$65/мес или DevOps\nbsl-graph alpha-статус\nИзбыточно для общих вопросов",
         "Очень высокая", "2-3 месяца", "$100+", "Phase 13+ опц."],
        ["5",
         "Fine-tuning LLM (QLoRA на BSL-корпусе)",
         "Максимальная встроенность\nРаботает офлайн\nПонимает BSL после дообучения",
         "Нет готового BSL-датасета (нужно 10K+ Q&A)\nCatastrophic forgetting\nClaude API не поддерживает fine-tune\nДорого ($50-200 + хостинг)",
         "Очень высокая", "2-3 месяца", "$10-50 + единоразово $50-200", "НЕ ДЕЛАТЬ"],
        ["6",
         "MCP-сервер с локальным ИТС (self-built)",
         "Переиспользуется в других проектах\nИзоляция данных\nВерсионирование знаний",
         "Дублирует onec-help-mcp\nВысокая стоимость разработки",
         "Высокая", "1-2 месяца", "—", "Не нужно — onec-help-mcp"],
        ["7",
         "Subscription API (ИТС / 1С:Напарник)",
         "Официальный, авторитетный",
         "1С:Напарник EULA запрещает commercial\nИТС подписка не даёт API\nЮридические риски",
         "Высокая (нет API)", "—", "—", "НЕ ИСПОЛЬЗОВАТЬ"],
    ]
    fill_data_rows(ws, 4, rows)

    # Подкрашиваем рекомендованные
    for r in (4, 5, 6):  # подходы 1, 2, 3
        for c in range(1, 9):
            ws.cell(row=r, column=c).fill = FILL_RECOMMENDED

    style_section_row(ws, 12, 8, "Сравнение подходов по критериям (★=плохо ... ★★★★★=отлично)")
    style_header_row(ws, 13, 8)
    for col, val in enumerate(["Критерий", "1. Prompt Cache", "2. MCP servers", "3. Hybrid RAG",
                                "4. GraphRAG", "5. Fine-tune", "Победитель", ""]):
        ws.cell(row=13, column=col + 1, value=val)

    fill_data_rows(ws, 14, [
        ["Релевантность под задачу", "★★★★", "★★★★★", "★★★★★", "★★★", "★★★", "MCP / Hybrid RAG", ""],
        ["Зрелость технологии", "★★★★★", "★★★★", "★★★★", "★★", "★★★", "Prompt Cache", ""],
        ["Простота внедрения", "★★★★★", "★★★★", "★★", "★", "★★", "Prompt Cache", ""],
        ["Актуальность данных", "★★★★", "★★★★★", "★★★", "★★★", "★★", "MCP servers", ""],
        ["Совместимость стеком", "★★★★★", "★★★★★", "★★★★★", "★★", "★★", "Любой первый", ""],
        ["Стоимость/мес", "★★★ ($54)", "★★★★★ ($0-30)", "★★★★★ ($1-10)", "★★ ($100+)", "★★★", "Hybrid RAG", ""],
        ["ИТОГО /30", "26", "28", "26", "13", "16", "MCP servers", ""],
    ])


def sheet_03_its_legal(wb: Workbook) -> None:
    ws = wb.create_sheet("03_ИТС_Юридическое")
    set_col_widths(ws, [4, 28, 20, 14, 44, 14])

    style_title_row(ws, 1, 6, "I.3 Юридический анализ источников знаний")
    style_header_row(ws, 3, 6)
    for col, val in enumerate(["#", "Источник", "Лицензия", "Риск", "Что МОЖНО / НЕЛЬЗЯ", "Митигейшен"]):
        ws.cell(row=3, column=col + 1, value=val)

    rows = [
        ["1", "HBK-файлы платформы (локально установленная)", "Proprietary 1С", "Низкий",
         "МОЖНО: индексировать локально для внутреннего AI-инструмента.\nНЕЛЬЗЯ: включать .hbk в дистрибутив, распространять извлечённые тексты.",
         "Индексация только из локальной установки пользователя"],
        ["2", "БСП 3.2 исходники", "CC-BY-4.0", "Нулевой",
         "МОЖНО: коммерческое использование, производные работы, RAG-индекс.\nТРЕБУЕТСЯ: указание авторства \"ООО Фирма 1С\" в README/документации.",
         "Атрибуция в README, лицензия рядом"],
        ["3", "v8std стандарты разработки", "CC0 (public domain)", "Нулевой",
         "МОЖНО ВСЁ: без ограничений, без атрибуции, в любом продукте.",
         "—"],
        ["4", "comol/ai_rules_1c", "Без лицензии (free to use)", "Низкий",
         "МОЖНО: использовать как угодно (заявлено автором).\nЮридическая неопределённость в строгих юрисдикциях.",
         "Дополнительная проверка автора при коммерциализации"],
        ["5", "onec-help-mcp", "MIT", "Нулевой",
         "МОЖНО: коммерческое использование, модификация, распространение.\nТРЕБУЕТСЯ: сохранение MIT-уведомления.",
         "MIT-license file в проекте"],
        ["6", "ИТС its.1c.ru парсинг", "Proprietary + ToS", "ВЫСОКИЙ",
         "НЕЛЬЗЯ: автоматический парсинг — нарушение ToS, риск блокировки аккаунта.",
         "НЕ ДЕЛАТЬ"],
        ["7", "ИТС subscription content", "Proprietary", "Средний",
         "МОЖНО: ручное чтение авторизованным пользователем.\nНЕЛЬЗЯ: передача в облачный LLM выдержек текстов на постоянной основе.",
         "Если используется — только ad-hoc, без массового retrieval"],
        ["8", "1С:Напарник", "Proprietary + EULA", "ВЫСОКИЙ",
         "НЕЛЬЗЯ: интегрировать в коммерческий продукт, обращаться через сторонние клиенты.",
         "НЕ ИСПОЛЬЗОВАТЬ"],
        ["9", "Infostart статьи", "Авторское право", "Средний",
         "НЕЛЬЗЯ: парсинг без явного разрешения авторов.\nМожно: цитирование с указанием источника в малых объёмах.",
         "Не использовать для массового RAG"],
        ["10", "Корпоративный код клиентов", "Конфиденциальный", "ВЫСОКИЙ",
         "МОЖНО: обрабатывать на стороне клиента (Electron).\nНЕЛЬЗЯ: отправлять полный код через публичный v8std MCP.",
         "Для prod — self-hosted MCP. Anon toggle для submit_for_deanonymization."],
    ]
    end = fill_data_rows(ws, 4, rows)
    for i in range(4, end):
        risk_val = ws.cell(row=i, column=4).value
        apply_priority_color(ws, i, 4, risk_val)

    style_section_row(ws, end + 1, 6, "Противоречия и нюансы")
    fill_data_rows(ws, end + 2, [
        ["⚠️", "Противоречие 1: HBK-парсинг + публичные MIT-репозитории",
         "onec-help-mcp под MIT использует HBK — создаёт прецедент допустимости. Формально EULA 1С содержит общие ограничения.",
         "Использовать только локально, не включать HBK в дистрибутив.", "", ""],
        ["⚠️", "Противоречие 2: v8std MCP публичный + конфиденциальный код",
         "Данные v8std — CC0, но публичный эндпоинт ВИДИТ ваши запросы (включая код).",
         "Self-hosted v8std для production с кодом клиентов.", "", ""],
        ["💡", "Прецедент: Infostart-инструмент \"Загрузка стандартов с ИТС\"",
         "Существует как платный продукт и парсит ИТС. Юридическая серая зона — 1С не предъявляет претензий, но это не легализация.",
         "Не следовать прецеденту без явного согласования с 1С.", "", ""],
    ])


def sheet_04_chains_mcp_ops(wb: Workbook) -> None:
    ws = wb.create_sheet("04_Цепочки_MCP_операции")
    set_col_widths(ws, [4, 26, 32, 50, 12, 18])

    style_title_row(ws, 1, 6, "II.1 Новые MCP-операции для цепочек документов и анализа ошибок")
    style_section_row(ws, 3, 6, "Текущее: 1С MCP Toolkit v1.7.0 — 10 операций")

    style_header_row(ws, 4, 6)
    for col, val in enumerate(["#", "Операция", "Назначение", "Применимость", "Изменения EPF", "Статус"]):
        ws.cell(row=4, column=col + 1, value=val)

    existing = [
        ["1", "execute_query", "Произвольный запрос на языке 1С", "Высокая для lineage (запрос регистров) + средняя для error analysis", "—", "Есть"],
        ["2", "execute_code", "Произвольный BSL-код", "Высокая — основа для get_document_chain через traversal", "—", "Есть"],
        ["3", "get_metadata", "Структура объектов конфигурации", "Средняя — структура модуля для error context", "—", "Есть"],
        ["4", "get_event_log", "Журнал регистрации", "Высокая — основной источник для error analysis", "—", "Есть"],
        ["5", "find_references_to_object", "Кто ссылается на объект", "Высокая — родительские документы", "—", "Есть"],
        ["6", "get_object_by_link", "Объект по навигационной ссылке", "Высокая — раскрытие узлов графа", "—", "Есть"],
        ["7", "get_link_of_object", "Обратное — построение URL", "Высокая — переход в 1С из приложения", "—", "Есть"],
        ["8", "get_access_rights", "Права роли/пользователя", "Средняя — кто имел доступ при ошибке", "—", "Есть"],
        ["9", "get_bsl_syntax_help", "Справочник BSL", "Высокая — объяснение метода в stack trace", "—", "Есть"],
        ["10", "submit_for_deanonymization", "Расшифровка анонимизированной сессии", "Низкая — privacy", "—", "Есть"],
    ]
    fill_data_rows(ws, 5, existing)

    style_section_row(ws, 16, 6, "Предлагается добавить: 9 новых операций")
    style_header_row(ws, 17, 6)
    for col, val in enumerate(["#", "Операция", "Назначение", "Сигнатура (JSON)", "Часы", "Приоритет"]):
        ws.cell(row=17, column=col + 1, value=val)

    new_ops = [
        ["11", "get_document_chain",
         "Полное дерево подчинённости документа: вверх (основания) + вниз (потребители через регистры)",
         'params: { document_link, depth_up:3, depth_down:2, include_registers:true, include_movements:false }\nreturns: { nodes:[...], edges:[...], registers:[...], build_time_ms }',
         "12", "P1"],
        ["12", "get_register_movements",
         "Все движения документа по всем его регистрам, сгруппировано",
         'params: { document_link, register_types:["accumulation","information","accounting"], format:"grouped" }\nreturns: { movements:{ "Регистр": [строки] }, total_registers, total_rows }',
         "8", "P1"],
        ["13", "get_document_errors",
         "Все ошибки связанные с документом из журнала регистрации",
         'params: { document_link, date_from, date_to, levels:["Error","Warning"], include_trace:true }\nreturns: { errors:[{id,timestamp,level,event,comment,module,line,stack:[...]}], total }',
         "10", "P1"],
        ["14", "analyze_error",
         "Контекст кода + LLM-объяснение конкретной ошибки",
         'params: { error_event_id, include_code_context:true, context_lines:20, suggest_fixes:true }\nreturns: { error, code_context:{module,file_path,line,code,highlighted_line}, explanation, suggestions:[...], related_antipatterns:[...], confidence }',
         "16", "P1"],
        ["15", "get_call_graph",
         "Граф вызовов: кто вызывает метод X, что вызывает метод X",
         'params: { module, procedure, direction:"both"|"callers"|"callees", depth:3 }\nreturns: { nodes:[...], edges:[...] }',
         "14", "P2"],
        ["16", "stream_event_log (SSE endpoint, не MCP)",
         "FastAPI SSE для стриминга новых событий журнала регистрации",
         'GET /api/events/stream?channel_id=X&level=Error,Warning&interval_sec=5\nstream events: \\{type:"1c_error", data:{...}\\}',
         "8", "P1"],
        ["17", "get_document_diff",
         "Сравнить два проведения документа — что изменилось в движениях",
         'params: { document_link, posting1_timestamp, posting2_timestamp }\nreturns: { added:[...], removed:[...], changed:[...] }',
         "10", "P2"],
        ["18", "get_object_history",
         "История изменений объекта (журнал + версионирование БСП)",
         'params: { object_link, include_data_history:true, limit:20 }\nreturns: { changes:[{timestamp,user,fields_changed,values}] }',
         "12", "P2"],
        ["19", "get_bsl_diagnostics",
         "BSL Language Server в режиме --analyze на модуле",
         'params: { module, file_path, min_severity:"WARNING" }\nreturns: { diagnostics:[{code,severity,line,message,range}], total }',
         "8", "P2"],
    ]
    end = fill_data_rows(ws, 18, new_ops)
    for i in range(18, end):
        apply_priority_color(ws, i, 6, ws.cell(row=i, column=6).value)

    total_hours = sum(int(r[4]) for r in new_ops)
    style_accent_row(ws, end + 1, 6, f"Итого новых операций: 9. Суммарные часы реализации: ~{total_hours} ч.")


def sheet_05_chains_ui_cards(wb: Workbook) -> None:
    ws = wb.create_sheet("05_Цепочки_UI_карточки")
    set_col_widths(ws, [4, 28, 38, 32, 22, 14])

    style_title_row(ws, 1, 6, "II.2 Новые UI-карточки для цепочек и ошибок")
    style_header_row(ws, 3, 6)
    for col, val in enumerate(["#", "Карточка", "Что показывает", "Технические зависимости", "Фаза", "Приоритет"]):
        ws.cell(row=3, column=col + 1, value=val)

    rows = [
        ["1", "DocumentChainCard",
         "Граф цепочки документов: основания → текущий → потребители. Раскрытие узлов по клику. Глубина +/-. Кнопка 'Открыть в 1С'.",
         "@xyflow/react v12 + @dagrejs/dagre. get_document_chain MCP.",
         "Phase 12", "P1"],
        ["2", "ErrorDiagnosisCard",
         "Заголовок ошибки + контекст кода (Monaco) + AI-причина + 3 варианта исправления + кнопка 'Применить'.",
         "Monaco Editor (есть). analyze_error MCP. LLM для объяснения.",
         "Phase 13", "P1"],
        ["3", "RegisterMovementsCard",
         "Движения документа по всем регистрам (вкладки). Таблицы строк с количествами/суммами. Антипаттерны inline.",
         "get_register_movements MCP. shadcn Tabs + Table.",
         "Phase 12", "P1"],
        ["4", "LiveEventFeedCard",
         "Live-поток событий с журнала (Error/Warning/Success). Фильтры, пауза, очистка, экспорт JSON.",
         "SSE endpoint /api/events/stream. EventSource API.",
         "Phase 13", "P1"],
        ["5", "BSLDiagnosticsCard",
         "Диагностики BSL LS по модулю: CRITICAL/WARNING/INFO. Кнопка 'Применить автофикс'.",
         "get_bsl_diagnostics MCP. Monaco markers.",
         "Phase 14", "P2"],
        ["6", "CallGraphCard",
         "Граф вызовов метода: кто вызывает + что вызывает. Глубина настраивается.",
         "get_call_graph MCP. React Flow + dagre.",
         "Phase 14", "P2"],
        ["7", "ImpactAnalysisCard",
         "При изменении реквизита X — что сломается. Список модулей, отчётов, ролей, интеграций.",
         "bsl-graph Docker (опц.). find_references MCP.",
         "Phase 14", "P3"],
    ]
    end = fill_data_rows(ws, 4, rows)
    for i in range(4, end):
        apply_priority_color(ws, i, 6, ws.cell(row=i, column=6).value)

    style_section_row(ws, end + 1, 6, "Mockup пример: DocumentChainCard")
    ws.cell(row=end + 2, column=1, value="").alignment = ALIGN_LEFT_TOP
    ws.merge_cells(start_row=end + 2, start_column=1, end_row=end + 12, end_column=6)
    mockup_cell = ws.cell(row=end + 2, column=1)
    mockup_cell.value = (
        "┌─────────────────────────────────────────────────┐\n"
        "│ 🔗 Цепочка документов                    [↗ CDN] │\n"
        "│                                                   │\n"
        "│  [Заказ-001] ──▶ [ОПП-001] ──▶ [Накл-045]       │\n"
        "│                      ↓                            │\n"
        "│              [Рег: ТоварыСклад]                   │\n"
        "│                      ↓                            │\n"
        "│                 [Накл-046]                        │\n"
        "│                                                   │\n"
        "│ Нажмите узел для раскрытия │ Глубина: [2] [+] [-] │\n"
        "│ [Экспорт PNG]  [Открыть в 1С]  [Обновить]        │\n"
        "└─────────────────────────────────────────────────┘"
    )
    mockup_cell.font = FONT_MONO
    mockup_cell.alignment = ALIGN_LEFT_TOP
    mockup_cell.border = BORDER_ALL
    for r in range(end + 2, end + 13):
        ws.row_dimensions[r].height = 18


def sheet_06_chains_approaches(wb: Workbook) -> None:
    ws = wb.create_sheet("06_Цепочки_Подходы")
    set_col_widths(ws, [4, 22, 36, 32, 14, 14, 16])

    style_title_row(ws, 1, 7, "II.3 Архитектурные подходы — Document Lineage и Real-Time Errors")
    style_section_row(ws, 3, 7, "A. Document Lineage — 5 вариантов")

    style_header_row(ws, 4, 7)
    for col, val in enumerate(["#", "Подход", "Плюсы", "Минусы", "Сложность", "Срок", "Вердикт"]):
        ws.cell(row=4, column=col + 1, value=val)

    lineage_rows = [
        ["A1", "execute_code SQL traversal",
         "Через существующий execute_code\nРаботает на любой конфигурации\nРеальные данные (экземпляр)\nDepth настраивается",
         "Медленно для глубоких (10-30 с при depth=3)\nНет кэша в MCP\nБольшой объём данных",
         "Средняя", "1-2 нед", "★ MVP"],
        ["A2", "bsl-graph + NebulaGraph",
         "Полный граф конфигурации\nImpact analysis\nMCP Protocol",
         "СХЕМА а не ДАННЫЕ\nJava 17 + NebulaGraph\nAlpha-статус\nНе отвечает 'какие документы связаны с накладной от 14.05'",
         "Высокая", "3-4 нед", "Phase 14 опц."],
        ["A3", "GraphRAG + Neo4j",
         "Граф накапливается — мгновенные повторы\nCypher для сложной аналитики\nNeo4j Browser",
         "Отдельный Neo4j сервер (~1GB)\nНужна синхронизация с базой\nИзбыточно для MVP",
         "Высокая", "1-2 мес", "Phase 15 опц."],
        ["A4", "React Flow + dagre (фронтенд рендеринг)",
         "@xyflow/react v12 + dagre layout\nКастомные DOM-узлы\nИерархический DAG автоматом\n175K downloads/неделю",
         "Это рендеринг — нужен бэкенд который вернёт {nodes,edges}",
         "Низкая", "1 нед", "★ MVP"],
        ["A5", "SQLite кэш + инкрементальное обновление",
         "Нулевые новые зависимости\n10-100x ускорение повторов\nИнвалидация по событию журнала",
         "TTL-инвалидация требует логики",
         "Низкая", "2-3 дня", "★ ВСЕГДА как слой"],
    ]
    end = fill_data_rows(ws, 5, lineage_rows)

    style_section_row(ws, end + 1, 7, "B. Real-Time Error Analysis — 4 варианта")
    style_header_row(ws, end + 2, 7)
    for col, val in enumerate(["#", "Подход", "Плюсы", "Минусы", "Сложность", "Срок", "Вердикт"]):
        ws.cell(row=end + 2, column=col + 1, value=val)

    error_rows = [
        ["B1", "ibcmd monitor → SSE → LLM",
         "ibcmd 8.3.20+ имеет JSON-режим\nстандартный формат\nSSE проще WebSocket\nsse-starlette готов",
         "ibcmd только для файловых баз\nДля серверных — через агент кластера\nЛог не содержит BSL stack trace",
         "Средняя", "1-2 нед", "★ для файл. баз"],
        ["B2", "Polling get_event_log + diff + push",
         "Через существующий MCP\nНет новых зависимостей\nРаботает для серверных баз",
         "Задержка 5-10 сек\nget_event_log не поддерживает after_id\nНагрузка от polling",
         "Низкая", "3-5 дней", "★ для серв. баз"],
        ["B3", "BSL Language Server WebSocket bridge",
         "130+ диагностик\nHover-документация по платформе\nInline-маркеры в Monaco\nЛокально, нет API ключей",
         "Сложная архитектура (3 слоя)\nBSL LS работает со статическими файлами\nSSR-конфликты в Next.js",
         "Высокая", "3-4 нед", "Phase 14"],
        ["B4", "LLM-объяснение без LSP (прагматичный)",
         "Быстро реализуется (1-2 дня)\nБез Java-зависимости\nLLM объясняет лучше статических правил",
         "Требует доступа к git-checkout\nЛатентность 2-5 сек\nВозможны галлюцинации деталей",
         "Низкая", "1-2 дня", "★ MVP"],
    ]
    end = fill_data_rows(ws, end + 3, error_rows)

    style_section_row(ws, end + 1, 7, "Рекомендация")
    fill_data_rows(ws, end + 2, [
        ["", "Lineage",
         "Комбо A1 (execute_code traversal) + A4 (React Flow рендеринг) + A5 (SQLite кэш). Без новых сервисов.",
         "", "", "", ""],
        ["", "Errors",
         "Phase 12: B4 (LLM-объяснение, 1-2 дня). Phase 13: + B1/B2 SSE. Phase 14: + B3 BSL LS.",
         "", "", "", ""],
    ])


def sheet_07_learning_layers(wb: Workbook) -> None:
    ws = wb.create_sheet("07_Самообучение_Слои")
    set_col_widths(ws, [4, 22, 18, 32, 32, 18])

    style_title_row(ws, 1, 6, "III.1 Архитектура памяти — 3 типа + текущее состояние проекта")
    style_section_row(ws, 3, 6, "Типы памяти в LLM-приложении (cognitive architecture)")

    style_header_row(ws, 4, 6)
    for col, val in enumerate(["#", "Тип памяти", "Источник", "Что хранит", "Реализация в analyst-workspace", "Статус"]):
        ws.cell(row=4, column=col + 1, value=val)

    fill_data_rows(ws, 5, [
        ["1", "Working Memory", "Контекст текущей сессии",
         "Последние N сообщений диалога. Tool calls. Streaming.",
         "messages таблица + контекст-окно LLM. Уже работает.",
         "✓ Есть"],
        ["2", "Procedural Memory", "Skills, паттерны 'как делать'",
         "Извлечённые из turn'ов паттерны: 'когда X — делай Y'. Markdown с YAML front-matter.",
         "SkillStore + background_review.py. Aux LLM анализирует каждый turn. Уже работает.",
         "✓ Есть"],
        ["3", "Episodic Memory", "RAG над историей сессий",
         "Векторный индекс по тексту сообщений. Семантический поиск 'похожих случаев'.",
         "sqlite-vec + embedding job. В roadmap Phase 10.",
         "⏳ Phase 10"],
        ["4", "Semantic Memory", "Структурированные кейсы",
         "Проблема + симптомы + решение + confidence + usage_count. SQL-таблица + векторный индекс.",
         "Case Repository — НОВАЯ сущность. Pipeline извлечения из сессий.",
         "📋 Phase 12"],
        ["5", "Feedback Memory", "Сигналы качества",
         "Thumbs up/down + implicit (copy_code, expand_trace, time-to-next).",
         "scores таблица + UI кнопки + JS clipboard события.",
         "📋 Phase 13"],
    ])

    style_section_row(ws, 11, 6, "Сравнение фреймворков управления памятью (12 вариантов)")
    style_header_row(ws, 12, 6)
    for col, val in enumerate(["#", "Фреймворк", "Тип", "Плюсы / Минусы", "Стоимость/мес", "Вердикт"]):
        ws.cell(row=12, column=col + 1, value=val)

    rows = [
        ["1", "RAG sqlite-vec (свой)", "Episodic",
         "+ Уже в стеке + zero infra + multi-tenant trivially\n- ANN flat (норм до 100K)",
         "$5-20", "★ MVP"],
        ["2", "SkillStore (текущий)", "Procedural",
         "+ Уже работает + zero infra\n- Только turn-level + нет vector",
         "$0", "✓ Развивать"],
        ["3", "Case Repository (свой)", "Semantic",
         "+ Confidence scoring + versioning\n- Curation overhead + cold start 2-4 нед",
         "$5-15", "★ Phase 12"],
        ["4", "mem0 (managed cloud)", "All",
         "+ Простота API\n- $19-249/мес + cloud-only + конфиденциальность",
         "$19-249", "Избыточно"],
        ["5", "Letta / MemGPT", "All",
         "+ Open source\n- Сложная архитектура + слишком тяжело для desktop",
         "$0 OSS", "Тяжело"],
        ["6", "Zep / Graphiti", "Semantic+Graph",
         "+ Knowledge graph\n- Слабый русский + Docker",
         "$0 OSS", "Phase 13 опц."],
        ["7", "Cognee", "Graph+Vector",
         "+ 12K star\n- Neo4j+FalkorDB+vector\n- '6 строк кода' — маркетинг",
         "$0 OSS", "Слишком"],
        ["8", "LangGraph LangMem", "All",
         "+ Часть LangGraph экосистемы\n- p95 latency 59c (стресс) — для batch только",
         "$0 OSS", "Нет"],
        ["9", "Feedback Loop (свой)", "Signal",
         "+ Нулевая стоимость + improves ranking\n- Implicit signals шумные",
         "$0", "★ Phase 14"],
        ["10", "Anthropic Memory Tool", "Managed",
         "+ Нативно для Claude\n- Только для Claude API + cloud",
         "Usage-based", "Только Claude"],
        ["11", "Fine-tuning (DPO/LoRA)", "Parametric",
         "- Нужно 1000+ pairs + $500+ + drift + cloud-only",
         "$500+/раз", "НЕ ДЕЛАТЬ"],
        ["12", "Knowledge Graph + Neo4j", "Structural",
         "+ Multi-hop reasoning\n- Очень высокая сложность",
         "$0-65", "Phase 15+"],
    ]
    end = fill_data_rows(ws, 13, rows)


def sheet_08_learning_pipeline(wb: Workbook) -> None:
    ws = wb.create_sheet("08_Самообучение_Pipeline")
    set_col_widths(ws, [6, 30, 50, 26])

    style_title_row(ws, 1, 4, "III.2 Pipeline извлечения кейсов — 10 шагов + SQL DDL")

    style_section_row(ws, 3, 4, "Pipeline: от сессии к проиндексированному кейсу")
    style_header_row(ws, 4, 4)
    for col, val in enumerate(["#", "Шаг", "Описание", "Зависимости"]):
        ws.cell(row=4, column=col + 1, value=val)

    pipeline = [
        ["1", "TRIGGER", "Сессия помечена completed ИЛИ неактивна >2 часов. Background task через asyncio. Флаг extraction_done в sessions.",
         "Phase 10 RAG"],
        ["2", "FETCH SESSION", "SELECT messages WHERE session_id=X ORDER BY created_at. Собрать user/assistant/tool_calls. Фильтр: ≥3 messages и ≥1 assistant.",
         "SQLite"],
        ["3", "ANONYMIZE", "Если Learn opt-in + anonymize toggle on — прогнать через orchestrator/redact.py. Заменить ИНН/имена/суммы на токены.",
         "redact.py есть"],
        ["4", "CASE EXTRACTOR LLM", "Aux LLM (cheaper модель). T=0.1. Prompt: 'извлеки типовые решения'. Expected JSON: {extract:bool, cases:[...]}",
         "OpenAI-compatible API"],
        ["5", "PARSE + VALIDATE", "Парсинг JSON. Валидация: title 10-200 символов, problem 50-2000, solution 100-5000. confidence 1-3 (4-5 только после user validation). max 5 cases/session.",
         "Pydantic"],
        ["6", "DEDUP CHECK", "По FTS: похожий case_fts WHERE title MATCH. По vector: cosine <0.15 = дубликат. Если дубликат — usage_count++, не создавать.",
         "FTS5 + sqlite-vec"],
        ["7", "EMBED CASE", "embed(title + ' ' + problem_description) через API. INSERT INTO cases_vec. Батч: 10 cases на один API call (экономия).",
         "Embedding API"],
        ["8", "QUALITY GATE (async)", "thumbs_down > thumbs_up ИЛИ confidence<2 после 5 uses → авто-архивация. confidence=3 + usage_count≥3 + thumbs_up>0 → UI 'поднять до 4?'",
         "Cron / nightly job"],
        ["9", "INJECT INTO PROMPT", "Before each turn: hybrid_search(query) → bm25 top-10 + vec top-10 → RRF merge → top-3 → блок '### Похожие кейсы' в system prompt",
         "RRF k=60"],
        ["10", "FEEDBACK COLLECTION", "После ответа UI показывает карточки кейсов. Thumbs → scores таблица. Implicit clicks → usage_count++.",
         "Phase 14 UI"],
    ]
    fill_data_rows(ws, 5, pipeline)

    style_section_row(ws, 16, 4, "SQL DDL: Case Repository (миграция v11)")
    ddl_cell = ws.cell(row=17, column=1)
    ws.merge_cells(start_row=17, start_column=1, end_row=17, end_column=4)
    ddl_cell.value = (
        "-- Миграция v11: Case Repository + Vector tables\n"
        "-- Запустить после установки sqlite-vec extension\n\n"
        "CREATE TABLE IF NOT EXISTS cases (\n"
        "    id TEXT PRIMARY KEY,\n"
        "    channel_id TEXT NOT NULL,\n"
        "    title TEXT NOT NULL,\n"
        "    problem_description TEXT NOT NULL,\n"
        "    symptoms TEXT,                  -- JSON array\n"
        "    solution TEXT NOT NULL,\n"
        "    tool_calls_example TEXT,\n"
        "    platform_version TEXT,\n"
        "    configuration TEXT,             -- 'УТ'|'ЕРП'|'КА'|'УСО'\n"
        "    tags TEXT,                      -- JSON array\n"
        "    confidence INTEGER DEFAULT 1,   -- 1-5\n"
        "    usage_count INTEGER DEFAULT 0,\n"
        "    thumbs_up INTEGER DEFAULT 0,\n"
        "    thumbs_down INTEGER DEFAULT 0,\n"
        "    provenance TEXT DEFAULT 'agent',-- 'agent'|'user'|'curated'\n"
        "    source_session_id TEXT,\n"
        "    version INTEGER DEFAULT 1,\n"
        "    version_notes TEXT,\n"
        "    is_archived BOOLEAN DEFAULT 0,\n"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        "    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        "    FOREIGN KEY (source_session_id) REFERENCES sessions(id) ON DELETE SET NULL\n"
        ");\n\n"
        "CREATE INDEX IF NOT EXISTS idx_cases_channel ON cases(channel_id, is_archived);\n"
        "CREATE INDEX IF NOT EXISTS idx_cases_confidence ON cases(confidence DESC);\n"
        "CREATE INDEX IF NOT EXISTS idx_cases_usage ON cases(usage_count DESC);\n\n"
        "-- FTS5 для keyword search\n"
        "CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(\n"
        "    title, problem_description, solution,\n"
        "    case_id UNINDEXED, channel_id UNINDEXED,\n"
        "    tokenize = 'porter unicode61'\n"
        ");\n\n"
        "-- Vector table для ANN (sqlite-vec)\n"
        "CREATE VIRTUAL TABLE IF NOT EXISTS cases_vec USING vec0(\n"
        "    case_id TEXT PRIMARY KEY,\n"
        "    embedding FLOAT[1536]  -- text-embedding-3-small\n"
        ");\n\n"
        "-- Vector для messages (Phase 10)\n"
        "CREATE VIRTUAL TABLE IF NOT EXISTS messages_vec USING vec0(\n"
        "    message_id TEXT PRIMARY KEY,\n"
        "    session_id TEXT,\n"
        "    channel_id TEXT,\n"
        "    embedding FLOAT[1536]\n"
        ");\n\n"
        "-- Таблица оценок (Phase 14)\n"
        "CREATE TABLE IF NOT EXISTS scores (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    session_id TEXT NOT NULL,\n"
        "    message_id TEXT,\n"
        "    case_id TEXT,\n"
        "    score_type TEXT NOT NULL,   -- 'thumbs_up'|'thumbs_down'|'copy_code'|'expand_trace'\n"
        "    value INTEGER DEFAULT 1,\n"
        "    user_comment TEXT,\n"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        "    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE\n"
        ");\n"
    )
    ddl_cell.font = FONT_MONO
    ddl_cell.alignment = ALIGN_LEFT_TOP
    ddl_cell.border = BORDER_ALL
    ws.row_dimensions[17].height = 800


def sheet_09_roadmap(wb: Workbook) -> None:
    ws = wb.create_sheet("09_Roadmap_общий")
    set_col_widths(ws, [4, 8, 28, 36, 14, 14, 26])

    style_title_row(ws, 1, 7, "Объединённый Roadmap — что и когда внедрять")

    style_section_row(ws, 3, 7, "Условные обозначения: P0 — критично, P1 — высокий, P2 — средний, P3 — опционально")

    style_header_row(ws, 4, 7)
    for col, val in enumerate(["#", "Фаза", "Шаг", "Описание", "Часы", "Приоритет", "Зависимости"]):
        ws.cell(row=4, column=col + 1, value=val)

    roadmap = [
        # Week 1
        ["1", "W1", "ИТС·P0a: v8std MCP публичный", "Подключить https://ai.v8std.ru/mcp как канал в .mcp.json. Покрытие: стандарты разработки.",
         "4", "P0", "—"],
        ["2", "W1", "ИТС·P0b: comol/ai_rules_1c", "git clone в tools/, конвертация .md в плоский текст для prompt cache.",
         "2", "P0", "—"],
        ["3", "W1", "ИТС·P0c: Prompt caching 1h", "knowledge_base.md (правила+стандарты) → system prompt с cache_control TTL=1h.",
         "4", "P0", "P0a, P0b"],
        # Phase 10
        ["4", "P10", "RAG·sqlite-vec install", "pip install sqlite-vec. Подключить через db.enable_load_extension. PyInstaller bundle.",
         "4", "P0", "—"],
        ["5", "P10", "Миграция v11: messages_vec", "CREATE VIRTUAL TABLE USING vec0. Индексы.",
         "2", "P0", "sqlite-vec"],
        ["6", "P10", "EmbeddingJob async worker", "INSERT message с role=assistant → batch embed → INSERT messages_vec. Backfill.",
         "8", "P0", "OpenAI API"],
        ["7", "P10", "RAG prefetch hook", "Before turn: embed(query) → ANN top-5 + BM25 top-5 → RRF merge → инжекция.",
         "8", "P0", "messages_fts (есть)"],
        ["8", "P10", "Config + Tests", "ENABLE_RAG=true/false, RAG_TOP_K=5. test_rag_prefetch.py.",
         "4", "P0", "—"],
        ["9", "P10", "UI: StreamingStages индикатор", "\"Использовано N кейсов из истории\" в stages component.",
         "4", "P0", "—"],
        # Phase 12: Lineage MVP
        ["10", "P12", "Lineage·MCP get_document_chain", "Новый endpoint через execute_code BSL traversal (родители + регистры + потребители).",
         "12", "P1", "MCP Toolkit EPF"],
        ["11", "P12", "Lineage·SQLite кэш", "graph_cache таблица с TTL. Hit rate >60% после прогрева.",
         "4", "P1", "—"],
        ["12", "P12", "Lineage·React Flow карточка", "@xyflow/react + dagre. Кастомные узлы с типами. Раскрытие по клику.",
         "10", "P1", "npm install"],
        ["13", "P12", "Lineage·FastAPI /api/document/chain", "REST endpoint поверх MCP + кэш.",
         "4", "P1", "—"],
        ["14", "P12", "Lineage·get_register_movements", "MCP операция + RegisterMovementsCard.",
         "14", "P1", "—"],
        # Phase 12: ITS Sprint 1
        ["15", "P12", "ИТС·Sprint1: onec-help-mcp self-hosted", "Docker + Qdrant + копирование HBK из локальной 1С. Подключить как MCP.",
         "16", "P1", "Docker"],
        ["16", "P12", "ИТС·Sprint1: v8std self-hosted", "Локальный индекс v8std jsonl вместо публичного MCP — для конфиденциального кода.",
         "8", "P1", "—"],
        # Phase 12: Case Repo
        ["17", "P12", "Case Repository: миграция v12", "cases + cases_fts + cases_vec tables.",
         "4", "P2", "Phase 10 RAG"],
        ["18", "P12", "CaseRepository class", "CRUD: add, get, search_hybrid, update_confidence, archive.",
         "12", "P2", "—"],
        ["19", "P12", "CaseExtractor: session-level LLM", "Trigger >2h idle. Prompt template. Dedup через cosine.",
         "16", "P2", "Aux LLM"],
        ["20", "P12", "CaseUI: \"Похожие кейсы\" sidebar", "Collapsible (как tool trace). Топ-3 inline.",
         "8", "P2", "—"],
        ["21", "P12", "Admin /api/cases CRUD", "Ручная curation. Confidence UI (поднять до 4-5).",
         "6", "P2", "—"],
        # Phase 13: Errors
        ["22", "P13", "Errors·SSE endpoint", "FastAPI /api/events/stream через polling get_event_log (для серверных баз).",
         "8", "P1", "sse-starlette"],
        ["23", "P13", "Errors·LiveEventFeedCard", "EventSource API, фильтры, пауза, экспорт.",
         "6", "P1", "—"],
        ["24", "P13", "Errors·analyze_error MCP", "Контекст кода + LLM-объяснение + 3 варианта исправления.",
         "16", "P1", "git checkout исходников"],
        ["25", "P13", "Errors·ErrorDiagnosisCard", "Monaco + highlighted line + AI causes + actions.",
         "10", "P1", "Monaco (есть)"],
        ["26", "P13", "Errors·get_document_errors MCP", "Ошибки связанные с конкретным документом.",
         "8", "P1", "—"],
        # Phase 13: Feedback
        ["27", "P13", "Feedback·scores table + API", "POST /api/scores {message_id, type, value}. CASCADE.",
         "4", "P2", "Phase 12 cases"],
        ["28", "P13", "Feedback·Thumbs UI", "Компоненты в ChatMessage. Implicit clipboard события.",
         "6", "P2", "—"],
        ["29", "P13", "Feedback·confidence recalc job", "Cron/nightly: пересчёт confidence по thumbs ratio.",
         "4", "P2", "—"],
        # Phase 14: BSL LSP + Impact
        ["30", "P14", "BSL LSP·WebSocket bridge", "FastAPI WebSocket ↔ BSL LS Java stdin/stdout.",
         "12", "P2", "Java 17 (есть)"],
        ["31", "P14", "BSL LSP·Monaco integration", "monaco-languageclient v10.7.0. dynamic import (SSR).",
         "16", "P2", "npm"],
        ["32", "P14", "BSL LSP·BSLDiagnosticsCard", "Inline markers + autofix actions.",
         "8", "P2", "—"],
        ["33", "P14", "Impact·bsl-graph Docker", "Setup + REST integration.",
         "12", "P3", "Docker, Java"],
        ["34", "P14", "Impact·ImpactAnalysisCard", "\"Что сломается при изменении X\".",
         "10", "P3", "bsl-graph"],
        ["35", "P14", "CallGraphCard", "get_call_graph MCP + React Flow.",
         "8", "P3", "—"],
        # Phase 15
        ["36", "P15", "Growth Dashboard", "Метрики роста знаний: кейсов накоплено, thumbs-up rate, RAG hit rate.",
         "16", "P3", "Phase 14"],
    ]
    end = fill_data_rows(ws, 5, roadmap)
    for i in range(5, end):
        apply_priority_color(ws, i, 6, ws.cell(row=i, column=6).value)

    # Итог
    total_hours = sum(int(r[4]) for r in roadmap)
    p0_hours = sum(int(r[4]) for r in roadmap if r[5] == "P0")
    p1_hours = sum(int(r[4]) for r in roadmap if r[5] == "P1")
    p2_hours = sum(int(r[4]) for r in roadmap if r[5] == "P2")
    p3_hours = sum(int(r[4]) for r in roadmap if r[5] == "P3")

    style_accent_row(ws, end + 1, 7,
        f"Итого: {len(roadmap)} шагов · {total_hours} ч. "
        f"По приоритетам: P0={p0_hours}ч, P1={p1_hours}ч, P2={p2_hours}ч, P3={p3_hours}ч."
    )


def sheet_10_budget(wb: Workbook) -> None:
    ws = wb.create_sheet("10_Стоимость")
    set_col_widths(ws, [4, 28, 18, 18, 18, 40])

    style_title_row(ws, 1, 6, "Стоимость и бюджет — единоразово + ежемесячно")

    style_section_row(ws, 3, 6, "Ежемесячные расходы (USD)")
    style_header_row(ws, 4, 6)
    for col, val in enumerate(["#", "Категория", "MVP (W1)", "Sprint 1 (1 мес)", "Full (3 мес)", "Комментарий"]):
        ws.cell(row=4, column=col + 1, value=val)

    rows = [
        ["1", "LLM Claude Sonnet 4.6 (input+output)", "$50", "$150", "$300",
         "Базовая стоимость без caching. С caching 1h — экономия 60-90%."],
        ["2", "Prompt Caching (cache_write 1h × 24)", "+$30", "+$30", "+$30",
         "Cache write = 2x input цена один раз в час. Окупается со 2-го запроса."],
        ["3", "Cache Reads", "-$80", "-$200", "-$400",
         "Cache read = 10% input цены. ЭКОНОМИЯ на повторных промптах."],
        ["4", "Embeddings (text-embedding-3-small @ $0.02/1M)", "$0.50", "$2", "$5",
         "100K-500K токенов/мес для multi-tenant работы. Малозаметно."],
        ["5", "Embeddings альтернатива: Voyage AI", "$1", "$5", "$15",
         "voyage-multilingual-2 @ $0.12/1M, лучшее для русского+code."],
        ["6", "Qdrant (если onec-help-mcp self-hosted)", "$0", "$10", "$10-30",
         "Локально бесплатно. VPS $10-30/мес для 4GB RAM."],
        ["7", "BSL Language Server", "$0", "$0", "$0",
         "OSS, локально. Только CPU."],
        ["8", "Neo4j (опц. для Phase 13+)", "$0", "$0", "$0-65",
         "Self-hosted бесплатно. AuraDB cloud $65+/мес."],
        ["9", "Хранилище SQLite (всё в одном файле)", "$0", "$0", "$0",
         "Локально. Электрон bundle включает sqlite-vec."],
        ["10", "Anthropic Claude API альтернативы", "$0", "$0", "$0",
         "Может работать с любым OpenAI-compatible: NVIDIA NIM, Xiaomi MiMo, GPT-4o, DeepSeek."],
    ]
    fill_data_rows(ws, 5, rows)

    style_section_row(ws, 16, 6, "ИТОГО месячные расходы (с учётом cache savings)")
    style_header_row(ws, 17, 6)
    for col, val in enumerate(["", "Сценарий", "MVP (W1)", "Sprint 1 (1 мес)", "Full (3 мес)", ""]):
        ws.cell(row=17, column=col + 1, value=val)

    fill_data_rows(ws, 18, [
        ["", "Минимум (всё локально, только LLM)", "~$50", "~$110", "~$250", ""],
        ["", "Реалистично (RAG + Qdrant + cache)", "~$80", "~$160", "~$350", ""],
        ["", "С опциями (Neo4j cloud, Voyage)", "~$100", "~$200", "~$450", ""],
    ])

    style_section_row(ws, 22, 6, "Единоразовые расходы")
    style_header_row(ws, 23, 6)
    for col, val in enumerate(["#", "Что", "Стоимость", "Когда", "", "Комментарий"]):
        ws.cell(row=23, column=col + 1, value=val)

    fill_data_rows(ws, 24, [
        ["1", "Embedding backfill истории сессий", "$0.50-2", "Phase 10 setup", "",
         "Все assistant messages — раз пройти эмбедингом."],
        ["2", "Code-signing certificate (Electron)", "$200-400", "v1.3.0", "",
         "Уже в roadmap (snapshot 2026-05-18). Снимает SmartScreen warning."],
        ["3", "Domain + SSL (если будет SaaS)", "$15-50", "Pivot to SaaS", "",
         "Если решите делать публичный сервис вместо on-prem desktop."],
        ["4", "Fine-tuning (НЕ рекомендуется)", "$500+", "Если выберете путь", "",
         "Не делать. Anti-pattern в данной архитектуре."],
    ])

    style_section_row(ws, 30, 6, "ROI: когда инвестиции окупаются")
    fill_data_rows(ws, 31, [
        ["", "Если инструмент продаётся аналитику франчайзи", "1 клиент × 3000₽/мес ≈ $30/мес",
         "11 клиентов = $330/мес = покрывает Sprint 1", "", "Дальше — чистая прибыль"],
        ["", "Если использовать внутренне в команде", "Экономия 10 часов аналитика × 3000₽/час",
         "= 30 000₽/мес экономии × 1 человек", "", "Окупается за 1 неделю на одном консультанте"],
        ["", "Если SaaS для нескольких компаний", "5000₽/мес × 20 компаний = 100 000₽/мес",
         "ARR ~1.2M₽/год", "", "Phase 15 (Growth Dashboard) — для маркетинга"],
    ])


def sheet_11_risks(wb: Workbook) -> None:
    ws = wb.create_sheet("11_Риски")
    set_col_widths(ws, [4, 14, 36, 14, 14, 38])

    style_title_row(ws, 1, 6, "Единый реестр рисков")
    style_header_row(ws, 3, 6)
    for col, val in enumerate(["#", "Направление", "Риск", "Вероятность", "Влияние", "Митигейшен"]):
        ws.cell(row=3, column=col + 1, value=val)

    risks = [
        # ИТС
        ["1", "ИТС", "Публичный v8std MCP видит код клиента — конфиденциальность",
         "Высокая", "Высокое", "Self-hosted v8std для production. Публичный только для dev/тестов."],
        ["2", "ИТС", "onec-help-mcp требует Docker — Electron-конфликт",
         "Средняя", "Среднее", "Опциональная зависимость. Без него — fallback на v8std MCP + prompt cache."],
        ["3", "ИТС", "1С предъявит претензии за HBK-парсинг",
         "Низкая", "Высокое", "Не включать .hbk в дистрибутив. Индексация только из локальной установки пользователя."],
        ["4", "ИТС", "Cache miss первого запроса в час = 2x цена",
         "Средняя", "Низкое", "1h TTL Anthropic — окупается после 2-го запроса. Прогрев на старте сессии."],
        # Цепочки
        ["5", "Цепочки", "execute_code timeout при глубоком обходе lineage",
         "Высокая", "Высокое", "Ограничить depth_down=2, добавить async + SQLite кэш."],
        ["6", "Цепочки", "monaco-languageclient SSR-конфликт в Next.js 15",
         "Высокая", "Среднее", "dynamic(() => import('./Monaco'), { ssr: false }) для всех Monaco-компонентов."],
        ["7", "Цепочки", "ibcmd недоступен для серверных баз клиентов",
         "Средняя", "Среднее", "Fallback на polling get_event_log (5-10 сек задержка приемлема)."],
        ["8", "Цепочки", "bsl-graph alpha-статус — нет SLA",
         "Высокая", "Низкое", "Только в Phase 14, не блокировать MVP. Альтернатива — find_references."],
        ["9", "Цепочки", "git checkout исходников клиента недоступен",
         "Средняя", "Высокое", "Сохранять код в SQLite при первом получении через get_metadata."],
        ["10", "Цепочки", "LLM галлюцинирует детали ошибки",
         "Средняя", "Среднее", "Метка 'AI-объяснение, проверьте вручную'. Ссылка на точную строку кода."],
        ["11", "Цепочки", "Нагрузка на 1С-базу от частых MCP",
         "Низкая", "Высокое", "Rate limiting в FastAPI. Агрессивное кэширование. Polling 5+ сек."],
        # Самообучение
        ["12", "Самообучение", "sqlite-vec не интегрируется с PyInstaller (.dll)",
         "Средняя", "Высокое", "Fallback на pure Python ANN через numpy.dot для <10K векторов."],
        ["13", "Самообучение", "Aux LLM недоступен для background_review",
         "Низкая", "Среднее", "Очередь pending_extraction. Retry при следующем старте."],
        ["14", "Самообучение", "Пользователь не включает Learn opt-in (privacy)",
         "Средняя", "Среднее", "Тогда работает только Procedural (SkillStore). Partial self-learning ОК."],
        ["15", "Самообучение", "Кейсы плохого качества автоматически попадают в базу",
         "Высокая", "Высокое", "confidence 1-3 автоматически, 4-5 только после user validation. Curation."],
        ["16", "Самообучение", "Multi-tenant утечка через RAG (баг)",
         "Низкая", "КРИТИЧНОЕ", "ЖЁСТКОЕ правило: каждый запрос к vec → WHERE channel_id=?. Тест на pivote."],
        ["17", "Самообучение", "Cold start — первые 2-4 недели база пустая",
         "Высокая", "Низкое", "Pre-load 20 \"стартовых\" кейсов из вашего опыта (1С Транзит)."],
        ["18", "Самообучение", "Embedding API недоступен у NVIDIA NIM",
         "Средняя", "Среднее", "Выделенный OpenAI key только для embeddings ($0.50-2/мес)."],
        ["19", "Самообучение", "RAG prefetch добавляет latency",
         "Низкая", "Среднее", "Параллельный async fetch. Target <200ms (sqlite-vec @ CPU справляется)."],
        # Стратегические
        ["20", "Стратегия", "Скоп проекта расползётся (feature creep)",
         "Высокая", "Высокое", "Чёткий приоритет: P0 → P1 → P2. Не браться за P2 пока P1 не доделан."],
        ["21", "Стратегия", "Пользователь не понимает ценность нового",
         "Средняя", "Среднее", "Growth Dashboard (Phase 15) показывает метрики роста явно."],
        ["22", "Стратегия", "Конкуренты (Aether Lab, 1С:Напарник) опередят",
         "Средняя", "Среднее", "Ваше преимущество: реальное выполнение через MCP + RAG + privacy-first."],
        ["23", "Стратегия", "Платформа 1С 8.5.x ломает совместимость MCP",
         "Низкая", "Высокое", "Тест на 8.5.1 стенде в августе 2026. План адаптации к декабрю."],
    ]
    end = fill_data_rows(ws, 4, risks)
    for i in range(4, end):
        apply_priority_color(ws, i, 4, ws.cell(row=i, column=4).value)
        apply_priority_color(ws, i, 5, ws.cell(row=i, column=5).value)


def sheet_12_metrics(wb: Workbook) -> None:
    ws = wb.create_sheet("12_Метрики_успеха")
    set_col_widths(ws, [4, 12, 28, 28, 22, 30])

    style_title_row(ws, 1, 6, "Метрики успеха — как поймём что работает")

    style_section_row(ws, 3, 6, "Направление I: ИТС интеграция")
    style_header_row(ws, 4, 6)
    for col, val in enumerate(["#", "Метрика", "Базовое значение", "Целевое значение", "Срок", "Как измерить"]):
        ws.cell(row=4, column=col + 1, value=val)

    fill_data_rows(ws, 5, [
        ["1", "Точность по стандартам", "Неизвестно (нет baseline)", ">85%", "30 дней",
         "Тест-набор: 20 вопросов из v8std с эталонными ответами"],
        ["2", "Hallucination rate (API платформы)", "~30% (без RAG)", "<5%", "60 дней",
         "20 вопросов о методах объектов; считаем выдуманные сигнатуры"],
        ["3", "Latency p95 ответа AI-чата", "Текущий baseline", "<5 сек (с RAG)", "Сразу",
         "FastAPI middleware замер duration_ms"],
        ["4", "Cache hit rate", "0% (нет caching)", ">90%", "1 неделя",
         "Anthropic usage dashboard"],
        ["5", "Аналитик NPS '1С-knowledge'", "—", ">8/10", "30 дней",
         "Опрос аналитиков после demo"],
    ])

    style_section_row(ws, 11, 6, "Направление II: Цепочки + Errors")
    style_header_row(ws, 12, 6)
    for col, val in enumerate(["#", "Метрика", "Базовое значение", "Целевое значение", "Срок", "Как измерить"]):
        ws.cell(row=12, column=col + 1, value=val)

    fill_data_rows(ws, 13, [
        ["1", "Время построения графа (depth=2)", "—", "<5 сек", "Сразу",
         "FastAPI middleware замер"],
        ["2", "Время построения графа (depth=3)", "—", "<15 сек", "Сразу", "—"],
        ["3", "Задержка отображения ошибки", "—", "<10 сек от события до UI", "Phase 13",
         "Замер SSE round-trip"],
        ["4", "Задержка LLM-объяснения ошибки", "—", "<5 сек (Sonnet 4.6)", "Phase 13", "—"],
        ["5", "Cache hit rate (графы)", "0%", ">60%", "Phase 12",
         "SQLite graph_cache stats"],
        ["6", "Точность LLM-объяснения ошибок", "—", ">75% (по оценке аналитика)", "Phase 13",
         "A/B feedback кнопки"],
        ["7", "% сессий с использованием цепочек", "0%", ">40%", "30 дней после Phase 12",
         "Telemetry на компоненте"],
    ])

    style_section_row(ws, 21, 6, "Направление III: Самообучение")
    style_header_row(ws, 22, 6)
    for col, val in enumerate(["#", "Метрика", "Базовое значение", "Целевое значение", "Срок", "Как измерить"]):
        ws.cell(row=22, column=col + 1, value=val)

    fill_data_rows(ws, 23, [
        ["1", "Thumbs-up rate", "~50% (предположение)", ">65% (30д) → >75% (90д)", "30/90 дней",
         "SELECT FROM scores WHERE score_type='thumbs_up' / total"],
        ["2", "RAG Hit Rate", "0%", ">40% (после 2 нед накопления)", "14 дней",
         "Логировать в messages.metadata"],
        ["3", "% повторных вопросов", "Высокий (>50%)", "<20%", "30 дней",
         "Cosine >0.85 между запросами в одном channel"],
        ["4", "Case Reuse", "—", ">60% turn'ов с инжектированным case → thumbs_up", "60 дней",
         "scores WHERE case_id IS NOT NULL"],
        ["5", "Размер базы кейсов", "0", ">50 validated кейсов", "30 дней",
         "SELECT COUNT(*) FROM cases WHERE confidence >= 3"],
        ["6", "Confidence distribution", "Только 1-2", ">50% кейсов confidence 3-4 + >10% conf=5", "90 дней",
         "Гистограмма по cases.confidence"],
        ["7", "Time to Answer (без регрессии)", "Текущий baseline", "Без регрессии (RAG prefetch <200ms)", "Сразу",
         "duration_ms сравнение"],
    ])

    style_section_row(ws, 32, 6, "Интегральные метрики продукта")
    style_header_row(ws, 33, 6)
    for col, val in enumerate(["#", "Метрика", "Базовое", "Целевое", "Срок", "Как измерить"]):
        ws.cell(row=33, column=col + 1, value=val)

    fill_data_rows(ws, 34, [
        ["1", "DAU/MAU (если SaaS)", "0", ">40% (sticky product)", "90 дней", "Telemetry"],
        ["2", "Средняя длина сессии", "—", ">15 минут (deep work)", "30 дней", "session.duration"],
        ["3", "Кол-во вопросов на сессию", "—", ">5", "30 дней", "messages count / session"],
        ["4", "Время до первого 'wow' момента", "—", "<5 минут", "Onboarding test", "Опрос новых пользователей"],
        ["5", "Conversion из demo → paid", "—", ">20%", "Когда будет sales", "CRM"],
    ])


def sheet_13_anti(wb: Workbook) -> None:
    ws = wb.create_sheet("13_Анти-паттерны")
    set_col_widths(ws, [4, 14, 32, 50])

    style_title_row(ws, 1, 4, "Анти-паттерны — что НЕ делать")

    style_section_row(ws, 3, 4, "Из всех 3 исследований")
    style_header_row(ws, 4, 4)
    for col, val in enumerate(["#", "Направление", "Что НЕ делать", "Почему — что вместо"]):
        ws.cell(row=4, column=col + 1, value=val)

    anti = [
        # ИТС
        ["1", "ИТС", "Парсить its.1c.ru web автоматически",
         "Нарушение ToS, риск блокировки аккаунта. Используй v8std (CC0) + локальные ресурсы."],
        ["2", "ИТС", "Подключать 1С:Напарник к продукту",
         "EULA явно запрещает commercial. Юридический риск. Используй своё решение через MCP."],
        ["3", "ИТС", "Fine-tuning LLM на BSL-корпусе",
         "Нет готового датасета (нужно 10K+ Q&A пар). Дорого ($500+). Catastrophic forgetting. RAG+Claude лучше."],
        ["4", "ИТС", "Включать .hbk в дистрибутив",
         "EULA серая зона. Индексируй из локальной установки 1С пользователя."],
        ["5", "ИТС", "GraphRAG как первый шаг",
         "Преждевременная оптимизация. Сначала Hybrid RAG (Phase 10). GraphRAG только если действительно нужны связи."],
        # Цепочки
        ["6", "Цепочки", "Парсить XML формы вручную",
         "AI генерит кривое (Form.xml = мёртвая зона). Используй DESIGNER → DumpConfigToFiles → AI правит JSON через form-edit."],
        ["7", "Цепочки", "Молча генерировать lineage без depth ограничения",
         "Глубокий обход = timeout 30 сек. Ограничь depth_down=2 как default."],
        ["8", "Цепочки", "Real-time pollить get_event_log каждую секунду",
         "Нагрузка на 1С-базу. Минимум 5 сек интервал. Лучше — ibcmd JSON stream."],
        ["9", "Цепочки", "Открывать Monaco без dynamic ssr:false",
         "SSR-конфликт в Next.js 15. ВСЕГДА используй dynamic(() => import, { ssr: false })."],
        ["10", "Цепочки", "Молча игнорировать ошибку MCP",
         "Пользователь не понимает что произошло. Confirm dialog (как scan_for_dangerous уже есть)."],
        # Самообучение
        ["11", "Самообучение", "Делать fine-tuning",
         "Нужно 1000+ preference pairs. Дорого. RAG+Skills всегда лучше для domain-specific."],
        ["12", "Самообучение", "Подключать mem0/Letta как external dependency",
         "Electron desktop, cloud-dependency нарушает offline. SaaS падает — приложение ломается."],
        ["13", "Самообучение", "Embed ВСЁ подряд (tool_calls, errors)",
         "Шум для retrieval. Embed только role=assistant content + case.solution. + user_message для похожих вопросов."],
        ["14", "Самообучение", "Генерировать cases из коротких сессий",
         "1-2 вопроса не дают паттерна. Минимум 3 turn'а И 500+ символов assistant контента."],
        ["15", "Самообучение", "Доверять confidence 4-5 автоматически",
         "LLM-экстрактор ошибается на 1С-домене. Confidence 1-3 авто, 4-5 только после user validation."],
        ["16", "Самообучение", "Хранить embeddings в отдельной БД",
         "Рассинхрон при удалении (CASCADE не пересекает файлы). Всё в одном app.db."],
        ["17", "Самообучение", "Embedding при каждом /chat",
         "Latency hit + стоимость. Embed при записи message (async). Retrieve по pre-computed."],
        ["18", "Самообучение", "Игнорировать channel_id в vector queries",
         "САМЫЙ КРИТИЧНЫЙ privacy баг. ЖЁСТКОЕ правило: каждый запрос → WHERE channel_id=?"],
        ["19", "Самообучение", "RAG из archived skills/cases",
         "Curator архивирует по причине. Всегда WHERE is_archived=0."],
        ["20", "Самообучение", "Knowledge Graph сразу (Phase 12)",
         "Преждевременная оптимизация. networkx на 200 кейсах не даёт прироста. Только если >500 кейсов И жалобы на качество поиска."],
        # Стратегические
        ["21", "Стратегия", "Браться за P2 пока P1 не готов",
         "Feature creep. Дисциплина: P0→P1→P2 строго последовательно."],
        ["22", "Стратегия", "Игнорировать тёмную тему / Plex Mono в новых UI",
         "Brand Stencil/Mono — source of truth. Mockups в Markdown OK, но в коде — design tokens."],
        ["23", "Стратегия", "Делать сразу под SaaS multi-user",
         "v0/v0b провальные итерации показали. Сначала single-user, потом multi-tenant, потом SaaS."],
    ]
    fill_data_rows(ws, 5, anti)


def sheet_14_vision(wb: Workbook) -> None:
    ws = wb.create_sheet("14_Видение_развития")
    set_col_widths(ws, [4, 26, 50, 26])

    style_title_row(ws, 1, 4, "Видение развития — что добавить от меня (Claude) на основе анализа возможных будущих проблем")

    style_section_row(ws, 3, 4, "Потенциальные будущие проблемы и предлагаемые ответы")
    style_header_row(ws, 4, 4)
    for col, val in enumerate(["#", "Будущая проблема", "Что предлагаю", "Когда внедрять"]):
        ws.cell(row=4, column=col + 1, value=val)

    vision = [
        ["1",
         "Аналитик задаёт вопросы о реальных бизнес-процессах клиента, AI отвечает только по техническому контексту",
         "Добавить Business Context Layer: после connect к базе — extract бизнес-роли (УТ vs ЕРП), типовые процессы, sigma/таможня/розница и т.д. Через get_metadata + LLM-классификатор. Хранить в channel_metadata таблице. Использовать как часть system prompt.",
         "Phase 12.5"],
        ["2",
         "Когда аналитик работает с 5+ клиентами параллельно — теряется контекст",
         "Channel Memory Cards: per-channel memo автогенерируется из истории сессий. Показывается в Header при переключении канала. \"Что было в прошлый раз / открытые вопросы / специфика этого клиента\".",
         "Phase 13"],
        ["3",
         "База решений растёт неконтролируемо — поиск становится медленным/неточным",
         "Hierarchical Memory: cases уровней L1 (specific, &lt;30 дней) → L2 (generalized, до 6 мес) → L3 (timeless, &gt;6 мес). Автоматическая консолидация: похожие L1 → одна L2.",
         "Phase 15"],
        ["4",
         "Конкуренты выпускают аналог, у нас нет дифференциации",
         "Federated Knowledge: аналитики опционально делятся кейсами (анонимизированно) в общий pool. Каждый получает доступ к коллективному опыту франчайзи 1С. Privacy-first: opt-in, anonymized, vector-only (не текст).",
         "Phase 16+"],
        ["5",
         "Ошибки в production у клиента — аналитик узнаёт поздно",
         "Proactive Monitoring: фоновый job опрашивает event log каждые 5 мин на каждом канале. При CRITICAL — push notification в Electron + email + Telegram. \"Сообщение от твоего AI-помощника — у клиента X отказ проведения\".",
         "Phase 17"],
        ["6",
         "Аналитик не доверяет AI на сложных кейсах",
         "Confidence Transparency: каждый ответ маркирован уровнем доверия (1-5 ★). Цифра берётся из confidence используемых кейсов + LLM self-evaluation + наличие подтверждающих источников. Низкое доверие → явный disclaimer + предложение проверить вручную.",
         "Phase 13"],
        ["7",
         "Скорость работы падает по мере роста базы",
         "Tiered Storage: горячие данные (последние 30 дней) — в основной SQLite. Холодные — в архивный файл. Прозрачно для пользователя. SQLite ATTACH DATABASE для архива.",
         "Phase 15"],
        ["8",
         "Стоимость LLM растёт линейно с пользователями",
         "Smart Routing: simple lookup queries → cheap LLM (Haiku/cheap NIM). Сложный анализ → Claude Sonnet/Opus. Auto-classification on input. Снижение costs в 3-5 раз для типовых вопросов.",
         "Phase 14"],
        ["9",
         "Аналитик хочет автоматизировать рутинные действия (cron-задачи)",
         "Recipe Mode: записать сценарий через demo → AI извлекает шаги → сохраняет как 'recipe' → можно запустить по расписанию. Например: \"Каждый понедельник в 9:00 — отчёт по просроченным ОПП в Telegram\".",
         "Phase 16"],
        ["10",
         "Onboarding нового аналитика на проект занимает дни",
         "Pair-Programming Mode: новый аналитик подключается к каналу, AI автоматически показывает релевантные кейсы из истории старшего аналитика (если он дал доступ). Knowledge transfer без manual handoff.",
         "Phase 16+"],
        ["11",
         "Аналитик ошибается с execute_code — портит данные",
         "Sandbox / Dry-Run Mode: для execute_code добавить --dry-run флаг (получить план изменений без применения). Confirm dialog (уже есть) усилить explanation \"что произойдёт\". Snapshot перед мутациями.",
         "Phase 13"],
        ["12",
         "Нет понимания ROI инструмента для бизнеса",
         "Value Dashboard: \"За месяц AI сэкономил тебе X часов\" — через extraction \"что бы аналитик делал руками\". На основе типов запросов считается экономия. Видимая ценность.",
         "Phase 15"],
        ["13",
         "Многоязычные конфигурации (английский интерфейс УТ Pro)",
         "Locale Detection per Channel: автоматически определять язык метаданных (Russian/English). Использовать соответствующий v8std MCP. Корректные prompt templates.",
         "Phase 14"],
        ["14",
         "Переход 1С на 8.5.x ломает MCP Toolkit",
         "Compatibility Matrix: для каждой версии платформы — отдельный тестовый стенд. Smoke-тесты MCP Toolkit на каждой версии. Автоматическое снижение функционала при несовместимости (graceful degradation).",
         "Август 2026"],
        ["15",
         "Развитие в сторону полноценного 1С-Cursor",
         "Code Generation Mode: расширить чат до 'agentic mode' — AI не только отвечает, но и сам пишет CFE / правит запросы / запускает тесты через метр. Использовать ваш существующий 1c-feature-dev workflow.",
         "Phase 18+"],
    ]
    fill_data_rows(ws, 5, vision)

    style_section_row(ws, 21, 4, "Долгосрочное видение (1-2 года)")
    fill_data_rows(ws, 22, [
        ["A", "Стать стандартом для франчайзи 1С",
         "Через 1 год — 100+ аналитиков активно используют. Через 2 — встроено в типовой стек франчайзи. Конкурент 1С:Напарника по позиционированию, но более открытый и Privacy-first.",
         "12-24 мес"],
        ["B", "Marketplace кейсов",
         "Аналитики могут публиковать solved cases в общий каталог (с лицензией). Дополнительный revenue stream. Network effect.",
         "12-18 мес"],
        ["C", "Plugin ecosystem",
         "Открытый API для extensions: интеграция с Jira/Telegram/CRM. Сообщество разработчиков. 1С-расширения для analyst-workspace.",
         "18-24 мес"],
        ["D", "Mobile / web (без Electron)",
         "Phase 20+. Только когда core стабилен. Web для просмотра, mobile для notifications + voice queries.",
         "24+ мес"],
        ["E", "Voice-first interface",
         "Запрос голосом → ответ голосом (для встреч с заказчиком). Использовать существующий voice-agent-1c проект.",
         "18-24 мес"],
    ])


# ═══════════════════════════════════════════════════════════════════════
#
#  ВТОРАЯ ИТЕРАЦИЯ (2026-05-24): конкурентный анализ +
#  декомпозиция работы аналитика + путь к 60% покрытия
#
# ═══════════════════════════════════════════════════════════════════════


def sheet_15_competitors(wb: Workbook) -> None:
    ws = wb.create_sheet("15_Конкуренты_Landscape")
    set_col_widths(ws, [4, 28, 22, 22, 16, 14, 10, 30])

    style_title_row(ws, 1, 8, "IV.1 Конкурентный landscape — 19 продуктов")
    style_section_row(ws, 3, 8, "Российский рынок (1С-специфика)")
    style_header_row(ws, 4, 8)
    for col, val in enumerate(["#", "Продукт", "Тип", "Целевой пользователь",
                                "Цена", "Год", "Threat", "Главный gap для нас"]):
        ws.cell(row=4, column=col + 1, value=val)

    rus = [
        ["1", "1С:Напарник (code.1c.ai)", "AI-ассистент для EDT", "Разработчик 1С",
         "Бесплатно до окт.2026", "2024", "5",
         "Только EDT, нет multi-tenant, нет workflow аналитика. Главный threat если расширится."],
        ["2", "Aether Lab Query Console", "AI-консоль запросов", "Разработчик/аналитик",
         "0-3 900 ₽/мес", "2024", "4",
         "Только запросы. Закрывает ~30% аналитика. Может развернуться."],
        ["3", "TurboConf 6 + FastCode AI", "Расширение Конфигуратора", "Разработчик 1С",
         "650 ₽/разраб/мес", "2019", "2",
         "Другой сегмент (разработчик в Конфигураторе)."],
        ["4", "mini-ai-1c (hawkxtreme)", "Desktop-ассистент", "Разработчик 1С",
         "Бесплатно (OS)", "2025", "2",
         "Desktop-обёртка через UIAutomation. Не для бизнес-задач."],
        ["5", "Confaster", "ИИ-агент в Конфигураторе", "Разработчик 1С",
         "Бесплатно", "2025", "2",
         "Свой MCP в Конфигураторе. Только код."],
        ["6", "mcp-1c (feenlace)", "MCP-сервер для AI+1С", "Продвинутый аналитик",
         "Бесплатно (OS)", "2025", "2",
         "Сами используем! Это часть нашего стека."],
        ["7", "1С-Коннект GPT Ассистент", "Корп.мессенджер + GPT", "Все пользователи",
         "Входит в 1С-Коннект", "2024", "1",
         "Общий GPT в мессенджере. Нет контекста базы."],
        ["8", "1С:Аналитика (BI)", "BI-платформа", "Руководитель/аналитик",
         "104 700 ₽ (10 user, бессрочно)", "2020", "2",
         "BI без LLM. Дашборды, не диалог."],
        ["9", "Infostart DevTools (комплекс)", "Консоли + инструменты", "Разработчик",
         "Бесплатно", "2015", "1",
         "Без AI. Аналитик пользуется как утилитой."],
        ["10", "GilevTools Monitor", "Мониторинг производительности", "Администратор",
         "Снят с продажи", "2010", "0",
         "Уходит с рынка."],
        ["11", "1С:ИТС Бот-консультант", "AI-помощник бухгалтера", "Бухгалтер 1С",
         "Входит в ИТС", "2024", "2",
         "Для конечного пользователя 1С, не для аналитика."],
        ["12", "AW BI / Centrofinance Monitor", "BI + мониторинг", "Финдиректор",
         "По запросу", "2018", "1",
         "Тонкий сегмент финансового анализа."],
        ["13", "YandexGPT / GigaChat API", "LLM API", "Разработчик",
         "Pay-per-token", "2023", "1",
         "Это инфраструктура (опц. подключим как provider)."],
    ]
    end = fill_data_rows(ws, 5, rus)
    for i in range(5, end):
        apply_priority_color(ws, i, 7, ws.cell(row=i, column=7).value)

    style_section_row(ws, end + 1, 8, "Зарубежные эталоны (для inspiration)")
    style_header_row(ws, end + 2, 8)
    for col, val in enumerate(["#", "Продукт", "Тип", "Целевой пользователь",
                                "Цена", "Год", "Threat", "Что перенять"]):
        ws.cell(row=end + 2, column=col + 1, value=val)

    intl = [
        ["14", "SAP Joule", "AI-ассистент SAP", "SAP-аналитик/менеджер",
         "$8-1 AI Unit/user/мес ($100K-1M/год enterprise)", "2023", "0",
         "Role-based assistants (по ролям, не один на всё). Скиллы 2100+."],
        ["15", "Microsoft Copilot for Dynamics 365", "AI ERP-ассистент", "Финансовый аналитик",
         "$30/user/мес (в M365 Enterprise)", "2023", "0",
         "Bundling в подписку (AI = feature, не отдельный продукт)."],
        ["16", "Salesforce Einstein / Agentforce", "AI CRM-ассистент", "CRM-аналитик",
         "$25+/user/мес", "2018", "0",
         "Agentforce: после ответа → предложить конкретный action."],
        ["17", "ThoughtSpot / Spotter AI", "Agentic Analytics", "Data Analyst",
         "$25/мес → $100K/год", "2012", "0",
         "Natural Language SQL: вопрос → запрос → визуализация."],
        ["18", "Hex Technologies", "Data Workspace", "Data Scientist",
         "$36-75/editor/мес", "2021", "1",
         "Единое workspace: SQL + Python + AI + визуализация в ноутбуке."],
        ["19", "Cursor / GitHub Copilot Workspace", "AI code editor", "Разработчик",
         "$19-40/мес", "2023", "1",
         "Codebase-aware AI. Опытные 1С-разработчики уже используют."],
    ]
    end2 = fill_data_rows(ws, end + 3, intl)
    for i in range(end + 3, end2):
        apply_priority_color(ws, i, 7, ws.cell(row=i, column=7).value)

    style_section_row(ws, end2 + 1, 8, "Сравнительный scorecard (ключевые критерии)")
    style_header_row(ws, end2 + 2, 8)
    for col, val in enumerate(["Критерий", "Мы", "1С:Напарник", "Aether Lab",
                                "TurboConf", "SAP Joule", "Победитель", ""]):
        ws.cell(row=end2 + 2, column=col + 1, value=val)

    fill_data_rows(ws, end2 + 3, [
        ["Целевой = аналитик", "★★★★★", "★★", "★★★", "★★", "★★★★", "Мы", ""],
        ["Multi-tenant", "★★★★★", "★", "★★", "★", "★★★★★", "Мы / SAP", ""],
        ["LLM-чат + контекст 1С", "★★★★★", "★★★★", "★★★", "★★", "★★★★★", "Мы / SAP", ""],
        ["Drill-down данных", "★★★★", "★", "★★★", "★", "★★★★★", "SAP Joule", ""],
        ["Генерация ТЗ", "★★★★★", "★★", "★★", "★★", "★★★", "Мы (план)", ""],
        ["Доступность (цена)", "★★★★★", "★★★★★ free", "★★★★", "★★★★", "★★", "Мы / 1С:Н", ""],
        ["Зрелость", "★★★ (v1.2)", "★★★★", "★★★", "★★★★★", "★★★★★", "TurboConf / SAP", ""],
        ["Расширяемость (MCP)", "★★★★★", "★★", "★★★", "★★", "★★★★", "Мы", ""],
        ["База знаний клиента", "★★★★★", "★★", "★★", "★", "★★★", "Мы", ""],
        ["ИТОГО /50", "43", "26", "27", "20", "42", "Мы лучшие в нише", ""],
    ])

    style_accent_row(ws, end2 + 14, 8,
        "Главный вывод: рынок практически пуст в целевом сегменте. "
        "Окно возможностей до того как 1С:Напарник развернётся на аналитиков — 12-18 месяцев."
    )


def sheet_16_swot_naparnik(wb: Workbook) -> None:
    ws = wb.create_sheet("16_SWOT_1С_Напарник")
    set_col_widths(ws, [4, 18, 60, 14, 38])

    style_title_row(ws, 1, 5, "IV.2 SWOT главного конкурента — 1С:Напарник + план дифференциации")

    style_section_row(ws, 3, 5, "STRENGTHS (что у них сильно)")
    style_header_row(ws, 4, 5)
    for col, val in enumerate(["#", "Сила", "Что это даёт им", "Сила (1-5)", "Что нам делать"]):
        ws.cell(row=4, column=col + 1, value=val)

    strengths = [
        ["S1", "Бренд 1С", "Доверие 600K+ организаций. Воспринимается как 'надёжный отечественный'.", "5",
         "Партнёрство а не борьба: позиционировать как 'дополнение' к Напарнику для аналитиков."],
        ["S2", "ИТС-дистрибуция", "Прямой канал до 200K+ ИТС-партнёров. Включение в стандартную подписку.", "5",
         "Войти в каталог Infostart, рассмотреть партнёрство с франчайзи, оценить ИТС-каталог через год."],
        ["S3", "RAG на метаданных платформы", "Уже обучен на BSL-синтаксисе + типовых объектах. Дорого воспроизвести.", "4",
         "Наш ответ: HBK 82МБ локально + БСП 77МБ + v8std MCP. У нас БОЛЬШЕ открытых данных."],
        ["S4", "Агентный режим в EDT", "Глубокая интеграция на уровне IDE. Контекст всей кодовой базы.", "4",
         "Мы не идём в IDE — мы web/desktop chat. Другой workflow."],
        ["S5", "Бесплатно до окт.2026", "Агрессивный захват рынка разработчиков, формирование привычки.", "4",
         "Наш ответ: Lite-tier бесплатно (5 диалогов/день, 1 база). Никто не превзойдёт 0₽."],
        ["S6", "Доступ к ИТС-документации из чата", "Уникальное преимущество, внешним игрокам закрыто.", "4",
         "Наш ответ: v8std (CC0) + comol/ai_rules + ИТС методичка локально. Близко по охвату."],
    ]
    fill_data_rows(ws, 5, strengths)

    style_section_row(ws, 12, 5, "WEAKNESSES (где они слабы)")
    style_header_row(ws, 13, 5)
    for col, val in enumerate(["#", "Слабость", "Почему это слабость", "Серьёзность", "Как мы атакуем"]):
        ws.cell(row=13, column=col + 1, value=val)

    weaknesses = [
        ["W1", "Только EDT", "Большинство 1С-разработчиков всё ещё на Конфигураторе. Аналитики — без EDT вообще.",
         "5", "Мы — web/desktop, доступны без EDT. Аналитик подключается за 5 минут."],
        ["W2", "Качество 'на уровне джуна'", "Сообщество отмечает: Cursor + Claude дают лучшие результаты на BSL.",
         "4", "Мы используем Claude Sonnet 4.6 / Opus — топовые модели."],
        ["W3", "Только для разработчиков", "Аналитики, консультанты, внедренцы не являются ЦА.",
         "5", "ПОЛНЫЙ gap для нас. Делаем для аналитика, не для разраба."],
        ["W4", "Vendor lock-in", "Нет публичного API. Нельзя встроить в сторонние продукты.",
         "3", "Наш MCP открытый. Можно подключить к Claude Code, Cursor, Zed."],
        ["W5", "EULA-ограничения", "Передача кода типовых конфигураций имеет юридические риски.",
         "3", "У нас anonymize toggle + on-prem опция в roadmap."],
        ["W6", "Нет multi-tenant", "Один разраб = один проект. Не подходит для франчайзи с 20+ клиентами.",
         "5", "Multi-tenant из коробки. Главный наш дифференциатор."],
        ["W7", "Нет автономного режима для аналитика", "'Почему упала выручка в окт?' — не ответит без EDT.",
         "5", "Мы отвечаем на бизнес-вопросы через MCP к боевой базе."],
    ]
    end = fill_data_rows(ws, 14, weaknesses)
    for i in range(14, end):
        apply_priority_color(ws, i, 4, ws.cell(row=i, column=4).value)

    style_section_row(ws, end + 1, 5, "OPPORTUNITIES (что они могут сделать)")
    fill_data_rows(ws, end + 2, [
        ["O1", "Расширение на аналитиков", "Логичный следующий шаг 1С. Если в 2026-2027 — будем прямыми конкурентами.",
         "Высокая (60%)", "Наша подушка — multi-tenant + workflow аналитика + история клиента — это лет 2 разработки."],
        ["O2", "Standalone-версия", "Веб-приложение или desktop вне EDT — расширение аудитории.",
         "Средняя (40%)", "Мы уже там. Опередим на год минимум."],
        ["O3", "Интеграция с ERP через HTTP-сервис", "Аналитика по данным, не только по коду.",
         "Средняя (35%)", "У нас MCP — более широкий протокол. Уже работает."],
        ["O4", "Не-партнёры ИТС после окт.2026", "Расширение платной аудитории.",
         "Высокая (80%)", "Это даже хорошо: рынок осознаёт ценность AI = больший pool для нас."],
    ])

    style_section_row(ws, end + 8, 5, "THREATS для них (что им угрожает)")
    fill_data_rows(ws, end + 9, [
        ["T1", "Cursor + BSL-LSP + mcp-1c", "Опытные разрабы уже собирают этот стек сами. Бесплатно.",
         "Высокая", "Этот стек — конкурент Напарника, не наш. Мы — для аналитика."],
        ["T2", "Claude/GPT улучшаются на открытых данных", "Через год разрыв с 1С-знаниями сократится.",
         "Высокая", "Нам выгодно — общий рост LLM-качества."],
        ["T3", "Конкуренция внутри 1С за бюджет", "Bot-консультант, ИТС, Напарник — конкурируют за ресурсы 1С.",
         "Средняя", "1С может растянуть развитие Напарника. Окно для нас увеличивается."],
    ])

    style_section_row(ws, end + 14, 5, "СТРАТЕГИЯ ДИФФЕРЕНЦИАЦИИ — главное")
    style_accent_row(ws, end + 15, 5,
        "Не конкурировать. Занять параллельную нишу: 'Аналитик' vs 'Разработчик'. "
        "Когда 1С:Напарник пойдёт в аналитика — у нас будут 12-18 мес лидерства + 500+ платных клиентов."
    )


def sheet_17_intl_best_practices(wb: Workbook) -> None:
    ws = wb.create_sheet("17_Best_Practices_Зарубеж")
    set_col_widths(ws, [4, 22, 42, 32, 14])

    style_title_row(ws, 1, 5, "IV.3 Зарубежные best practices — что перенять из SAP/Salesforce/Hex/Cursor")

    style_header_row(ws, 3, 5)
    for col, val in enumerate(["#", "Откуда", "Паттерн / идея", "Как реализовать у нас", "Phase"]):
        ws.cell(row=3, column=col + 1, value=val)

    practices = [
        ["1", "SAP Joule",
         "Role-Based AI Assistants. Не один помощник на всё, а специализированные ассистенты под каждую роль (снабженец, финансист, HR).",
         "Сделать в продукте 'режимы аналитика': Аудит базы / Разбор тикета / Проектирование доработки / Drill-down цифр. У каждого свой system prompt + tool set.",
         "Phase 16"],
        ["2", "SAP Joule",
         "2100+ AI Skills — каталог готовых задач, которые AI умеет выполнять (запросы, проверки, отчёты).",
         "Скилл-каталог в UI: 'Найти неоплаченные ОПП > 30 дней', 'Аудит ролей RLS', 'Проверить движения регистра X'. Скилл = промпт-шаблон + tool sequence.",
         "Phase 17"],
        ["3", "SAP Joule",
         "Deep Research — сложные многодоменные вопросы с синтезом внутренних и внешних данных.",
         "Multi-step research mode: один большой вопрос → AI планирует 5-7 шагов → последовательно вызывает MCP → агрегирует ответ.",
         "Phase 18"],
        ["4", "Salesforce Agentforce",
         "После ответа — предложить конкретный action. Не 'вот данные', а 'хотите создать задачу?'",
         "После каждого ответа AI — 2-3 suggested actions: 'Создать задачу разработчику', 'Экспортировать в Excel', 'Сохранить как кейс'.",
         "Phase 12"],
        ["5", "Salesforce Agentforce",
         "Agent Builder — пользователь сам собирает агентов из готовых блоков (триггер + действия).",
         "В Enterprise tariff — конструктор кастомных recipes: 'каждый понедельник — отчёт по просрочке в Telegram'.",
         "Phase 19"],
        ["6", "Microsoft Copilot",
         "Bundling AI в подписку. AI не отдельный продукт, а feature inside.",
         "Долгосрочно: AI часть базовой подписки. Сейчас — Lite-free + Pro-paid. Через год — все фичи в одном тарифе.",
         "GTM 1 год"],
        ["7", "Microsoft Copilot",
         "Suggested prompts — AI не ждёт вопроса, предлагает что спросить с учётом контекста.",
         "Empty state чата — 3 умных предложения: 'Покажи 10 самых проблемных документов', 'Какие регистры использует ОПП', etc.",
         "Phase 12"],
        ["8", "Hex Technologies",
         "Единое workspace: SQL + Python + AI + визуализация в одном ноутбуке.",
         "У нас уже chat + cards. Расширить: NotebookCard где можно играть с запросами/Python (sandbox) и сохранять как 'recipe'.",
         "Phase 17"],
        ["9", "ThoughtSpot Spotter",
         "Natural Language SQL: вопрос → запрос → визуализация автоматом.",
         "Уже близко через execute_query. Усилить: автоматическая визуализация результата (если >1 строка) через recharts.",
         "Phase 13"],
        ["10", "Cursor",
         "Codebase-aware AI: контекст ВСЕЙ кодовой базы, не одного файла. Хирургические правки с пониманием зависимостей.",
         "У нас MCP + цепочки документов это даёт. Усилить: при выводе кода — авто-показать related объекты (родители, потомки).",
         "Phase 13"],
        ["11", "GitHub Copilot Workspace",
         "Spec mode → plan mode → implement mode. Структурированный flow.",
         "Аналог: Mode toggle в Header. Switch между Q&A / Spec / Implement. Каждый mode = свой system prompt.",
         "Phase 16"],
        ["12", "Sentry AI (Seer)",
         "Не просто 'вот ошибка' — а 'вот объяснение + 3 варианта фикса + кнопка применить'.",
         "Уже в roadmap как ErrorDiagnosisCard (Phase 13).",
         "Phase 13"],
        ["13", "Cody (Sourcegraph)",
         "Context Engine — индексация всей кодовой базы для AI. Поиск по семантике, не только по тексту.",
         "У нас sqlite-vec Phase 10. Добавить индексацию BSL-кода клиента отдельно от сессий.",
         "Phase 11"],
        ["14", "Cursor",
         "Tab autocomplete. Не only chat, ещё и inline предложения.",
         "В наших Monaco-фрагментах кода — inline 'AI suggest'. Кнопка Tab принимает.",
         "Phase 14"],
        ["15", "Notion AI",
         "AI прямо в документе: выделил текст → /ai improve / translate / summarize.",
         "В каждой карточке (TableCard, LogCard) — кнопка 'AI: summarize / explain / chart'.",
         "Phase 17"],
    ]
    fill_data_rows(ws, 4, practices)


def sheet_18_analyst_decomposition(wb: Workbook) -> None:
    ws = wb.create_sheet("18_Декомпозиция_аналитика")
    set_col_widths(ws, [4, 28, 8, 12, 14, 14, 12])

    style_title_row(ws, 1, 7, "V.1 Декомпозиция работы бизнес-аналитика 1С — 44 задачи")
    style_section_row(ws, 3, 7,
        "% времени = из исследований индустрии. AI-feasibility = насколько реально автоматизировать. "
        "Покрытие СЕЙЧАС = после реализации Phases 10-15."
    )
    style_header_row(ws, 4, 7)
    for col, val in enumerate(["#", "Задача", "% времени", "AI-feasibility",
                                "Макс. AI-покрытие %", "Сейчас (P15) %", "Сложность"]):
        ws.cell(row=4, column=col + 1, value=val)

    tasks = [
        # Предпроектное обследование
        ["1", "Первичные встречи с заказчиком", "3.5", "Средняя", "20", "5", "Средняя"],
        ["2", "Сбор требований — интервью", "5.0", "Низкая", "15", "2", "Высокая"],
        ["3", "Изучение AS-IS процессов", "4.0", "Средняя", "35", "5", "Высокая"],
        ["4", "Подготовка коммерческого предложения", "2.5", "Высокая", "70", "0", "Средняя"],
        ["5", "Расчёт трудозатрат на проект", "2.0", "Средняя", "45", "0", "Средняя"],
        # Анализ конфигурации
        ["6", "Идентификация конфигурации (УТ/ЕРП/КА)", "0.5", "Высокая", "90", "60", "Низкая"],
        ["7", "Анализ версии конфигурации/платформы", "0.5", "Высокая", "95", "70", "Низкая"],
        ["8", "Анализ расширений (CFE) и доработок", "2.0", "Высокая", "80", "50", "Средняя"],
        ["9", "Инвентаризация ролей и прав", "1.5", "Высокая", "85", "30", "Средняя"],
        ["10", "Анализ использования регистров/документов", "2.0", "Высокая", "75", "40", "Средняя"],
        ["11", "Аудит качества кода (антипаттерны)", "2.5", "Высокая", "80", "35", "Средняя"],
        ["12", "Анализ производительности, узкие места", "2.0", "Средняя", "55", "25", "Высокая"],
        # Разработка решения
        ["13", "Написание ТЗ / Spec.md", "6.0", "Высокая", "65", "10", "Средняя"],
        ["14", "Дизайн архитектуры решения", "3.5", "Средняя", "40", "10", "Высокая"],
        ["15", "Создание макетов форм и отчётов", "2.5", "Средняя", "50", "0", "Высокая"],
        ["16", "Code review BSL и XML", "3.0", "Высокая", "75", "20", "Средняя"],
        ["17", "Написание тест-кейсов для UAT", "2.0", "Высокая", "70", "5", "Средняя"],
        ["18", "Участие в UAT", "3.0", "Низкая", "10", "2", "Высокая"],
        ["19", "Проверка соответствия ТЗ и реализации", "2.0", "Средняя", "55", "10", "Средняя"],
        # Поддержка production
        ["20", "Разбор инцидентов клиента (1-я линия)", "5.0", "Высокая", "65", "30", "Средняя"],
        ["21", "Анализ журнала регистрации — поиск ошибок", "3.0", "Высокая", "80", "40", "Средняя"],
        ["22", "Drill-down цифр из отчётов руководству", "2.5", "Средняя", "50", "15", "Средняя"],
        ["23", "Объяснение баг-репортов разработчику", "2.5", "Высокая", "70", "15", "Средняя"],
        ["24", "Performance troubleshooting", "2.0", "Средняя", "45", "20", "Высокая"],
        ["25", "Восстановление данных при сбоях", "1.0", "Низкая", "15", "5", "Высокая"],
        ["26", "Мониторинг регламентных заданий", "1.0", "Высокая", "70", "10", "Средняя"],
        # Коммуникация
        ["27", "E-mail переписка с заказчиком", "5.0", "Средняя", "40", "0", "Средняя"],
        ["28", "Telegram/мессенджеры — оперативка", "4.0", "Низкая", "20", "0", "Высокая"],
        ["29", "Встречи-статусы с заказчиком", "4.0", "Низкая", "15", "0", "Высокая"],
        ["30", "Постановка задач разработчику", "3.5", "Высокая", "65", "10", "Средняя"],
        ["31", "Эскалации и согласования с руководством", "2.0", "Низкая", "10", "0", "Высокая"],
        # Документирование
        ["32", "Пользовательские инструкции", "3.0", "Высокая", "80", "5", "Средняя"],
        ["33", "Технические описания модулей", "2.5", "Высокая", "75", "10", "Средняя"],
        ["34", "Протоколы совещаний", "1.5", "Высокая", "85", "0", "Низкая"],
        ["35", "Регламенты бизнес-процессов", "2.0", "Высокая", "70", "0", "Средняя"],
        ["36", "Карточки изменений / Change log", "1.0", "Высокая", "85", "0", "Низкая"],
        # Аудит и оптимизация
        ["37", "Аудит безопасности (роли, RLS)", "2.0", "Высокая", "75", "20", "Средняя"],
        ["38", "Аудит производительности запросов", "2.0", "Высокая", "70", "20", "Средняя"],
        ["39", "Аудит качества данных", "1.5", "Средняя", "50", "10", "Высокая"],
        ["40", "Аудит соответствия методологии 1С/ИТС", "1.5", "Высокая", "80", "40", "Средняя"],
        # Миграции
        ["41", "Анализ различий конфигураций при обновлении", "2.0", "Высокая", "70", "20", "Средняя"],
        ["42", "Разработка плана миграции данных", "1.5", "Средняя", "40", "5", "Высокая"],
        ["43", "Обучение пользователей", "3.0", "Низкая", "15", "0", "Высокая"],
        ["44", "Онбординг нового аналитика на проект", "1.5", "Высокая", "75", "5", "Средняя"],
    ]
    end = fill_data_rows(ws, 5, tasks)
    for i in range(5, end):
        apply_priority_color(ws, i, 4, ws.cell(row=i, column=4).value)

    # Итоги по разделам
    style_section_row(ws, end + 1, 7, "Расчёт покрытия (взвешенное среднее: %времени × %покрытия / 100)")
    fill_data_rows(ws, end + 2, [
        ["", "ТЕКУЩЕЕ покрытие (Phases 10-15)", "", "", "~22-26%", "Сумма столбца (T × Now / 100)", ""],
        ["", "ПОТЕНЦИАЛ AI (теоретический максимум)", "", "", "~55-60%", "Сумма столбца (T × Max / 100)", ""],
        ["", "GAP для закрытия (что мы НЕ покрываем сейчас)", "", "", "~32%", "Это работа Phases 16-20", ""],
        ["", "ПОТОЛОК что AI не может никогда", "", "", "~40%", "Коммуникация + UAT + решения", ""],
    ])

    style_accent_row(ws, end + 7, 7,
        "Главные выводы: (1) 60% покрытие достижимо к Q2-Q3 2027 при реализации Phases 16-20. "
        "(2) 80% покрытие НЕДОСТИЖИМО в 2026-2027 — это физический потолок. "
        "(3) Топ-3 для быстрого ROI: ТЗ-генератор (6% времени), Инструкции (3%), Инциденты (5%)."
    )


def sheet_19_phase_16_20(wb: Workbook) -> None:
    ws = wb.create_sheet("19_Путь_к_60_проц")
    set_col_widths(ws, [4, 12, 28, 42, 14, 14, 18])

    style_title_row(ws, 1, 7, "V.2 Путь к 60%+ покрытия — Phases 16-20")

    style_section_row(ws, 3, 7, "Что добавить к существующему roadmap (Phases 10-15)")
    style_header_row(ws, 4, 7)
    for col, val in enumerate(["#", "Phase", "Модуль", "Описание", "+ к покрытию",
                                "Срок", "Сложность"]):
        ws.cell(row=4, column=col + 1, value=val)

    phases = [
        # Phase 16 — Документогенерация
        ["1", "P16", "ТЗ-генератор",
         "Из контекста чата (требования собраны → нажать → черновик ТЗ в ГОСТ-формате). Шаблоны под типы (отчёт, обработка, расширение). Экспорт в .docx.",
         "+3.9%", "3-4 нед", "Средняя"],
        ["2", "P16", "Генератор пользовательских инструкций",
         "По описанию функционала → инструкция для кладовщика/бухгалтера/менеджера. Без скриншотов — 85% качество.",
         "+2.4%", "1-2 нед", "Низкая"],
        ["3", "P16", "Генератор протоколов совещаний",
         "Bullet-points обсуждения → форматированный протокол с решениями и ответственными. Экспорт в Confluence/Word.",
         "+1.3%", "1 нед", "Низкая"],
        ["4", "P16", "Карточки изменений / Change log",
         "Из git commit + ТЗ → changelog для клиента (понятным языком, не для разработчика).",
         "+0.8%", "1 нед", "Низкая"],
        ["5", "P16", "Role-based modes",
         "Toggle режимов: Аудит / Разбор тикета / Проектирование / Drill-down. У каждого свой system prompt + tool set.",
         "+1.5%", "2 нед", "Средняя"],
        # Phase 17 — Code Review Engine
        ["6", "P17", "BSL-аудитор",
         "Загрузил файл/вставил код → отчёт по A1-A11 антипаттернам, стандартам ИТС, метрикам (вложенность, запросы в цикле).",
         "+1.7%", "3-4 нед", "Средняя"],
        ["7", "P17", "Query Analyzer",
         "Вставил запрос → анализ: виртуальные таблицы, ПЕРВЫЕ N, фильтры в ГДЕ вместо параметров. Предложения оптимизации.",
         "+0.9%", "2-3 нед", "Средняя"],
        ["8", "P17", "ИТС compliance checker",
         "'Это решение соответствует методологии ИТС?' Сравнение с базой стандартов.",
         "+1.2%", "2 нед", "Средняя"],
        ["9", "P17", "Skill Catalog (как SAP Joule)",
         "Каталог 50+ готовых задач: 'Аудит ролей RLS', 'Поиск неоплаченных ОПП >30 дней'. Каждый = промпт+tool sequence.",
         "+1.5%", "3-4 нед", "Средняя"],
        # Phase 18 — Task Decomposition
        ["10", "P18", "Постановщик задач разработчику",
         "Неформальное 'нужен отчёт по остаткам' → AI расписывает: регистры, поля, СКД, фильтры, ТЧ.",
         "+2.3%", "3-4 нед", "Средняя"],
        ["11", "P18", "Тест-кейс генератор",
         "Из описания функционала → список тест-кейсов с шагами для UAT.",
         "+1.4%", "2 нед", "Низкая"],
        ["12", "P18", "Трудозатратный калькулятор",
         "По аналогии с историей задач (self-learning) предсказывает оценку трудозатрат.",
         "+0.9%", "2-3 нед", "Высокая"],
        ["13", "P18", "Suggested Actions (Agentforce-style)",
         "После каждого ответа AI — 2-3 действия: 'Создать задачу', 'Экспортировать в Excel', 'Сохранить как кейс'.",
         "+1.5%", "2 нед", "Средняя"],
        # Phase 19 — Incident Intelligence
        ["14", "P19", "Структуратор инцидентов",
         "Клиент пишет 'ничего не работает' → AI задаёт уточняющие вопросы → структурированная карточка.",
         "+1.0%", "2-3 нед", "Средняя"],
        ["15", "P19", "Предиктивный мониторинг",
         "Анализирует паттерны ошибок и предупреждает: 'в пятницу падает регламентное задание X'.",
         "+0.5%", "4-6 нед", "Высокая"],
        ["16", "P19", "База решений инцидентов (поверх case repo)",
         "Каждый решённый инцидент → база с поиском. Bonus к self-learning Phase 14.",
         "+1.5%", "3 нед", "Средняя"],
        # Phase 20 — Voice & Meeting
        ["17", "P20", "Voice-to-requirements",
         "Запись встречи → транскрипт (Whisper / Yandex SpeechKit) → структурированные требования → черновик ТЗ.",
         "+1.5%", "8-12 нед", "Очень высокая"],
        ["18", "P20", "Pre-meeting briefing",
         "Перед звонком клиенту: сводка по проекту, открытые вопросы, последние инциденты.",
         "+0.6%", "1-2 нед", "Низкая"],
        ["19", "P20", "Post-meeting follow-up",
         "Из протокола встречи → автоматическая постановка задач + e-mail клиенту с резюме.",
         "+0.5%", "2 нед", "Средняя"],
    ]
    end = fill_data_rows(ws, 5, phases)

    # Итог
    total_pct = sum(float(r[4].strip("+%")) for r in phases)
    style_section_row(ws, end + 1, 7, f"Суммарный вклад Phases 16-20: +{total_pct:.1f}% к текущему ~24%")
    fill_data_rows(ws, end + 2, [
        ["", "После Phase 15 (текущий roadmap)", "", "~24%", "", "", ""],
        ["", "После Phase 16 (документогенерация)", "", "~34%", "", "", ""],
        ["", "После Phase 17 (code review)", "", "~39%", "", "", ""],
        ["", "После Phase 18 (task decomposition)", "", "~45%", "", "", ""],
        ["", "После Phase 19 (incident intelligence)", "", "~48%", "", "", ""],
        ["", "После Phase 20 (voice + meeting)", "", "~51%", "", "", ""],
        ["", "Реалистичный потолок (с qualitative AI gains)", "", "~55-58%", "", "", ""],
    ])

    style_section_row(ws, end + 10, 7, "Что AI НЕ покроет НИКОГДА (~40% работы)")
    fill_data_rows(ws, end + 11, [
        ["", "Политика внутри клиента", "Кто против проекта и почему — невидимая динамика", "0%", "", "", ""],
        ["", "Финальные архитектурные решения", "Ответственность лежит на человеке", "0%", "", "", ""],
        ["", "UAT в production с реальными данными", "Юридически и практически нельзя автоматизировать", "0%", "", "", ""],
        ["", "Работа с ПД клиентов в облачном AI", "152-ФЗ + GDPR", "0%", "", "", ""],
        ["", "Устные договорённости 'на берегу'", "Доверие и репутация — не транскрибируемы", "0%", "", "", ""],
        ["", "Обучение сопротивляющихся пользователей", "Психология + мотивация — не AI", "0%", "", "", ""],
    ])

    style_accent_row(ws, end + 18, 7,
        "ЦЕЛЬ 60% ДОСТИЖИМА. Самые ценные первыми (highest ROI): "
        "ТЗ-генератор (P16) → инструкции (P16) → BSL-аудитор (P17) → постановщик задач (P18). "
        "За 3-4 месяца — +15% к покрытию."
    )


def sheet_20_pricing_gtm(wb: Workbook) -> None:
    ws = wb.create_sheet("20_Pricing_GTM")
    set_col_widths(ws, [4, 28, 28, 28, 28])

    style_title_row(ws, 1, 5, "VI.1 Pricing модели + Go-to-Market roadmap")

    style_section_row(ws, 3, 5, "Модель 1: Workspace SaaS (per-company) — для Стратегии Франчайзи")
    style_header_row(ws, 4, 5)
    for col, val in enumerate(["Тариф", "Цена", "Что входит", "Лимиты", "Для кого"]):
        ws.cell(row=4, column=col + 1, value=val)

    fill_data_rows(ws, 5, [
        ["СТАРТ", "₽9 900/мес", "Multi-tenant, чат, цепочки, ИТС", "3 базы, 1 аналитик, 2M токенов", "Малый франчайзи"],
        ["КОМАНДА", "₽24 900/мес", "+ ТЗ-генератор, code review", "10 баз, 3 аналитика, 8M токенов", "Средний франчайзи"],
        ["АГЕНТСТВО", "₽49 900/мес", "+ skill catalog, voice, dashboard", "30 баз, 10 аналитиков, 25M токенов", "Крупный франчайзи 50+"],
        ["Enterprise", "договорная", "On-premise, SLA, кастом", "Неограниченно", "Корпорации, гос"],
    ])

    style_section_row(ws, 10, 5, "Модель 2: Per-Seat SaaS — для Стратегии Senior-аналитика ★ РЕКОМЕНДОВАНА")
    style_header_row(ws, 11, 5)
    for col, val in enumerate(["Тариф", "Цена", "Что входит", "Лимиты", "Для кого"]):
        ws.cell(row=11, column=col + 1, value=val)

    fill_data_rows(ws, 12, [
        ["Lite (FREE)", "₽0", "Чат + 1 база + базовые карточки", "5 диалогов/день, 1 база", "Любой попробовать"],
        ["Pro", "₽5 900/аналитик/мес", "+ multi-tenant + ТЗ-генератор + SQL", "5 баз, безлимит диалогов", "Активный аналитик"],
        ["Expert", "₽12 900/аналитик/мес", "+ Claude Opus + skill catalog + API", "20 баз, приоритет", "Senior, лидер команды"],
    ])

    style_section_row(ws, 17, 5, "Модель 3: Hybrid (Desktop license + AI credits)")
    style_header_row(ws, 18, 5)
    for col, val in enumerate(["Элемент", "Цена", "Что даёт", "Когда выбрать", ""]):
        ws.cell(row=18, column=col + 1, value=val)

    fill_data_rows(ws, 19, [
        ["Desktop лицензия", "₽14 900 бессрочно", "Electron приложение + локальные данные", "Боязнь подписок", ""],
        ["Поддержка", "₽6 900/год", "Обновления, тех. поддержка", "Долгосрочное использование", ""],
        ["AI Мини", "₽2 900/мес", "3M токенов", "Лёгкое использование", ""],
        ["AI Стандарт", "₽6 900/мес", "10M токенов", "Активное использование", ""],
        ["AI Макс", "₽14 900/мес", "30M токенов + on-prem LLM опция", "Энтерпрайз, безопасность", ""],
    ])

    style_section_row(ws, 26, 5, "Go-to-Market: 90 дней — захват охотников за новым")
    style_header_row(ws, 27, 5)
    for col, val in enumerate(["#", "Действие", "Канал", "Цель", "Метрика"]):
        ws.cell(row=27, column=col + 1, value=val)

    fill_data_rows(ws, 28, [
        ["1", "Статья на Infostart 'AI-аналитик для 1С'", "Infostart", "Awareness в core-аудитории", "1000+ просмотров"],
        ["2", "Видео YouTube: 'Разбор тикета за 10 минут'", "YouTube + Telegram", "Демонстрация ценности", "500+ просмотров"],
        ["3", "Прямые продажи 20 франчайзи (hh.ru по вакансиям)", "Email + LinkedIn", "Первые платные клиенты", "3-5 контрактов"],
        ["4", "5-10 постов в Telegram-каналах про 1С", "Telegram (Mista, Infostart)", "Trial signups", "200+ Lite пользователей"],
        ["5", "Freemium Lite tier — снижение барьера до нуля", "Сайт + onboarding", "Word-of-mouth", "Conversion 5-10%"],
    ])

    style_section_row(ws, 34, 5, "Go-to-Market: 6 месяцев — канальная стратегия")
    fill_data_rows(ws, 35, [
        ["1", "Партнёрская программа для франчайзи", "Direct sales", "Channel partners", "3-5 партнёров"],
        ["2", "Выступление на Infostart Event 2026", "Event", "Industry awareness", "Booth + сессия"],
        ["3", "Интеграция с Jira/Bitrix24 как '1С контекст'", "Integration", "Workflow позиционирование", "Pilot 2-3 клиента"],
        ["4", "PR на Habr / vc.ru / CNews", "PR", "Brand awareness", "5+ статей"],
        ["5", "SEO под 'инструменты аналитика 1С'", "Organic", "Inbound лиды", "500+ visits/мес"],
    ])

    style_section_row(ws, 41, 5, "Go-to-Market: 1 год — масштабирование")
    fill_data_rows(ws, 42, [
        ["1", "Enterprise тарифы для крупных франчайзи 50+", "Direct sales", "Большие чеки", "5-10 enterprise"],
        ["2", "On-premise опция для гос/ОПК", "Direct", "Закрытые контуры", "2-3 контракта/год"],
        ["3", "1С:ИТС каталог (через партнёрство)", "1C channel", "Massive distribution", "TBD"],
        ["4", "Расширение на СНГ (Казахстан, Беларусь)", "Regional", "Geographic expansion", "100+ accounts"],
        ["5", "MRR target", "Все каналы", "₽2-4M MRR", "400-600 paid"],
    ])

    style_section_row(ws, 48, 5, "Финансовая прогноз (12 месяцев)")
    style_header_row(ws, 49, 5)
    for col, val in enumerate(["Период", "Free users", "Paid users", "MRR", "Кумулятивная выручка"]):
        ws.cell(row=49, column=col + 1, value=val)

    fill_data_rows(ws, 50, [
        ["Месяц 1", "50", "0", "₽0", "₽0"],
        ["Месяц 3", "200", "20", "₽120K", "₽180K"],
        ["Месяц 6", "1000", "120", "₽700K", "₽2.5M"],
        ["Месяц 9", "2500", "280", "₽1.7M", "₽7M"],
        ["Месяц 12", "5000", "500", "₽3M", "₽15M"],
    ])

    style_accent_row(ws, 56, 5,
        "Рекомендация: старт с Модели 2 (per-seat, Lite=free). "
        "Через 3 месяца — добавить Модель 1 (workspace) для франчайзи. "
        "Модель 3 (Hybrid) — на запрос enterprise."
    )


def sheet_21_ethics(wb: Workbook) -> None:
    ws = wb.create_sheet("21_Этика_правовые_границы")
    set_col_widths(ws, [4, 28, 42, 32])

    style_title_row(ws, 1, 4, "VII. Этика и правовые границы AI-аналитика")

    style_section_row(ws, 3, 4, "Где AI НЕ должен принимать решения (абсолютные ограничения)")
    style_header_row(ws, 4, 4)
    for col, val in enumerate(["#", "Зона", "Почему", "Что вместо"]):
        ws.cell(row=4, column=col + 1, value=val)

    fill_data_rows(ws, 5, [
        ["1", "Деструктивные операции (DELETE, миграция)",
         "Необратимые последствия. Юридическая ответственность.",
         "Обязательный confirm dialog. Snapshot перед операцией. Логирование."],
        ["2", "Финальные архитектурные решения",
         "AI может предложить 3 варианта, но выбрать — человек (несёт ответственность).",
         "AI выводит 'предлагаю N вариантов', человек явно выбирает."],
        ["3", "Решения о правах/ролях/RLS",
         "Безопасность данных. Ошибка = data breach.",
         "Только аудит + предложения. Финальное решение — security officer."],
        ["4", "Production обязательства перед клиентом",
         "Юридические сроки и SLA — нельзя обещать от имени компании.",
         "AI redirect к PM/руководителю проекта."],
        ["5", "Передача кода типовой конфигурации в облачный LLM",
         "EULA 1С: типовой код защищён.",
         "Только кастомные расширения. Anonymize toggle. On-prem опция."],
        ["6", "Согласование коммерческих условий с клиентом",
         "Договорные обязательства = живой переговорный процесс.",
         "AI готовит черновик, человек подписывает."],
    ])

    style_section_row(ws, 12, 4, "Escalation rules — когда AI обязан передать человеку")
    style_header_row(ws, 13, 4)
    for col, val in enumerate(["#", "Триггер", "Действие AI", "UI поведение"]):
        ws.cell(row=13, column=col + 1, value=val)

    fill_data_rows(ws, 14, [
        ["1", "Уверенность ответа < 60%",
         "Префикс 'Эта тема требует проверки эксперта'",
         "Badge 'Low confidence' + кнопка 'Спросить старшего'"],
        ["2", "Деструктивная операция",
         "Confirm dialog с явным WARNING и описанием последствий",
         "Modal с детальным diff + двойным подтверждением"],
        ["3", "Вопрос о правах/ролях",
         "'Безопасность — решение человека'",
         "Disclaimer + ссылка на security officer"],
        ["4", "Вопрос о сроках/обязательствах перед клиентом",
         "Redirect к PM",
         "Карточка 'Эскалировать PM'"],
        ["5", "Код типовой конфигурации в запросе",
         "Disclaimer о лицензии 1С",
         "Modal: 'Использовать только для кастомных расширений?'"],
        ["6", "Конфиденциальные данные обнаружены (PII)",
         "Заблокировать отправку в облако",
         "Toast + кнопка 'Анонимизировать и отправить'"],
        ["7", "Финансовые цифры > порога (например, > 1M ₽)",
         "Confirm: 'Подтвердите что верно интерпретируете'",
         "Tooltip с источником цифры"],
    ])

    style_section_row(ws, 22, 4, "Соответствие 152-ФЗ / GDPR — обязательные меры")
    fill_data_rows(ws, 23, [
        ["1", "PII-детектор на входе",
         "Regex для ИНН (\\b\\d{10,12}\\b), КПП (\\b\\d{9}\\b), СНИЛС, ОГРН, паспорт, e-mail",
         "Блокировка отправки в облачный LLM до подтверждения"],
        ["2", "Terms of Service с явным указанием",
         "'Не вставляйте персональные данные клиентов'",
         "Onboarding step + checkbox согласия"],
        ["3", "Логирование всех AI-рекомендаций",
         "Timestamp + user + prompt + response → для аудита",
         "SQLite таблица ai_audit_log с retention 2 года"],
        ["4", "On-premise опция (локальный LLM)",
         "Для enterprise с закрытыми контурами — Ollama/LocalAI",
         "Phase 14+: Enterprise tier"],
        ["5", "Anonymization toggle (уже в Phase 11)",
         "Замена реальных имён/ИНН/сумм на токены перед embed",
         "Header toggle с amber pill индикатором"],
        ["6", "Right to erasure",
         "DELETE cascade по channel_id (уже есть)",
         "Settings → 'Удалить все данные клиента X'"],
        ["7", "Шифрование at rest",
         "AES-256 для cases.json + sessions. Или SQLCipher для всей БД.",
         "Минимум: OS-level (BitLocker)"],
    ])

    style_section_row(ws, 31, 4, "Лицензия 1С — серая зона")
    fill_data_rows(ws, 32, [
        ["1", "Локальная индексация HBK файлов",
         "Серая зона — формально EULA содержит ограничения, но для внутреннего инструмента — нормально (прецедент onec-help-mcp MIT).",
         "НЕ включать .hbk в дистрибутив, индексация только из локальной 1С"],
        ["2", "Передача BSL-кода в облачный LLM",
         "Если код типовой — серая зона. Если расширение — норма (это код клиента).",
         "Toggle + предупреждение для пользователя"],
        ["3", "1С:Напарник EULA",
         "Запрещает коммерческое использование в сторонних продуктах.",
         "НЕ интегрировать. Использовать свой стек (Claude, GPT, NIM)"],
        ["4", "Декомпиляция защищённого кода через AI",
         "Запрещено лицензией 1С.",
         "Не делать вообще. Блокировать в UI."],
    ])

    style_accent_row(ws, 37, 4,
        "Принцип: 'Augmentation, not replacement'. AI — помощник аналитика, не его замена. "
        "Финальная ответственность всегда на человеке. Disclaimer на каждом критичном действии."
    )
    style_accent_row(ws, 38, 4,
        "В UI должен быть везде явный indicator: 'AI-рекомендация требует проверки экспертом'."
    )


# ──────────────────────────────── MAIN ──────────────────────────────────
def main() -> None:
    wb = Workbook()
    # Удаляем дефолтный
    wb.remove(wb.active)

    sheet_00_summary(wb)
    sheet_01_its_sources(wb)
    sheet_02_its_approaches(wb)
    sheet_03_its_legal(wb)
    sheet_04_chains_mcp_ops(wb)
    sheet_05_chains_ui_cards(wb)
    sheet_06_chains_approaches(wb)
    sheet_07_learning_layers(wb)
    sheet_08_learning_pipeline(wb)
    sheet_09_roadmap(wb)
    sheet_10_budget(wb)
    sheet_11_risks(wb)
    sheet_12_metrics(wb)
    sheet_13_anti(wb)
    sheet_14_vision(wb)
    # ── Вторая итерация: конкурентный анализ + декомпозиция аналитика ──
    sheet_15_competitors(wb)
    sheet_16_swot_naparnik(wb)
    sheet_17_intl_best_practices(wb)
    sheet_18_analyst_decomposition(wb)
    sheet_19_phase_16_20(wb)
    sheet_20_pricing_gtm(wb)
    sheet_21_ethics(wb)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT_PATH)
    print(f"OK: {OUTPUT_PATH}")
    print(f"   {OUTPUT_PATH.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
