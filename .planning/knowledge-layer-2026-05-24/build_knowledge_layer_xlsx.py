# -*- coding: utf-8 -*-
"""Knowledge Layer для 1С Аналитик — план развития на 8 листов."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = (
    r"C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
    r"knowledge-layer-2026-05-24/Knowledge_Layer_1С_Аналитик_2026-05-24.xlsx"
)

# ============================================================
# СТИЛЬ
# ============================================================
SEV = {
    "P0": ("FFB91C1C", "FFFFFFFF"),  # red
    "P1": ("FFEA580C", "FFFFFFFF"),  # orange
    "P2": ("FFCA8A04", "FFFFFFFF"),  # amber
    "P3": ("FF374151", "FFFFFFFF"),  # slate
    "—":  ("FF6B7280", "FFFFFFFF"),
}

LEVEL_COLOR = {
    "L0 Lexical":    "FF7C3AED",  # purple-600 — что есть сейчас (MCP live)
    "L1 Structural": "FF2563EB",  # blue-600
    "L2 Relational": "FF0891B2",  # cyan-600
    "L3 Semantic":   "FF059669",  # emerald-600
    "L4 Behavioral": "FFD97706",  # amber-600
    "L5 Normative":  "FFDC2626",  # red-600
    "L6 Predictive": "FF7C2D12",  # brown-800
    "Cross-cutting": "FF4B5563",  # gray-600
    "Pipeline":      "FF1F2937",  # gray-900
    "UX":            "FFFF6A3D",  # Signal brand
    "Pricing/GTM":   "FF111827",
}

HEADER_FILL = PatternFill("solid", start_color="FF111827")
HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFFFF", size=11)
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
THIN = Side(border_style="thin", color="FF374151")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
DATA_FONT = Font(name="Arial", size=10)
DATA_FONT_BOLD = Font(name="Arial", bold=True, size=10)
ALIGN_WRAP = Alignment(vertical="top", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
COMMENT_FILL = PatternFill("solid", start_color="FFFEF3C7")  # yellow

# ============================================================
# Лист 1 — FINDINGS (главный реестр)
# id | level | type | prio | subject | desc | maturity | ready_now (готовое) |
# need_build (что строить) | deps | effort | days | quarter |
# business_impact | source | comment
# ============================================================
FINDINGS = [
    # ============================================================
    # L1 — STRUCTURAL (знаем имена, структуру, типы)
    # ============================================================
    ("L1-1", "L1 Structural", "Component", "P0",
     "Metadata Cache — заполнение готовой таблицы",
     "В backend/app/storage/migrations.py V5 уже создана таблица metadata_cache(channel_id, object_path, object_type, name, presentation). Сейчас НЕ заполняется. Нужен service-layer вокруг MCP get_metadata: при первом обращении к каналу — fetch tree + write cache. Дальше — incremental refresh через event_log webhook (когда меняется конфигурация) или manual via UI.",
     "Lexical/Structural",
     "metadata_cache схема — backend/app/storage/migrations.py:V5",
     "MetadataCacheService (~150 строк): crawl + diff + persist; integration в connections.py POST + manual refresh endpoint /channels/{id}/metadata/refresh",
     "—",
     "S", 0.5, "M-K1",
     "Снимает один MCP вызов per chat (сейчас get_metadata каждый раз). Latency -50ms, MCP load -30%.",
     "inventory (general-purpose)", ""),

    ("L1-2", "L1 Structural", "Component", "P0",
     "Object Dossier — full inspection одной командой",
     "Композит из MCP вызовов: get_object_structure + get_form_handlers + get_event_subscriptions + кеш в metadata_cache. Возвращает 'паспорт' объекта: реквизиты + типы + табл.части + измерения регистров + формы + подписки. Аналог Sourcegraph 'symbol dossier'.",
     "Structural",
     "MCP get_object_structure (mcp-1c-readonly v1.6.9), get_form_handlers, get_event_subscriptions",
     "Backend orchestrator/dossier.py — fetcher + cache + serializer; новый MCP-aware aux tool 'inspect_object' который LLM сам вызывает в одно действие",
     "L1-1",
     "M", 2, "M-K1",
     "LLM получает полный контекст об объекте в 1 вызове вместо 5. UC-1/3/4/8.",
     "deep-researcher (Code Index pattern)", ""),

    ("L1-3", "L1 Structural", "Use Case", "P0",
     "UC: 'Расскажи про этот документ всё'",
     "Пользователь: '@Документ.ОПП — что это?'. Система: достаёт dossier + находит cross-references (где используется) + список движений → Object Card + References Card + Movement Card.",
     "Structural",
     "ObjectCard (cards.py), L1-2 dossier, ReferencesCard",
     "Готовый prompt-template + UI композиция 3 карточек как 'дайджест'",
     "L1-1, L1-2",
     "S", 0.5, "M-K1",
     "Killer UX. Аналитик за 5 секунд получает то что в EDT находит за 5 минут.",
     "claude synthesis", ""),

    ("L1-4", "L1 Structural", "Component", "P1",
     "Configuration Fingerprint",
     "Хеш всей структуры конфигурации: count объектов, ключевые имена, версия БСП, версия типовой. Хранится в SQLite. Меняется хеш → background refresh metadata_cache. Используется для invalidation cache.",
     "Structural",
     "—",
     "ConfigurationFingerprintService — Python модуль 80 строк; CRON job на startup + раз в час",
     "L1-1",
     "S", 0.5, "M-K1",
     "Точка инвалидации кеша. Без неё кеш протухает молча.",
     "claude synthesis", ""),

    ("L1-5", "L1 Structural", "Component", "P2",
     "Configuration Type Detection",
     "Авто-определение что за конфигурация: УТ 11.5 / ERP 2.5 / БП 3.0 / УСО 2.5 / БГУ / ЗУП / кастом. По fingerprint метаданных (присутствие ключевых документов и регистров). Открывает специализированные knowledge bundles (см. L4-3).",
     "Structural",
     "Готовые сигнатуры типовых (memory: 1c-business-processes-data-structures-2026-05-24)",
     "ConfigTypeDetector (~100 строк): сравнение fingerprint с справочником типовых",
     "L1-4",
     "S", 0.5, "M-K2",
     "Условие активации L4 типовых knowledge bundles.",
     "claude synthesis", ""),

    # ============================================================
    # L2 — RELATIONAL (графы, связи, callgraph)
    # ============================================================
    ("L2-1", "L2 Relational", "Component", "P0",
     "Knowledge Graph (SQLite + recursive CTE)",
     "Embedded граф в том же SQLite (без Neo4j/Kuzu — Apple купила Kuzu в 10.2025, риск). Таблицы: nodes(id, type, name, props_json), edges(from_id, to_id, edge_type, weight). 6 типов edges: WRITES_TO (документ→регистр), READS_FROM (отчёт→регистр), CALLS (метод→метод), SUBSCRIBES_TO (подписка→объект), RESTRICTS_BY (RLS), COMPUTES_FROM (СКД ресурс→поле).",
     "Relational",
     "SQLite уже в стеке (aiosqlite), Code Index доказал паттерн (find_path через recursive CTE)",
     "Backend graph/ module — nodes/edges schema migration, builder pipeline (TreeSitter+mdclasses), query helpers, GraphQL-style API",
     "L1-1, L1-2",
     "L", 5, "M-K2",
     "Фундамент для всех L2+ use cases. Все 'покажи цепочку' / 'где используется' базируются на этом.",
     "deep-researcher (Sourcegraph + Code Index)", ""),

    ("L2-2", "L2 Relational", "Component", "P0",
     "BSL Parser (TreeSitter integration)",
     "Tree-sitter грамматика BSL существует (используется в Code Index). Парсит BSL incrementally — изменился файл, перепарсивается только subtree. Извлекает: процедуры/функции, экспорты, вызовы, директивы (&НаСервере), переменные. Основа для callgraph + dataflow.",
     "Relational",
     "tree-sitter-bsl грамматика (в Code Index), Python tree_sitter binding",
     "Backend orchestrator/bsl_ast.py: TS-parser wrapper, symbol extraction, инкрементальный rebuild по mtime",
     "—",
     "M", 2, "M-K2",
     "Без AST невозможны UC-4 (impact analysis), UC-5 (line-by-line explain), UC-7 (дубли), UC-12 (server calls counter).",
     "deep-researcher", ""),

    ("L2-3", "L2 Relational", "Component", "P1",
     "Call Graph Builder",
     "Из AST → edges типа CALLS в knowledge graph. Учитывает: общие модули, модули объектов, методы менеджеров, формы. Поддерживает direction=callers (кто меня вызывает) и callees (кого я вызываю). Глубина настраиваема.",
     "Relational",
     "L2-1 graph, L2-2 parser; MCP get_method_call_hierarchy (mcp-1c) — first iteration уже работает",
     "CallGraphBuilder: AST walker + edge writer; query API direction+depth",
     "L2-1, L2-2",
     "M", 2, "M-K2",
     "UC-4, UC-11, UC-16. 'что сломается / где используется' — fundamental analyst question.",
     "deep-researcher", ""),

    ("L2-4", "L2 Relational", "Component", "P1",
     "Data Flow Lineage (документ → регистр → отчёт)",
     "Парсим ОбработкаПроведения → детектим Движения.X.Добавить → edges WRITES_TO. Парсим СКД-схемы отчётов → детектим источники → edges READS_FROM. Получаем полную data lineage аналогично OpenMetadata/DataHub но для 1С.",
     "Relational",
     "L2-1 graph, L2-2 parser, mdclasses (tools/mdclasses — Java, но можно вызвать через Java MCP)",
     "DataFlowBuilder: ОбработкаПроведения scanner + СКД xml parser + edges writer",
     "L2-1, L2-2",
     "L", 5, "M-K3",
     "UC-2 (почему отчёт пустой), UC-3 (цепочка проведения), UC-8 (граф использования регистра).",
     "deep-researcher (data lineage)", ""),

    ("L2-5", "L2 Relational", "Use Case", "P0",
     "UC: 'Покажи цепочку проведения документа Х'",
     "Пользователь спрашивает. Система: WRITES_TO edges от документа → все регистры → SUBSCRIBES_TO подписки → визуализирует Mermaid/React Flow. Граф с подписями типа ('+ кол-во', '- сумма').",
     "Relational",
     "L2-1, L2-4",
     "GraphCard frontend (новый card type, React Flow или Mermaid via mermaid.js)",
     "L2-1, L2-4, UX-1",
     "M", 2, "M-K3",
     "Killer demo. 'Вижу как документ влияет' — то что делается часами в Конфигураторе.",
     "deep-researcher (UC-3)", ""),

    ("L2-6", "L2 Relational", "Use Case", "P0",
     "UC: 'Что сломается если переименую реквизит X?'",
     "Impact analysis: traversal по graph от node реквизита → все referencing nodes (запросы, BSL код, СКД, Form.xml, RLS). Возвращает список с file:line + severity ('critical: блок проведения', 'medium: отчёт может показать ошибку').",
     "Relational",
     "L2-1, L2-2, L2-3",
     "ImpactAnalysisService: graph traversal + severity classifier (rules)",
     "L2-1, L2-2, L2-3",
     "M", 2, "M-K3",
     "Снимает страх рефакторинга. Часовая работа в одну команду.",
     "deep-researcher (UC-4)", ""),

    ("L2-7", "L2 Relational", "Use Case", "P1",
     "UC: 'Trace от UI-кнопки до записи в регистр'",
     "Полный execution trace без запуска базы. Form.xml → handler команды → BSL цепочка вызовов → server методы → запросы → движения. Визуализация sequence-diagram.",
     "Relational + Behavioral",
     "L2-1, L2-3, L2-4",
     "ExecutionTracer: pipeline через graph; Mermaid sequence-diagram",
     "L2-3, L2-4",
     "L", 5, "M-K3",
     "UC-11, UC-12. 'Как работает эта кнопка' за 10 сек.",
     "deep-researcher (UC-11)", ""),

    # ============================================================
    # L3 — SEMANTIC (embeddings, vector search, дубли, объяснения)
    # ============================================================
    ("L3-1", "L3 Semantic", "Component", "P0",
     "Vector Store (LanceDB embedded)",
     "Local embedded vector DB. LanceDB рекомендован — disk-mapped, SIMD, интегрирован в Continue.dev (доказано). Альтернатива — sqlite-vec (ещё проще, всё в SQLite). Для AWD: один файл .knowledge/vectors.lance/ или vectors.sqlite-vec.",
     "Semantic",
     "Phase 10 (Learn Engine) уже спроектирована, не реализована (см. ROADMAP)",
     "Migration v11 + embeddings_store.py (CRUD + similarity search) + integration в orchestrator",
     "—",
     "M", 2, "M-K2",
     "Активация всех semantic use cases. Без vector store невозможен поиск 'найди похожий код'.",
     "deep-researcher (LanceDB/Continue)", ""),

    ("L3-2", "L3 Semantic", "Component", "P0",
     "Embedding Pipeline (BGE-M3 multilingual)",
     "BAAI/bge-m3 — 100+ языков, 8192 контекст, dense+sparse+colbert одновременно. Идеален для 1С (русский код + русская документация). Локальный inference через Ollama или text-embeddings-inference (HF). ~570 MB модель. Cost: $0 (local).",
     "Semantic",
     "Ollama (если установлен) или HF text-embeddings-inference Docker",
     "EmbeddingService (Python): bge-m3 через HTTP к Ollama / TEI; batch indexer; chunking strategy для BSL (по функциям, не по строкам)",
     "L3-1",
     "M", 2, "M-K2",
     "Качество семантики на русском в 1.5-2× выше CodeBERT и проч.",
     "deep-researcher (BGE-M3)", ""),

    ("L3-3", "L3 Semantic", "Component", "P1",
     "Semantic Code Search в чате",
     "Замена/дополнение MCP search_code (который BM25). Пользователь: 'найди где реализован подбор цен по соглашениям' → vector search в индексе функций → top-K с similarity score → грауnding в file:line.",
     "Semantic",
     "L3-1, L3-2",
     "search_semantic tool в orchestrator (новый internal_tool); UI ResultsCard с relevance score",
     "L3-1, L3-2",
     "S", 0.5, "M-K3",
     "+10% по семантическим запросам (data point: bsl-atlas, по research roadmap 2026-05-21).",
     "deep-researcher (bsl-atlas)", ""),

    ("L3-4", "L3 Semantic", "Use Case", "P1",
     "UC: 'Найди дубли логики в этой конфигурации'",
     "Embedding similarity по телам функций. Cosine > 0.85 = пара дублей. Дополнительно — AST-pattern matching для точного совпадения структуры. Output: список пар с diff.",
     "Semantic",
     "L3-1, L3-2, L2-2 AST",
     "DuplicateDetector: cosine clustering + AST normalizer (переименование переменных перед сравнением)",
     "L3-1, L3-2",
     "M", 2, "M-K3",
     "Технический долг визуализирован. Сразу видны цели для рефакторинга.",
     "deep-researcher (UC-7)", ""),

    ("L3-5", "L3 Semantic", "Component", "P1",
     "Object Memory Encoder (vector-aware sessions)",
     "Все сессии чата → embedded → можно искать 'была у меня сессия про это'. Расширение текущего FTS5 search (который production-ready) векторным.",
     "Semantic",
     "FTS5 production-ready (миграция v5)",
     "Расширение session_search.py + embed messages на write + hybrid retrieval (BM25 + vector reranker)",
     "L3-1, L3-2",
     "M", 2, "M-K3",
     "Sessions становятся persistent knowledge базой аналитика.",
     "deep-researcher (Pieces.app)", ""),

    ("L3-6", "L3 Semantic", "Use Case", "P2",
     "UC: 'Объясни эту функцию построчно с привязкой к ИТС'",
     "AST walk → каждый блок → retrieve релевантный ИТС-стандарт + БСП-pattern → LLM chain-of-thought 'строка делает X, это Y-паттерн, согласно ИТС standard №NNN'.",
     "Semantic + Normative",
     "L2-2 AST, L5-1 ИТС RAG",
     "ExplainerService: AST walker + retrieval+CoT + structured output",
     "L2-2, L5-1",
     "M", 2, "M-K4",
     "Killer demo. Учебно-объяснительная функция.",
     "deep-researcher (UC-5)", ""),

    # ============================================================
    # L4 — BEHAVIORAL (понимание поведения, симуляция, diagnose)
    # ============================================================
    ("L4-1", "L4 Behavioral", "Component", "P0",
     "Diagnose Engine (rule-based + LLM)",
     "Rule-based engine для known patterns. Симптом → диагностический workflow. Примеры: 'пустой отчёт' → check RLS+фильтры+отложенные движения+права; 'медленный запрос' → проверить ВТ-фильтры+цикл+индексы+точки; 'дедлок' → trace порядка блокировок. LLM fallback с retrieved context.",
     "Behavioral",
     "—",
     "DiagnoseRulebook (YAML): ~30 known symptoms с steps; DiagnoseEngine (Python) — оркестратор через MCP+graph+vector",
     "L2-1..L2-4, L3-1, L3-2",
     "L", 5, "M-K3",
     "Главная differentiator vs Напарник/MetaVision. 'Объясняет почему'.",
     "deep-researcher (главная ниша)", ""),

    ("L4-2", "L4 Behavioral", "Use Case", "P0",
     "UC: 'Почему Иванов не видит этот документ?' — RLS-tracer",
     "trace ролей Иванова → найти RLS-шаблоны на типе объекта → парсить шаблон → проверить параметры сеанса → определить виновное условие. Output: 'условие <ВладелецДокумента <> &ТекущийПользователь> не выполнено + как исправить'.",
     "Behavioral",
     "MCP get_access_rights (mcp-1c), L1-2 dossier",
     "RLSTracerService: roles fetch + template parser + session params resolver + reasoning",
     "L4-1",
     "M", 2, "M-K3",
     "Главный demo-кейс. Постоянная боль аналитиков.",
     "deep-researcher (UC-1)", ""),

    ("L4-3", "L4 Behavioral", "Use Case", "P0",
     "UC: 'Почему этот отчёт пустой?' — Report-tracer",
     "СКД → параметры фильтра → значения по умолчанию → источники → виртуальные таблицы → детект антипаттернов (фильтр в WHERE) + проверка отложенных движений если УТ + проверка прав. Pinpoint виновной строки.",
     "Behavioral",
     "L2-4 lineage, MCP get_metadata, L4-1 engine",
     "ReportEmptyTracer: chain of checks; integration с L4-1",
     "L4-1, L2-4",
     "M", 2, "M-K3",
     "Самый частый вопрос аналитика. Решает за минуту вместо часа.",
     "deep-researcher (UC-2)", ""),

    ("L4-4", "L4 Behavioral", "Use Case", "P1",
     "UC: 'Почему проведение падает с ошибкой блокировки?' — Deadlock-tracer",
     "Парсит все ОбработкаПроведения → извлекает порядок блокировок (Заблокировать calls) → строит карту → находит инверсию между документами → объясняет 'A берёт регистр X потом Y, B — Y потом X = дедлок'.",
     "Behavioral",
     "L2-2, L2-3, ТЖ через MCP get_event_log",
     "DeadlockDetector: pattern matcher + lock-order analyzer",
     "L4-1, L2-2",
     "L", 5, "M-K4",
     "Прод-кейс. Дедлоки — самая больная тема enterprise 1С.",
     "deep-researcher (UC-9)", ""),

    ("L4-5", "L4 Behavioral", "Use Case", "P1",
     "UC: 'Почему запрос медленный?' — Query-optimizer",
     "Парс запроса → check ВТ-фильтры в WHERE → check запрос в цикле (контекст вызова) → check подзапросы в SELECT → check точки в ссылках → проверка индексов. Возвращает исправленную версию запроса + объяснение каждой правки.",
     "Behavioral",
     "L2-2 AST, MCP validate_query (mcp-1c), tools/ssl_3_2 паттерны",
     "QueryOptimizer: rule-engine + AST-rewriter + diff output",
     "L4-1, L2-2",
     "M", 2, "M-K4",
     "Производительность — топ-3 боль. 1 секунда vs неделя.",
     "deep-researcher (UC-15)", ""),

    ("L4-6", "L4 Behavioral", "Component", "P2",
     "Hypothesis-Driven Reasoning Framework",
     "Когда нет готового rule — LLM генерирует hypotheses, по каждой — verification через MCP + graph. Workflow: H1 'может RLS', H2 'может отложенные движения', H3 'может фильтр' → для каждой verify → ranked output. Chain-of-thought прозрачен пользователю в trace.",
     "Behavioral",
     "L4-1 engine",
     "HypothesisReasoner: prompts + verification loop + score aggregator",
     "L4-1, L4-2..L4-5",
     "L", 5, "M-K4",
     "Открытый класс диагностики для нестандартных случаев.",
     "claude synthesis", ""),

    # ============================================================
    # L5 — NORMATIVE (ИТС, стандарты, antipatterns, compliance)
    # ============================================================
    ("L5-1", "L5 Normative", "Component", "P0",
     "ИТС RAG (v8327doc + v8std)",
     "Crawler для its.1c.ru/db/v8327doc (платформенная документация) + v8std (317 стандартов). HTML дамп → markdown chunking → embeddings (BGE-M3) → vector store + FTS5. Citation engine: ответ → ссылка 'ИТС стандарт №NNN'.",
     "Normative",
     "ИТС открыт (без подписки). v8std-for-humans (sfaqer) — готовый markdown 317 стандартов!",
     "Crawler (one-time + monthly refresh), chunker (по разделам), indexer; RetrievalAPI + citation formatter",
     "L3-1, L3-2",
     "M", 2, "M-K2",
     "Главный 'normative' источник. Цитирование ИТС = доверие пользователя.",
     "deep-researcher + memory (ИТС открыт)", ""),

    ("L5-2", "L5 Normative", "Component", "P0",
     "БСП Pattern Index (ssl_3_1 + ssl_3_2)",
     "Готовые исходники БСП клонированы в tools/ssl_3_1, tools/ssl_3_2 (CC-BY-4.0). Индексируем по подсистемам: 73 БСП-подсистемы → patterns каждой → embeddings. Когда пользователь спрашивает 'как реализовать длительную операцию' — retrieve готовый БСП-паттерн.",
     "Normative",
     "tools/ssl_3_2/src/, tools/ssl_3_1/src/ — Grep-able прямо сейчас",
     "BSP indexer: subsystem detector + chunker по подсистемам/экспортам + embeddings; RetrievalAPI",
     "L3-1, L3-2",
     "S", 0.5, "M-K2",
     "Снимает галлюцинации LLM на БСП API.",
     "inventory (ssl_3_2 готов)", ""),

    ("L5-3", "L5 Normative", "Component", "P1",
     "Antipattern Detector (A1-A11 + custom)",
     "Static analysis по AST: 11 AI-антипаттернов (A1 тернарник, A2 Сообщить(), A3 НаСервере без БезКонтекста, A4 точка к реквизиту, A5 ВТ_ префикс, A6 пустые Исключение, A7 синхронные диалоги, A8 хардкод, A9 маркеры, A10 magic numbers, A11 ТекущаяДата) + extensible.",
     "Normative",
     "rules/1c/1c-anti-patterns.md в проекте + bsl-language-server tools/bsl-language-server-0.29.0-exec.jar",
     "AntiPatternDetector: AST patterns + integration с BSL LS; result aggregator",
     "L2-2",
     "M", 2, "M-K3",
     "Постоянная проверка качества — гигиена кода.",
     "rules/1c/1c-anti-patterns.md + inventory", ""),

    ("L5-4", "L5 Normative", "Use Case", "P1",
     "UC: 'Соответствует ли это ИТС-стандартам?' — Compliance check",
     "Параметр: file/method/extension/full config. Прогон через L5-3 detector + match с ИТС-стандартами через L5-1 RAG. Output: список нарушений с severity + ссылками на стандарты + suggested fix.",
     "Normative",
     "L5-1, L5-2, L5-3",
     "ComplianceChecker — orchestrator детекторов + report formatter",
     "L5-1, L5-3",
     "S", 0.5, "M-K4",
     "'Compliance Dashboard' — продаётся легко крупным франшизам.",
     "deep-researcher (UC-13)", ""),

    ("L5-5", "L5 Normative", "Use Case", "P2",
     "UC: 'Сгенерируй refactor этого God-модуля по DDD'",
     "Возьми L2-2 AST + L5-2 БСП-паттерны → LLM с retrieved context → план разбиения на N модулей с обоснованием каждого + примеры из БСП.",
     "Normative + Predictive",
     "L2-2, L5-2",
     "RefactorPlanner: prompt template + structured output + validate через BSL LS",
     "L2-2, L5-2",
     "M", 2, "M-K4",
     "Архитектурный рефакторинг — топ-уровень value.",
     "deep-researcher (UC-11 из 1.5)", ""),

    # ============================================================
    # L6 — PREDICTIVE (predict, simulation, что-если)
    # ============================================================
    ("L6-1", "L6 Predictive", "Use Case", "P1",
     "UC: 'Что изменилось за месяц / между версиями?' — Temporal Diff",
     "Git history + Knowledge Layer snapshots. Сравнение двух fingerprints → diff: новые/удалённые/изменённые объекты + diff BSL. 'Этот регистр и эта форма добавлены 14 дней назад — вероятно одна фича'.",
     "Predictive (temporal)",
     "—",
     "TemporalKnowledge: snapshot store + git-aware indexer + diff engine",
     "L1-4, L2-1",
     "L", 5, "M-K5",
     "Аудит. 'Что менял разработчик'. Killer для проектов в саппорте.",
     "deep-researcher (11.1 temporal)", ""),

    ("L6-2", "L6 Predictive", "Use Case", "P1",
     "UC: 'Сравни мою базу с типовой УТ 11.5'",
     "L1-5 detects тип = УТ 11.5. Reference Configurations Library (см. L5-6) содержит карту типовой. Diff: что у пользователя добавлено, что переименовано, что отличается в логике. Output: 'таблица отличий + риски при обновлении типовой'.",
     "Predictive",
     "L1-5, L5-2",
     "ConfigDiff: reference store + structural diff + semantic diff (через L3)",
     "L1-5, L5-2",
     "L", 5, "M-K5",
     "Перед обновлением типовой — критично. Часто стоит миллионы.",
     "deep-researcher (UC-6)", ""),

    ("L6-3", "L6 Predictive", "Component", "P2",
     "Reference Configurations Library",
     "Карта типовой УТ 11.5 / ERP 2.5 / БП 3.0 / УСО 2.5 / ЗУП 3.1. Не сам код (лицензия 1С!), а структурный fingerprint + ключевые методы + бизнес-логика на уровне 'кто что делает'. Получаем через инспекцию официальной поставки 1С (с лицензией), храним как metadata-only.",
     "Predictive",
     "Memory: 1c-business-processes-data-structures-2026-05-24 (готовые карты УТ/ERP/БП/ЗУП)",
     "Reference store + indexer + admin tool для добавления новых типовых",
     "L1-5",
     "L", 5, "M-K5",
     "Без этого L6-2 не работает.",
     "claude synthesis (memory leverage)", ""),

    ("L6-4", "L6 Predictive", "Use Case", "P2",
     "UC: '8.5-Ready Assessment' — миграция на платформу 8.5",
     "Платформа 8.5 выпускается лето 2026. Knowledge Layer содержит diff API 8.3 vs 8.5 + индекс вашей конфигурации → автоматический список рисков ('3 формы используют двойной клик как primary trigger', 'эта функция deprecated', 'это условное оформление с hardcoded RGB сломается на dark theme').",
     "Predictive",
     "L2-2 AST + diff 8.3↔8.5 (нужно собрать)",
     "Migration8.5Assessor: diff loader + matcher + risk classifier + report",
     "L2-2, L5-1",
     "L", 5, "M-K5",
     "Прямой продаваемый продукт! Конкретно сейчас (лето 2026 наступает).",
     "deep-researcher (11.3 migration)", ""),

    ("L6-5", "L6 Predictive", "Use Case", "P3",
     "UC: 'Cross-Configuration Patterns' — бенчмарк vs отрасль",
     "Если Knowledge Layer проиндексировал 100+ конфигураций (с opt-in) — может показывать 'так делают 87% торговых компаний'. Превращает продукт в benchmarking tool. Anonymized aggregation.",
     "Predictive",
     "Нужна база ≥50 проиндексированных конфигов",
     "BenchmarkAggregator (cloud, opt-in only) + UI dashboard",
     "L1-5, all L1-L3",
     "XL", 10, "M-K6",
     "Долгосрочный moat. После 100+ клиентов = unique data asset.",
     "deep-researcher (11.2 cross-config)", ""),

    ("L6-6", "L6 Predictive", "Use Case", "P3",
     "UC: 'Natural Language Query over Config'",
     "'Покажи всех поставщиков у которых нет ни одного проведённого счёта за последние 90 дней'. NL→знание структуры (L2)→генерация запроса 1С→валидация через validate_query→выполнение через MCP execute_query→Table card. Это NL2SQL для 1С.",
     "Predictive (semantic NL2SQL)",
     "L1-1 cache, L2-1 graph",
     "NL2QueryService: LLM с retrieved schema + validator + executor",
     "L1-1, L2-1, MCP execute_query",
     "L", 5, "M-K6",
     "'Спрашивай базу как человека'. Самая броская demo-фича.",
     "deep-researcher (11.4 NL2SQL)", ""),

    ("L6-7", "L6 Predictive", "Use Case", "P3",
     "UC: 'Automated Code Review для каждого commit'",
     "Git hook → diff → Knowledge Layer анализирует in context → comments в PR с file:line + ссылки на ИТС. Не статический анализ, а контекстуальный ('это изменение ломает паттерн, который используется в 12 других местах').",
     "Predictive",
     "L2-1, L3-1, L5-1, L5-3",
     "GitHook + ReviewBot + GitLab/GitHub PR integration",
     "L2-1, L3-1, L5-1",
     "L", 5, "M-K6",
     "Enterprise DevOps фича. Продаётся командам с CI/CD.",
     "deep-researcher (11.5 auto review)", ""),

    # ============================================================
    # CROSS-CUTTING: Pipeline / Storage / Infra
    # ============================================================
    ("X-1", "Pipeline", "Component", "P0",
     "First-Touch Indexer Pipeline",
     "При подключении новой конфигурации: (1) Quick scan 10 сек — метаданные через MCP get_metadata_tree → metadata_cache; (2) Background full crawl 2-15 мин — AST через TreeSitter + edges → graph; (3) Embeddings 5-20 мин — BGE-M3 → vector store. Progress UI: 'Анализирую базу... 234/1200 объектов, оценка 8 минут'.",
     "Pipeline",
     "Code Index прод-данные: 93k файлов 19k BSL за 2:31 (proven pattern)",
     "IndexerPipeline (Python): job runner + progress events SSE + cancel + retry; UI Progress card",
     "L1-1, L2-1, L2-2, L3-1, L3-2",
     "L", 5, "M-K2",
     "Это первое впечатление пользователя. 'Установил, подключил, ждёт'.",
     "deep-researcher (Code Index numbers)", ""),

    ("X-2", "Pipeline", "Component", "P0",
     "Incremental Update (mtime / event log)",
     "При изменении конфигурации: detect через event log (1С пишет туда об обновлениях) или mtime файлов (если EDT-workspace). Только изменённые объекты → re-parse → update graph + re-embed. Per file 1 сек ≤. Background, без блокировки UI.",
     "Pipeline",
     "Code Index демонстрирует mtime mode (daemon)",
     "IncrementalUpdater: change detector + diff applier + invalidate dependents",
     "X-1",
     "M", 2, "M-K2",
     "Без этого Knowledge Layer протухает через день. Critical for trust.",
     "deep-researcher (Code Index daemon)", ""),

    ("X-3", "Pipeline", "Component", "P0",
     "Knowledge Store Layout",
     "Per-configuration: ~/.analyst-1c/knowledge/<config-fingerprint>/{metadata.sqlite, graph.sqlite, vectors.lance, ast/, snapshots/}. Multi-channel — папка под каждый. Lock-file для concurrent access. Backup-friendly (один dir = всё).",
     "Pipeline",
     "Existing SQLite stack (aiosqlite)",
     "StoreManager: layout + locks + backup; миграция при апдейтах формата",
     "—",
     "S", 0.5, "M-K2",
     "Foundation. Без этого Knowledge Layer = в /tmp.",
     "claude synthesis", ""),

    ("X-4", "Pipeline", "Component", "P1",
     "MCP Result Cache (с TTL)",
     "Кеш результатов MCP-вызовов (помимо metadata): get_object_structure, get_event_log, get_access_rights. TTL 5-60 мин в зависимости от endpoint. Invalidate при изменении конфигурации.",
     "Pipeline",
     "—",
     "MCPCacheService: redis-like in-memory + LRU; key composition + TTL config",
     "L1-1",
     "S", 0.5, "M-K2",
     "MCP overhead -70% на повторных вопросах одного контекста.",
     "perf consideration", ""),

    ("X-5", "Pipeline", "Component", "P2",
     "Hybrid Retrieval (BM25 + Vector + Reranker)",
     "Лучшая практика 2025: dense + sparse одновременно (как BGE-M3 умеет нативно), потом cross-encoder reranker (bge-reranker-v2-m3) топ-К. Качество vs только vector — +15-25%.",
     "Pipeline",
     "BGE-M3 поддерживает dense+sparse+colbert; reranker есть в той же семье",
     "RetrievalOrchestrator: parallel queries + score fusion + reranker call",
     "L3-1, L3-2",
     "M", 2, "M-K4",
     "Precision retrieval = меньше LLM галлюцинаций.",
     "deep-researcher (Copilot 4 strategies)", ""),

    ("X-6", "Pipeline", "Decision", "P0",
     "Решение: Vector DB — LanceDB vs sqlite-vec",
     "LanceDB: production-grade, Continue.dev уже использует, SIMD, disk-mapped, отдельный файл. sqlite-vec: всё в одном SQLite (уже есть aiosqlite), extension simple. Рекомендация: НАЧАТЬ с sqlite-vec (lock-in минимальный), мигрировать на LanceDB если станет узким местом.",
     "Pipeline",
     "sqlite-vec / LanceDB — оба open-source",
     "Адоптировать sqlite-vec в migration v11 (10 строк); прототип на этом",
     "L3-1",
     "S", 0.5, "M-K1",
     "Снимает блокирующее техническое решение. Без него L3 не стартует.",
     "claude synthesis", ""),

    ("X-7", "Pipeline", "Decision", "P0",
     "Решение: Graph DB — SQLite CTE vs Kuzu",
     "Apple купила Kuzu (10.2025) — community рассматривает форки, risk высокий. Code Index доказал что recursive CTE в SQLite справляется с реальными размерами (93k файлов, find_path). Рекомендация: SQLite + edges table + recursive CTE. Дёшево, без vendor lock-in.",
     "Pipeline",
     "SQLite (уже в стеке)",
     "graph migration с edges/nodes tables; helpers find_path / neighbors / shortest_path через CTE",
     "L2-1",
     "S", 0.5, "M-K2",
     "Снимает второе блокирующее решение.",
     "deep-researcher (Kuzu Apple acquisition)", ""),

    ("X-8", "Pipeline", "Decision", "P0",
     "Решение: Embedding inference — Ollama vs HF TEI vs ONNX",
     "Ollama: проще всего (одна команда), но overhead. HF text-embeddings-inference: специализированный, быстрее, но Docker. ONNX runtime: embedded в Python, без external service, но больше кода. Рекомендация: ONNX (embedded, нет depend на Docker/Ollama) для desktop deploy; Ollama optionally для self-host.",
     "Pipeline",
     "ONNX runtime, FastEmbed (бинарные модели в pip пакете)",
     "FastEmbed wrapper (~30 строк): загрузить BGE-M3 ONNX → encode batch",
     "L3-2",
     "S", 0.5, "M-K2",
     "Один pip install вместо Docker + Ollama. Critical для Electron-deploy.",
     "claude synthesis (Electron-friendly)", ""),

    # ============================================================
    # UX: новые карточки и взаимодействие
    # ============================================================
    ("UX-1", "UX", "Component", "P0",
     "GraphCard — интерактивный граф (React Flow)",
     "Новый тип карточки в frontend. Использует React Flow / xyflow для node-edge визуализации. Поддерживает: zoom, pan, hover-tooltip, click-to-expand, фильтр по типу edge. Применение: L2-5 (цепочка проведения), L2-7 (UI→регистр), L6-4 (8.5 migration risks).",
     "UX",
     "lib/cards/* — есть инфраструктура карточек",
     "frontend/components/cards/GraphCard.tsx + types.ts расширение + React Flow npm install",
     "—",
     "M", 2, "M-K3",
     "Без визуализации L2/L4/L6 use cases не воспринимаются.",
     "claude synthesis", ""),

    ("UX-2", "UX", "Component", "P1",
     "DiagnoseCard — структурированное 'почему не работает'",
     "Карточка с pinpoint: симптом → шаги диагностики (collapsible) → finding (highlighted) → recommendation с file:line. Visual: pipeline-like с зелёными/красными чек-марками.",
     "UX",
     "ObjectCard / TableCard как образцы",
     "DiagnoseCard.tsx + types + DiagnoseEvent SSE type",
     "L4-1",
     "M", 2, "M-K3",
     "UX для главной differentiator-фичи (объяснение почему).",
     "claude synthesis", ""),

    ("UX-3", "UX", "Component", "P1",
     "ComparisonCard — diff между сущностями",
     "Side-by-side diff: версия N vs N+1 кода, ваша реализация vs типовая, до vs после рефакторинга. Подсветка различий.",
     "UX",
     "—",
     "ComparisonCard.tsx + monaco-editor diff view (или react-diff-viewer)",
     "—",
     "M", 2, "M-K5",
     "Поддержка L6-1 (temporal diff) и L6-2 (vs типовая).",
     "claude synthesis", ""),

    ("UX-4", "UX", "Component", "P2",
     "TimelineCard — события во времени",
     "Хронологический список: изменения метаданных + commits git + event_log события. Filter by type. Click для drill-down.",
     "UX",
     "—",
     "TimelineCard.tsx + timeline lib (react-chrono или custom)",
     "L6-1",
     "M", 2, "M-K5",
     "Поддержка L6-1. 'Что менял разработчик последние N дней'.",
     "claude synthesis", ""),

    ("UX-5", "UX", "Component", "P2",
     "ProcessCard — BPMN бизнес-процесса",
     "Mermaid sequenceDiagram / BPMN-style для бизнес-процессов (закупка, продажа, ВЭД, закрытие месяца). Базируется на L2-4 lineage + L4 knowledge о процессах.",
     "UX",
     "mermaid.js — npm install ~700kb",
     "ProcessCard.tsx + mermaid render",
     "L2-4",
     "M", 2, "M-K5",
     "'Покажи бизнес-процесс' — высокая ценность.",
     "memory (10 готовых процессов)", ""),

    ("UX-6", "UX", "Component", "P1",
     "Indexing Progress UI (на старте)",
     "При первом подключении конфигурации — модальное окно: 'Изучаю вашу базу. Это разовая операция, ~10 минут. Прогресс: метаданные ✓ / AST 234/1200 / индексация...'. С опцией 'продолжить позже', 'настроить уровень детализации'.",
     "UX",
     "OnboardingDialog паттерн",
     "IndexingProgress component + SSE подписка на X-1 events",
     "X-1",
     "M", 2, "M-K2",
     "Первое впечатление. Если выглядит как 'непонятный freeze' — отток.",
     "claude synthesis", ""),

    ("UX-7", "UX", "Component", "P2",
     "Citation Layer (как Perplexity)",
     "Все ответы LLM с inline-ссылками: [1] ИТС §147, [2] file.bsl:42, [3] БСП.ДлительныеОперации:88. Hover → preview. Click → открыть source.",
     "UX",
     "Perplexity citations паттерн",
     "frontend citation parser + tooltip + source viewer",
     "L5-1, L5-2",
     "M", 2, "M-K4",
     "Доверие пользователя. Каждое утверждение grounded.",
     "deep-researcher (Perplexity)", ""),

    ("UX-8", "UX", "Component", "P3",
     "Conversational Drill-Down",
     "После ответа с graph/diagnose — chip-кнопки 'детальнее по A', 'почему B', 'что если X'. Программируемые follow-ups на основе текущего answer-context.",
     "UX",
     "—",
     "DrillDownChips component + suggestion engine (LLM 1-shot)",
     "L4-1",
     "M", 2, "M-K5",
     "Сокращает trial-and-error пользователя в чате.",
     "claude synthesis (Cursor pattern)", ""),

    # ============================================================
    # PRICING / GTM / POSITIONING
    # ============================================================
    ("PG-1", "Pricing/GTM", "Decision", "P0",
     "Pricing model — Per-Configuration Tier",
     "Free: только L0-L1 (lexical/structural), 3 конфигурации. Standard 4900₽/мес: L0-L4 (включая diagnose), unlimited конфигов. Enterprise (от 49k₽/мес): L0-L6 (включая predictive + temporal), self-hosted, custom integrations. Тонкость: 'configuration' = индексированная база, не пользователь.",
     "Pricing/GTM",
     "—",
     "Конкретный price-list + biller integration (Cloud Payments / ЮKassa)",
     "—",
     "M", 2, "M-K6",
     "Чёткое ценообразование разблокирует commerce.",
     "deep-researcher (3 модели монетизации)", ""),

    ("PG-2", "Pricing/GTM", "Decision", "P0",
     "Главный killer-product (USP) = 'Объяснитель'",
     "Фокус первого коммерческого пакета: вводишь симптом → трассировка с file:line + ссылкой на ИТС. Конкретно: пустой отчёт / медленный запрос / невидимый документ / ошибка проведения. Это L4 + L5 = MVP Knowledge Layer.",
     "Pricing/GTM",
     "L4-1..L4-5, L5-1",
     "Marketing copy + landing block + demo video",
     "L4-1, L4-2, L4-3, L4-5, L5-1",
     "S", 0.5, "M-K3",
     "Чёткое positioning. 'Экономия на диагностике' — продаваемое.",
     "deep-researcher (вердикт)", ""),

    ("PG-3", "Pricing/GTM", "Decision", "P1",
     "Конкурентная позиция — заполнить L4-L6 (ниши Напарника + MetaVision)",
     "Напарник = L1-3 (только writing, не explain). MetaVision = L1-2 (structural). Knowledge Layer = L3-6 включая explain 'почему'. Это empty space. Позиционировать: 'Напарник пишет, MetaVision видит, мы — объясняем'.",
     "Pricing/GTM",
     "—",
     "Marketing positioning + comparison table",
     "—",
     "S", 0.5, "M-K3",
     "Уникальность доказана. До октября 2026 пока Напарник бесплатен.",
     "deep-researcher (positioning)", ""),

    ("PG-4", "Pricing/GTM", "Component", "P1",
     "Сервис 8.5-Ready Assessment как standalone offering",
     "Отдельный pre-paid сервис: индексируешь свою базу → получаешь отчёт 'риски при миграции на 8.5'. Цена 9 900-49 000₽ в зависимости от размера. Timing: лето 2026 платформа выходит.",
     "Pricing/GTM",
     "L6-4",
     "Landing + payment + automated report pipeline",
     "L6-4",
     "M", 2, "M-K5",
     "Прямой revenue здесь и сейчас, до релиза Knowledge Layer.",
     "deep-researcher (8.5-Ready)", ""),

    ("PG-5", "Pricing/GTM", "Component", "P2",
     "Сервис Configuration Audit для франшиз",
     "B2B-партнёрский продукт: франшизы делают audit клиентских баз. 'Купи 100 audit-токенов = 100 проиндексированных баз'. Каждая база → автоматический отчёт. Цена per-token 990-1990₽.",
     "Pricing/GTM",
     "L1-L5",
     "Partner portal + bulk billing + reports white-label",
     "all L1-L5",
     "L", 5, "M-K6",
     "Channel-sales 5-10× direct revenue.",
     "deep-researcher (Per-crawl model)", ""),

    ("PG-6", "Pricing/GTM", "Component", "P2",
     "Self-Hosted License для крупных франшиз",
     "Annual license 250-800k₽ за on-premise Knowledge Layer server. Партнёр разворачивает у себя → индексирует клиентские базы → unlimited internal usage. КИИ-compliant.",
     "Pricing/GTM",
     "Docker self-host (требует DEVOPS-2 из основного плана)",
     "License system + Docker image + docs + installation support",
     "—",
     "L", 5, "M-K6",
     "Enterprise upsell. 1 контракт = $5-10k.",
     "deep-researcher (Self-hosted model)", ""),

    # ============================================================
    # OPS / DATA / META
    # ============================================================
    ("OPS-1", "Cross-cutting", "Component", "P1",
     "Privacy & Compliance: 'данные не покидают машину'",
     "Knowledge Layer индексация — ЛОКАЛЬНО. Embeddings — local ONNX. RAG — local. LLM — на выбор пользователя (Cloud.ru для 152-ФЗ или NVIDIA NIM). Документировать в PRIVACY.md + UI badge 'Local Knowledge'.",
     "Cross-cutting",
     "Architecture: ONNX embeddings (X-8), local SQLite",
     "PRIVACY.md обновление + UI badge",
     "X-8",
     "S", 0.5, "M-K2",
     "Compliance для enterprise РФ + общий privacy-first ethos.",
     "claude synthesis (152-ФЗ critical)", ""),

    ("OPS-2", "Cross-cutting", "Component", "P1",
     "Telemetry / Indexing Quality Metrics",
     "Внутренний dashboard: время индексации per config, retrieval precision (через user feedback 👍👎), embedding model performance, miss rate vector search. Privacy-respecting (только metrics, не контент).",
     "Cross-cutting",
     "—",
     "MetricsCollector + admin dashboard",
     "X-1",
     "M", 2, "M-K4",
     "Data-driven improvement Knowledge Layer.",
     "claude synthesis", ""),

    ("OPS-3", "Cross-cutting", "Component", "P2",
     "Knowledge Layer Export / Import",
     "Один файл-bundle (.klzip) с метаданными+графом+embeddings конкретной конфигурации. Можно передать коллеге, сохранить как snapshot, восстановить после переустановки. Хеш-проверка integrity.",
     "Cross-cutting",
     "—",
     "Export/Import CLI + UI + integrity checks",
     "X-3",
     "M", 2, "M-K5",
     "Portability. 'Перенеси аналитика на новую машину за 5 минут'.",
     "claude synthesis", ""),

    ("OPS-4", "Cross-cutting", "Decision", "P1",
     "Open vs Closed: Knowledge Layer как proprietary advantage",
     "Indexing pipeline можно open-source (привлечь contributors), но reference configurations library + проиндексированные knowledge bundles — closed. Это создаёт moat без блокировки community innovation.",
     "Cross-cutting",
     "—",
     "OSS vs Proprietary boundary doc; LICENSE",
     "—",
     "S", 0.5, "M-K1",
     "Стратегическое решение влияющее на adoption и moat.",
     "claude synthesis", ""),

    ("OPS-5", "Cross-cutting", "Component", "P2",
     "Knowledge Layer как MCP Server (внутренний)",
     "Knowledge Layer экспонируется через свой MCP-server (порт например 7070). LLM в orchestrator вызывает knowledge_search, knowledge_dossier, knowledge_diagnose как обычные tools. Это даёт чистую границу + возможность стороннему ИИ работать с тем же индексом.",
     "Cross-cutting",
     "FastMCP / mcp-python-sdk",
     "MCP server wrapper над Knowledge Layer API",
     "all L1-L5",
     "M", 2, "M-K4",
     "Архитектурная чистота. И marketable как 'MCP-first product'.",
     "deep-researcher (MCP adoption trend)", ""),
]

# ============================================================
# Лист 2 — УРОВНИ ПОНИМАНИЯ
# ============================================================
LEVELS = [
    ("L0", "Lexical",
     "Знает имена объектов. Умеет находить по строке.",
     "Live MCP search_code (BM25)",
     "—",
     "Существующее search в чате",
     "Конкуренты: feenlace/mcp-1c"),
    ("L1", "Structural",
     "Знает структуру: реквизиты, формы, табл.части, типы.",
     "metadata_cache (SQLite), Object Dossier",
     "MCP get_metadata + кеш",
     "L1-1 metadata cache, L1-2 dossier, L1-3 UC 'расскажи про объект'",
     "Code Index, EDT Схема данных. Напарник = здесь и L3."),
    ("L2", "Relational",
     "Знает связи: callgraph, документ→регистр, where-used.",
     "Knowledge Graph (SQLite nodes/edges + recursive CTE)",
     "TreeSitter BSL + mdclasses XML",
     "L2-1..L2-7: graph, parser, callgraph, lineage, UC цепочка/импакт/trace",
     "bsl-graph (alpha), MetaVision = здесь."),
    ("L3", "Semantic",
     "Понимает смысл: похожий код, дубли, объяснения функций.",
     "Vector store (sqlite-vec → LanceDB), embeddings BGE-M3",
     "Local ONNX inference",
     "L3-1..L3-6: vector store, embedding pipeline, search, дубли, sessions encoder, explain функцию",
     "bsl-atlas, FSerg/mcp-1c-v1. Напарник writing = здесь."),
    ("L4", "Behavioral",
     "Понимает поведение: что произойдёт, диагностика 'почему'.",
     "Diagnose engine (rules + LLM CoT)",
     "Reasoning + retrieved context",
     "L4-1..L4-6: engine, RLS-tracer, report-tracer, deadlock, query-optimizer, hypothesis reasoner",
     "ПУСТО. Главная ниша Knowledge Layer."),
    ("L5", "Normative",
     "Знает стандарты ИТС, антипаттерны, best practices.",
     "ИТС RAG (v8327doc + v8std), БСП index, antipattern detector",
     "RAG + BSL LS + AST patterns",
     "L5-1..L5-5: ИТС RAG, БСП index, antipattern detector, compliance check, refactor planner",
     "ПУСТО. v8std-for-humans есть как корпус."),
    ("L6", "Predictive",
     "Предсказывает: temporal diff, vs типовая, миграция, NL2SQL.",
     "Cross-temporal + reference configurations + cross-config",
     "Все предыдущие + LLM с CoT",
     "L6-1..L6-7: temporal, vs типовая, ref configs, 8.5-Ready, cross-config benchmark, NL2SQL, auto code review",
     "ПУСТО. Долгосрочный moat."),
]

# ============================================================
# Лист 3 — USE CASES
# ============================================================
USE_CASES = [
    ("UC-1", "L4", "Пустой отчёт у одного, у другого — есть данные",
     "Trace ролей пользователя → RLS-шаблоны на типе объекта → парсинг условий → проверка параметров сеанса → виновное условие. Output: 'условие X не выполнено, пользователь не входит в группу Y'.",
     "Главная боль аналитиков enterprise. Часы детектива → минута диагностики.",
     "L4-2, L1-2"),
    ("UC-2", "L4", "Почему отчёт пустой",
     "СКД → параметры фильтра → значения по умолчанию → источники → виртуальные таблицы → детект антипаттерна (фильтр в WHERE вместо параметров) → отложенные движения если УТ. Pinpoint виновной строки.",
     "Самый частый вопрос. Минута вместо часа.",
     "L4-3, L2-4"),
    ("UC-3", "L2", "Покажи цепочку проведения этого документа",
     "Граф: ОбработкаПроведения → регистры (с движениями +/-) → подписки → связанные объекты → визуализация Mermaid/React Flow.",
     "'Я вижу как документ влияет' — то что в EDT часами.",
     "L2-5, UX-1"),
    ("UC-4", "L2", "Что сломается если переименую реквизит",
     "Impact analysis по graph: все referencing nodes (запросы, BSL, СКД, Form.xml, RLS) с severity. 'Critical: блок проведения, Medium: 3 отчёта'.",
     "Снимает страх рефакторинга.",
     "L2-6"),
    ("UC-5", "L3", "Объясни эту функцию построчно с привязкой к ИТС",
     "AST walk → каждый блок → retrieve ИТС-стандарт + БСП-паттерн → LLM CoT 'строка делает X, это Y-паттерн, ИТС §NNN'.",
     "Учебно-объяснительная функция. Demo killer.",
     "L3-6, UX-7"),
    ("UC-6", "L6", "Сравни мою реализацию с типовой УТ 11.5",
     "Reference config УТ 11.5 → structural diff с пользователем → семантический diff (через L3). 'Вы не используете РаспределениеЗапасов — это устаревший паттерн УТ 10.3'.",
     "Перед обновлением типовой — критично. Часто = миллионы.",
     "L6-2, L6-3"),
    ("UC-7", "L3", "Найди дубли логики",
     "Embedding similarity > 0.85 по функциям + AST-pattern matching. Output: пары дублей с diff.",
     "Технический долг визуализирован. Цели рефакторинга.",
     "L3-4"),
    ("UC-8", "L2", "Граф всех мест использования регистра X",
     "WRITES_TO + READS_FROM edges + формы + MCP вызовы. Визуализация.",
     "Карта влияния регистра. Аудит ясен.",
     "L2-5, UX-1"),
    ("UC-9", "L4", "Почему проведение падает с блокировкой",
     "Парс ОбработкаПроведения → порядок Заблокировать → сравнение с каноническим → инверсия = дедлок-pattern.",
     "Дедлоки = больная тема enterprise.",
     "L4-4"),
    ("UC-10", "L4", "Точки входа внешних систем (audit)",
     "HTTP/web/COM/REST/ODATA + права + валидация + safety по ИТС.",
     "Security audit одной командой.",
     "L4-1, L5-1"),
    ("UC-11", "L2", "Trace от UI-кнопки до записи в регистр",
     "Form.xml → handler → BSL chain → server → запросы → движения. Sequence diagram.",
     "'Как работает эта кнопка' за 10 сек.",
     "L2-7"),
    ("UC-12", "L2", "Сколько серверных вызовов при открытии формы",
     "AST подсчёт &НаСервере / &НаСервереБезКонтекста + граф вызовов из ПриОткрытии → roundtrips estimate.",
     "Performance профиль формы без открытия.",
     "L2-2, L2-3"),
    ("UC-13", "L5", "Где нарушен ИТС-стандарт NNN",
     "Pattern matching по всей базе → file:line + severity + пример fix.",
     "Compliance dashboard для крупных франшиз.",
     "L5-4, L5-3"),
    ("UC-14", "L6", "Что изменится при апгрейде типовой 11.4 → 11.5",
     "Карты двух версий + diff + impact на ваши доработки + риски.",
     "Pre-upgrade аудит.",
     "L6-2"),
    ("UC-15", "L4", "Почему запрос медленный",
     "Парс → антипаттерны → индексы → исправленный вариант + объяснение.",
     "Топ-3 боль. Секунда vs неделя.",
     "L4-5"),
    ("UC-16", "L2", "Какие подписки/задания затронут изменение функции",
     "Callgraph + SUBSCRIBES_TO edges + регламентные задания.",
     "Перед коммитом — full impact.",
     "L2-3"),
    ("UC-17", "L3", "Объясни этот регистр: что в нём, кто пишет, для чего",
     "Dossier + WRITES_TO + READS_FROM + business semantics (через L3 retrieval из v8std/типовых).",
     "Новый разработчик понимает за минуту вместо часа.",
     "L3-3, L1-2"),
    ("UC-18", "L6", "Расскажи историю этой конфигурации (temporal)",
     "Git + snapshots → diff по месяцам → 'фича X добавлена 2 мес назад вместе с регистром Y и формой Z'.",
     "Аудит/legacy системы. Killer для саппорта.",
     "L6-1"),
    ("UC-19", "L4", "Расскажи всё что знаешь про эту ошибку '...'",
     "Полнотекстовый match по логам + БСП + ИТС + код проекта → структурированное описание + типичные fix.",
     "Самый частый запрос аналитика. Сейчас — google → 30 минут.",
     "L4-1, L5-1, L5-2"),
    ("UC-20", "L6", "Покажи поставщиков без проведённых счетов за 90 дней (NL2SQL)",
     "Понимает структуру → генерирует запрос 1С → validate → execute → Table card.",
     "'Спрашивай базу как человека'. Демо-killer.",
     "L6-6"),
    ("UC-21", "L6", "Симулируй: что произойдёт если я выполню операцию Х завтра",
     "Symbolic execution: подменить ТекущаяДата → trace через ОбработкаПроведения → ожидаемые движения без записи. 'Эта реализация изменит остатки на X в Y'.",
     "What-if без боли. Перед production изменением.",
     "L4-1, L4-6"),
    ("UC-22", "L5", "Сгенерируй BSL по моему описанию + verify",
     "Описание → retrieve БСП-паттерн → LLM gen → BSL LS validate → fix if errors → return verified code.",
     "Generation с гарантией compile.",
     "L5-2, L5-3"),
    ("UC-23", "L4", "Покажи 5 самых рискованных мест в конфигурации",
     "Cross-analysis: complexity + tech-debt + ИТС нарушения + dependencies + последние изменения = риск-score. Top-5.",
     "Дайджест health конфигурации.",
     "L4-1, L5-3"),
    ("UC-24", "L6", "Сгенерируй документацию для нового разработчика",
     "Walk через знание → README со всеми ключевыми объектами + бизнес-процессами + рисками + быстрым стартом.",
     "Онбординг с 2 недель → 2 часа.",
     "all L1-L5"),
    ("UC-25", "L4", "Объясни этот ОПП документ (кастомный объект Транзита)",
     "Когда есть только знание метаданных + код — синтез: 'Этот документ создаёт движения в N регистрах, его используют M отчётов, типичный сценарий: ...'.",
     "Понимание custom объектов = первый день нового аналитика.",
     "L1-2, L4-1, L3-6"),
]

# ============================================================
# Лист 4 — TECH STACK
# ============================================================
TECH = [
    ("Vector DB", "sqlite-vec (старт) → LanceDB (когда нужна prod-scale)",
     "Lightweight embed, в SQLite уже есть aiosqlite, нулевые зависимости",
     "Continue.dev использует LanceDB; sqlite-vec — 200KB extension",
     "200KB → 50MB"),
    ("Graph DB", "SQLite + edges table + recursive CTE",
     "Apple купила Kuzu — risk; Code Index доказал что recursive CTE справляется с 93k файлов",
     "Один SQLite-файл; Без vendor lock-in",
     "Часть знакомого SQLite"),
    ("Embeddings", "BAAI/bge-m3 (multilingual, 1024-dim, 8192-context)",
     "100+ языков (русский!), dense+sparse одновременно",
     "Стандарт мультиязычной RAG; ~570MB",
     "ONNX bundle"),
    ("Embedding Runtime", "FastEmbed (ONNX, in-process)",
     "Один pip install, без Docker/Ollama. Critical для Electron-deploy",
     "Альтернативы: Ollama (требует daemon), HF TEI (требует Docker)",
     "Bundle в PyInstaller"),
    ("Reranker", "BAAI/bge-reranker-v2-m3 (опционально)",
     "+15-25% к precision retrieval, особенно для длинного контекста",
     "Cross-encoder поверх BGE-M3 семьи",
     "~500MB"),
    ("BSL Parser", "tree-sitter-bsl (через py-tree-sitter)",
     "Incremental parsing, AST за миллисекунды, используется в Code Index",
     "Грамматика существует, протестирована на проде",
     "Native bindings"),
    ("Metadata Parser", "mdclasses (Java через subprocess или JPype)",
     "Готовый парсер XML конфигурации 1С (LGPL-3)",
     "Альтернатива: чистый Python lxml для XML (требует много кода)",
     "JVM или JPype wrapper"),
    ("XML/MDO Parser", "lxml + bsl-language-server",
     "Для простых cases — встроенный, для глубокого — mdclasses",
     "BSL LS уже в проекте (tools/bsl-language-server-0.29.0-exec.jar)",
     "Уже есть"),
    ("Hybrid Retrieval", "BGE-M3 (dense+sparse native) + bge-reranker (cross-encoder)",
     "Лучшая практика 2025 (Sourcegraph Cody, Copilot Enterprise)",
     "BGE-M3 уникально умеет dense+sparse одновременно",
     "Один HTTP call"),
    ("Diagnose Engine", "Custom rule-engine (YAML rules) + LLM fallback",
     "Гибрид: правила для known patterns (быстро/дёшево), LLM для нестандартного",
     "Inspirations: Sentry suggested fixes, Datadog AI",
     "0 deps (python YAML)"),
    ("Frontend Graph Viz", "React Flow (xyflow)",
     "Best-in-class для interactive node-edge диаграмм React",
     "Альтернатива: Cytoscape.js (тяжелее), Mermaid (статика)",
     "~150KB gzipped"),
    ("Frontend Diagram", "mermaid.js",
     "Sequence diagrams, BPMN-like flows. Markdown-friendly",
     "Уже стандарт для документации",
     "~700KB gzipped"),
    ("Frontend Diff", "monaco-editor diff view (или react-diff-viewer)",
     "Сравнение кода/конфигов для ComparisonCard",
     "Используется в VS Code",
     "Monaco уже может быть в depe"),
    ("ИТС Crawler", "httpx + BeautifulSoup4 + markdownify",
     "Простой crawler с rate-limit, dump в markdown, индексация в RAG",
     "Альтернатива: использовать готовый v8std-for-humans (sfaqer) если v8std покрывает",
     "Минимальный код"),
    ("Knowledge Layer MCP", "FastMCP (Python SDK)",
     "Экспонируем Knowledge Layer как MCP-сервер. Marketable как 'MCP-first'",
     "Стандартный паттерн 2025-2026",
     "Часть существующего стека"),
]

# ============================================================
# Лист 5 — ROADMAP
# ============================================================
ROADMAP = [
    ("M-K1", "Foundation: Decisions + Quick Wins",
     "1-2 нед", "до 15.06.2026",
     "Фикс архитектурных решений (X-6 vector DB, X-7 graph, X-8 embeddings), L1 metadata_cache + dossier (L1-1..L1-3) + OPS-4 open/closed boundary. Seed SkillStore из готовых memory-файлов. Подключить ssl_3_2 grep в system prompt. Без code rewrite — только инфра + контент.",
     "L1-1, L1-2, L1-3, L1-4, X-3, X-6, X-7, X-8, OPS-4"),
    ("M-K2", "Knowledge Foundation: L1 + L5 базы + Pipeline",
     "3-4 нед", "до 20.07.2026",
     "Indexer pipeline (X-1) + incremental (X-2) + MCP cache (X-4) + Knowledge Store layout (X-3). L5-1 ИТС RAG + L5-2 БСП index. L3-1 vector store + L3-2 embeddings. UX-6 Indexing Progress UI. OPS-1 privacy badge.",
     "X-1, X-2, X-3, X-4, X-8, L3-1, L3-2, L5-1, L5-2, L1-5, UX-6, OPS-1"),
    ("M-K3", "Relational + Behavioral: L2 + L4 + Killer UCs",
     "4-6 нед", "до 31.08.2026",
     "L2-1 graph, L2-2 BSL parser, L2-3 callgraph, L2-4 data lineage. L4-1 diagnose engine. Топ-5 UC: UC-1 RLS, UC-2 пустой отчёт, UC-3 цепочка, UC-4 impact, UC-15 медленный. UX-1 GraphCard + UX-2 DiagnoseCard. PG-2 + PG-3 positioning + Killer Demo Day. L5-3 antipattern detector + L3-3 semantic search.",
     "L2-1..L2-4, L4-1, L4-2, L4-3, L4-5, L2-5, L2-6, UX-1, UX-2, L5-3, L3-3, PG-2, PG-3"),
    ("M-K4", "Normative + Hybrid Retrieval + Advanced Diagnose",
     "4-5 нед", "до 30.09.2026",
     "L4-4 deadlock-tracer + L4-6 hypothesis reasoner. L5-4 compliance check + L5-5 refactor planner. L3-5 sessions encoder + L3-6 explain функцию. X-5 hybrid retrieval + reranker. UX-7 citations + OPS-2 telemetry + OPS-5 Knowledge Layer MCP. Готовность к INFOSTART A&PM EVENT октябрь.",
     "L4-4, L4-6, L5-4, L5-5, L3-5, L3-6, X-5, UX-7, OPS-2, OPS-5"),
    ("M-K5", "Predictive: L6 + Temporal + 8.5-Ready (revenue trigger)",
     "5-7 нед", "до 30.11.2026",
     "L6-1 temporal diff + L6-2 vs типовая + L6-3 reference configurations. L6-4 8.5-Ready Assessment (PG-4 как standalone offering!). UX-3 ComparisonCard + UX-4 TimelineCard + UX-5 ProcessCard. L2-7 UI-trace. OPS-3 export/import. Запуск 8.5-Ready как paid service до выхода платформы.",
     "L6-1, L6-2, L6-3, L6-4, PG-4, UX-3, UX-4, UX-5, L2-7, OPS-3"),
    ("M-K6", "Predictive++: NL2SQL + Cross-Config + Enterprise",
     "6-10 нед", "до 31.01.2027",
     "L6-5 cross-config benchmark + L6-6 NL2SQL + L6-7 auto code review. PG-1 финальный pricing (Per-Configuration Tier) + PG-5 franchise channel + PG-6 self-hosted license. UX-8 conversational drill-down. Enterprise sales motion.",
     "L6-5, L6-6, L6-7, PG-1, PG-5, PG-6, UX-8"),
]

# ============================================================
# Лист 6 — Pricing & GTM (отдельный)
# ============================================================
PRICING = [
    ("Tier", "Цена/мес", "Уровни", "Конфигов", "Целевой сегмент", "Когда"),
    ("Free", "0₽", "L0-L1 (lexical/structural)", "3", "P2 франчайзи trial / индивидуальный аналитик", "M-K1+"),
    ("Solo", "1 990₽", "L0-L4 + 1 пользователь", "Unlimited", "P1 опытный аналитик", "M-K3+"),
    ("Standard", "4 900₽", "L0-L5 + 3 пользователя + Compliance", "Unlimited", "Малая команда в франшизе", "M-K4+"),
    ("Team", "12 900₽", "L0-L6 + 10 пользователей + temporal", "Unlimited", "Средняя команда", "M-K5+"),
    ("Enterprise", "от 49 000₽", "L0-L6 + self-hosted + custom + SLA", "Unlimited", "Крупные франшизы / enterprise", "M-K6+"),
    ("8.5-Ready Audit", "9 900-49 000₽ единоразово", "Standalone offering", "1", "Прединг апгрейда на 8.5", "M-K5+"),
    ("Franchise Bulk", "990₽/токен (от 100)", "Per-config audit", "Bulk", "Партнёрские франшизы", "M-K6+"),
    ("Self-Hosted License", "250-800k₽/год", "Полный Knowledge Layer", "Unlimited internal", "Крупные франшизы / гос (КИИ)", "M-K6+"),
]

# ============================================================
# BUILD WORKBOOK
# ============================================================
wb = Workbook()

# ============================================================
# Лист 1 — FINDINGS
# ============================================================
ws = wb.active
ws.title = "Findings"

headers = [
    "ID", "Уровень / Категория", "Тип", "Приоритет",
    "Заголовок", "Описание (что это и зачем)",
    "Зрелость понимания",
    "Готовое (что использовать)", "Что нужно построить",
    "Зависимости", "Усилия", "Дней", "Milestone",
    "Бизнес-эффект", "Источник", "Комментарий пользователя",
]
ws.append(headers)
for f in FINDINGS:
    ws.append(list(f))

# Header style
for col_idx in range(1, len(headers) + 1):
    c = ws.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws.row_dimensions[1].height = 36

# Data
for row_idx in range(2, ws.max_row + 1):
    for col_idx in range(1, len(headers) + 1):
        c = ws.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
        if col_idx in (1, 3, 4, 7, 11, 12, 13):
            c.alignment = ALIGN_CENTER

    # Color level (col 2)
    lvl = str(ws.cell(row=row_idx, column=2).value or "").strip()
    if lvl in LEVEL_COLOR:
        c = ws.cell(row=row_idx, column=2)
        c.fill = PatternFill("solid", start_color=LEVEL_COLOR[lvl])
        c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)

    # Color priority (col 4)
    prio = str(ws.cell(row=row_idx, column=4).value or "").strip()
    if prio in SEV:
        bg, fg = SEV[prio]
        c = ws.cell(row=row_idx, column=4)
        c.fill = PatternFill("solid", start_color=bg)
        c.font = Font(name="Arial", bold=True, color=fg, size=10)

    # Stripe
    if row_idx % 2 == 0:
        for col_idx in (1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16):
            cell = ws.cell(row=row_idx, column=col_idx)
            if not cell.fill or cell.fill.fgColor.rgb in (None, "00000000"):
                cell.fill = PatternFill("solid", start_color="FFF9FAFB")

    # Comment column yellow
    ws.cell(row=row_idx, column=16).fill = COMMENT_FILL

widths = {
    "A": 8, "B": 16, "C": 11, "D": 10, "E": 38, "F": 55,
    "G": 15, "H": 32, "I": 42, "J": 18, "K": 9, "L": 7,
    "M": 9, "N": 38, "O": 26, "P": 40,
}
for col, w in widths.items():
    ws.column_dimensions[col].width = w

ws.freeze_panes = "B2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"

# ============================================================
# Лист 2 — УРОВНИ
# ============================================================
ws2 = wb.create_sheet("Уровни понимания")
ws2.append(["Уровень", "Название", "Что значит", "Технологии",
            "Источники данных", "Findings (этот лист)", "Где сейчас рынок"])
for r in LEVELS:
    ws2.append(list(r))

for col_idx in range(1, 8):
    c = ws2.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws2.row_dimensions[1].height = 36

level_full = {
    "L0": "L0 Lexical",
    "L1": "L1 Structural",
    "L2": "L2 Relational",
    "L3": "L3 Semantic",
    "L4": "L4 Behavioral",
    "L5": "L5 Normative",
    "L6": "L6 Predictive",
}
for row_idx in range(2, ws2.max_row + 1):
    for col_idx in range(1, 8):
        c = ws2.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
    lvl_short = str(ws2.cell(row=row_idx, column=1).value).strip()
    lvl_key = level_full.get(lvl_short)
    if lvl_key and lvl_key in LEVEL_COLOR:
        c = ws2.cell(row=row_idx, column=1)
        c.fill = PatternFill("solid", start_color=LEVEL_COLOR[lvl_key])
        c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)
        c.alignment = ALIGN_CENTER
    if row_idx % 2 == 0:
        for col_idx in (2, 3, 4, 5, 6, 7):
            cell = ws2.cell(row=row_idx, column=col_idx)
            cell.fill = PatternFill("solid", start_color="FFF9FAFB")

widths2 = {"A": 6, "B": 16, "C": 45, "D": 32, "E": 28, "F": 38, "G": 32}
for col, w in widths2.items():
    ws2.column_dimensions[col].width = w
for r in range(2, ws2.max_row + 1):
    ws2.row_dimensions[r].height = 75

# ============================================================
# Лист 3 — USE CASES
# ============================================================
ws3 = wb.create_sheet("Use Cases")
ws3.append(["UC", "Уровень", "Сценарий", "Как работает",
            "Бизнес-эффект", "Связанные Findings"])
for r in USE_CASES:
    ws3.append(list(r))

for col_idx in range(1, 7):
    c = ws3.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws3.row_dimensions[1].height = 32

for row_idx in range(2, ws3.max_row + 1):
    for col_idx in range(1, 7):
        c = ws3.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
        if col_idx in (1, 2):
            c.alignment = ALIGN_CENTER
    lvl_short = str(ws3.cell(row=row_idx, column=2).value).strip()
    lvl_key = level_full.get(lvl_short)
    if lvl_key and lvl_key in LEVEL_COLOR:
        c = ws3.cell(row=row_idx, column=2)
        c.fill = PatternFill("solid", start_color=LEVEL_COLOR[lvl_key])
        c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)
    if row_idx % 2 == 0:
        for col_idx in (1, 3, 4, 5, 6):
            cell = ws3.cell(row=row_idx, column=col_idx)
            if not cell.fill or cell.fill.fgColor.rgb in (None, "00000000"):
                cell.fill = PatternFill("solid", start_color="FFF9FAFB")

widths3 = {"A": 9, "B": 8, "C": 42, "D": 70, "E": 38, "F": 22}
for col, w in widths3.items():
    ws3.column_dimensions[col].width = w
for r in range(2, ws3.max_row + 1):
    ws3.row_dimensions[r].height = 60

# ============================================================
# Лист 4 — TECH STACK
# ============================================================
ws4 = wb.create_sheet("Tech Stack")
ws4.append(["Компонент", "Решение",
            "Почему", "Альтернативы / Контекст", "Размер / Cost"])
for r in TECH:
    ws4.append(list(r))

for col_idx in range(1, 6):
    c = ws4.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws4.row_dimensions[1].height = 32

for row_idx in range(2, ws4.max_row + 1):
    for col_idx in range(1, 6):
        c = ws4.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
    if row_idx % 2 == 0:
        for col_idx in range(1, 6):
            cell = ws4.cell(row=row_idx, column=col_idx)
            cell.fill = PatternFill("solid", start_color="FFF9FAFB")

widths4 = {"A": 22, "B": 36, "C": 52, "D": 42, "E": 18}
for col, w in widths4.items():
    ws4.column_dimensions[col].width = w
for r in range(2, ws4.max_row + 1):
    ws4.row_dimensions[r].height = 60

# ============================================================
# Лист 5 — ROADMAP
# ============================================================
ws5 = wb.create_sheet("Roadmap")
ws5.append(["Milestone", "Название", "Длительность", "Целевая дата",
            "Содержание", "Связанные Findings"])
for r in ROADMAP:
    ws5.append(list(r))

for col_idx in range(1, 7):
    c = ws5.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws5.row_dimensions[1].height = 32

for row_idx in range(2, ws5.max_row + 1):
    for col_idx in range(1, 7):
        c = ws5.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
        if col_idx == 1:
            c.font = DATA_FONT_BOLD
            c.fill = PatternFill("solid", start_color="FF111827")
            c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=11)
            c.alignment = ALIGN_CENTER
    if row_idx % 2 == 0:
        for col_idx in range(2, 7):
            cell = ws5.cell(row=row_idx, column=col_idx)
            cell.fill = PatternFill("solid", start_color="FFF9FAFB")

widths5 = {"A": 10, "B": 32, "C": 14, "D": 16, "E": 75, "F": 38}
for col, w in widths5.items():
    ws5.column_dimensions[col].width = w
for r in range(2, ws5.max_row + 1):
    ws5.row_dimensions[r].height = 110

# ============================================================
# Лист 6 — PRICING
# ============================================================
ws6 = wb.create_sheet("Pricing & GTM")
for r in PRICING:
    ws6.append(list(r))

for col_idx in range(1, 7):
    c = ws6.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER
ws6.row_dimensions[1].height = 32

for row_idx in range(2, ws6.max_row + 1):
    for col_idx in range(1, 7):
        c = ws6.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_WRAP
        if col_idx in (1, 2, 4, 6):
            c.alignment = ALIGN_CENTER
    if row_idx % 2 == 0:
        for col_idx in range(1, 7):
            cell = ws6.cell(row=row_idx, column=col_idx)
            cell.fill = PatternFill("solid", start_color="FFF9FAFB")

widths6 = {"A": 18, "B": 22, "C": 30, "D": 14, "E": 38, "F": 14}
for col, w in widths6.items():
    ws6.column_dimensions[col].width = w
for r in range(2, ws6.max_row + 1):
    ws6.row_dimensions[r].height = 45

# ============================================================
# Лист 7 — Сводка
# ============================================================
ws7 = wb.create_sheet("Сводка")
ws7.append(["Категория / Уровень", "P0", "P1", "P2", "P3",
            "Всего", "Сумма дней"])

cats_order = []
for f in FINDINGS:
    cat = f[1]
    if cat not in cats_order:
        cats_order.append(cat)

for cat in cats_order:
    row_data = [cat]
    for prio in ["P0", "P1", "P2", "P3"]:
        cnt = sum(1 for f in FINDINGS if f[1] == cat and f[3] == prio)
        row_data.append(cnt)
    total_cnt = sum(1 for f in FINDINGS if f[1] == cat)
    total_days = sum(f[11] for f in FINDINGS if f[1] == cat)
    row_data.append(total_cnt)
    row_data.append(total_days)
    ws7.append(row_data)

ws7.append([
    "ИТОГО",
    sum(1 for f in FINDINGS if f[3] == "P0"),
    sum(1 for f in FINDINGS if f[3] == "P1"),
    sum(1 for f in FINDINGS if f[3] == "P2"),
    sum(1 for f in FINDINGS if f[3] == "P3"),
    len(FINDINGS),
    sum(f[11] for f in FINDINGS),
])

for col_idx in range(1, 8):
    c = ws7.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER

for row_idx in range(2, ws7.max_row + 1):
    for col_idx in range(1, 8):
        c = ws7.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.border = BORDER
        c.alignment = ALIGN_CENTER if col_idx > 1 else Alignment(vertical="center")
    lvl = str(ws7.cell(row=row_idx, column=1).value).strip()
    if lvl in LEVEL_COLOR:
        c = ws7.cell(row=row_idx, column=1)
        c.fill = PatternFill("solid", start_color=LEVEL_COLOR[lvl])
        c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)
    if row_idx == ws7.max_row:
        for col_idx in range(1, 8):
            c = ws7.cell(row=row_idx, column=col_idx)
            c.fill = HEADER_FILL
            c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)

widths7 = {"A": 22, "B": 8, "C": 8, "D": 8, "E": 8, "F": 10, "G": 14}
for col, w in widths7.items():
    ws7.column_dimensions[col].width = w

# ============================================================
# Лист 8 — Легенда
# ============================================================
ws8 = wb.create_sheet("Легенда")
legend = [
    ["Уровень / Категория", "Значение"],
    ["L0 Lexical", "Знает имена (поиск)"],
    ["L1 Structural", "Знает структуру (метаданные)"],
    ["L2 Relational", "Знает связи (графы)"],
    ["L3 Semantic", "Понимает смысл (embeddings)"],
    ["L4 Behavioral", "Понимает 'почему' (diagnose)"],
    ["L5 Normative", "Знает стандарты (ИТС)"],
    ["L6 Predictive", "Предсказывает (temporal, what-if)"],
    ["Pipeline", "Инфраструктура (storage, indexing, retrieval)"],
    ["UX", "Frontend-карточки и взаимодействие"],
    ["Cross-cutting", "Сквозные темы (privacy, telemetry, MCP)"],
    ["Pricing/GTM", "Монетизация и каналы продаж"],
    ["", ""],
    ["Приоритет", "Значение"],
    ["P0", "Foundation / Critical. Без этого следующие уровни не работают."],
    ["P1", "Highly valuable. В первом коммерческом релизе."],
    ["P2", "Important. В roadmap, но не блокирует launch."],
    ["P3", "Nice-to-have. Долгосрочный backlog."],
    ["", ""],
    ["Зрелость понимания", "По шкале Bloom-like (L0→L6)"],
    ["Lexical", "Самый базовый: поиск по строке"],
    ["Structural", "Знание структуры"],
    ["Relational", "Графы и связи"],
    ["Semantic", "Понимание смысла"],
    ["Behavioral", "Понимание поведения"],
    ["Normative", "Знание стандартов"],
    ["Predictive", "Предсказание последствий"],
    ["", ""],
    ["Тип Finding", "Значение"],
    ["Component", "Технический компонент для построения"],
    ["Use Case", "Сценарий 'вопрос пользователя → ответ системы'"],
    ["Decision", "Архитектурное / продуктовое решение"],
    ["", ""],
    ["Усилия", "Дней"],
    ["S (Small)", "0.5 дня"],
    ["M (Medium)", "2 дня"],
    ["L (Large)", "5 дней"],
    ["XL (Extra Large)", "10 дней"],
    ["", ""],
    ["Поле 'Комментарий пользователя'", "Жёлтый фон. Пишите свои мысли, приоритеты, отказы. Я подхвачу при следующей итерации."],
]

for row_data in legend:
    ws8.append(row_data)

for col_idx in (1, 2):
    c = ws8.cell(row=1, column=col_idx)
    c.fill = HEADER_FILL
    c.font = HEADER_FONT
    c.alignment = HEADER_ALIGN
    c.border = BORDER

for row_idx in range(2, ws8.max_row + 1):
    for col_idx in (1, 2):
        c = ws8.cell(row=row_idx, column=col_idx)
        c.font = DATA_FONT
        c.alignment = ALIGN_WRAP
        c.border = BORDER
    lvl = str(ws8.cell(row=row_idx, column=1).value or "").strip()
    if lvl in LEVEL_COLOR:
        c = ws8.cell(row=row_idx, column=1)
        c.fill = PatternFill("solid", start_color=LEVEL_COLOR[lvl])
        c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)
    if lvl in SEV:
        bg, fg = SEV[lvl]
        c = ws8.cell(row=row_idx, column=1)
        c.fill = PatternFill("solid", start_color=bg)
        c.font = Font(name="Arial", bold=True, color=fg, size=10)

ws8.column_dimensions["A"].width = 32
ws8.column_dimensions["B"].width = 75

wb.save(OUT)
print(f"Saved: {OUT}")
print(f"Findings: {len(FINDINGS)}")
print(f"Use Cases: {len(USE_CASES)}")
print(f"Tech components: {len(TECH)}")
print(f"Roadmap milestones: {len(ROADMAP)}")
print(f"Pricing tiers: {len(PRICING)-1}")
print(f"Levels: {len(LEVELS)}")
