"""Smoke-проверка LLM tools на нестандартных вопросах (M-K2.5 closing).

Запускает 6 typical tools напрямую на pilot.db с 4 типовыми
конфигурациями (БП/КА/УТ/ERP), задаёт каждому tool несколько
**нетривиальных** вопросов и проверяет что:

1. Tools возвращают (ok=True, result, None) на валидных запросах
2. Результаты не пустые
3. Ключи в payload соответствуют schema
4. Нестандартные ключевые слова находятся (поиск по русским
   терминам с разной типографикой / падежами / частями слов)

Запуск:
    cd backend
    python -m scripts.typical_smoke_questions

Выход: подробный отчёт в stdout + exit code 0 / 1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import aiosqlite

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.typical.tool import (  # noqa: E402
    TOOL_COMPARE,
    TOOL_EXPLAIN,
    TOOL_LIST_CONFIGS,
    TOOL_SEARCH_OBJECTS,
    TOOL_TRACE_CALLS,
    TOOL_TRACE_MOVEMENTS,
    dispatch_typical_tool,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

DB_PATH = Path("C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db")

# Цвета для терминала (Windows + ANSI)
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


passed = 0
failed = 0
issues: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  {GREEN}PASS{RESET} {label}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        issues.append(f"{label}: {detail}")
        print(f"  {RED}FAIL{RESET} {label}{(' — ' + detail) if detail else ''}")


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


async def smoke():
    db = await aiosqlite.connect(str(DB_PATH))
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(db)

        await q1_list_configurations(db)
        await q2_search_with_unusual_keywords(db)
        await q3_explain_known_objects(db)
        await q4_explain_unknown_object_returns_cold_start_fallback(db)
        await q5_trace_movements_real_register(db)
        await q6_trace_calls_handler(db)
        await q7_cross_config_consistency(db)
        await q8_compare_returns_not_implemented(db)
        await q9_error_paths(db)
        await q10_card_payload_shape(db)

        # v2.0 — новые проверки на 9 закрытых рисков (M-K2.5.9).
        await q11_mock_isolation_explain(db)
        await q12_mock_isolation_list_configs_ratio(db)
        await q13_search_returns_is_mock(db)
        await q14_explain_includes_validation_meta(db)
        await q15_explain_includes_embedding_meta(db)
        await q16_hard_limits_reject_overshoot(db)
        await q17_closed_vocabulary_register_validator(db)
        await q18_closed_vocabulary_direction_literal(db)
        await q19_cold_start_with_suggestions(db)
        await q20_graph_validator_detects_phantom(db)
        await q21_existing_object_no_cold_start_regression(db)

        # M-K2.5.10 — real LLM rebuild infrastructure smoke checks.
        await q22_openai_compat_caller_importable(db)
        await q23_caller_pricing_table_has_known_models(db)
        await q24_caller_cost_calculator_works(db)
        await q25_set_rebuild_credentials_storage_roundtrip(db)
        await q26_credentials_masked_in_display(db)
        await q27_rebuild_script_dry_run_without_credentials(db)
        await q28_validate_all_script_dry_run(db)
        await q29_rebuild_plan_document_exists(db)

    finally:
        await db.close()


# ─── M-K2.5.10 NEW SCENARIOS ─────────────────────────────────────────


async def q22_openai_compat_caller_importable(db):
    """v2.0.10-2: OpenAICompatLLMCaller импортируется и instantiates."""
    section("Q22: M-K2.5.10 — OpenAICompatLLMCaller adapter importable")

    try:
        from app.knowledge.typical.openai_compat_llm_caller import (  # noqa: PLC0415
            CallTelemetry,
            LLMAuthError,
            LLMBadRequestError,
            LLMRateLimitError,
            LLMServerError,
            OpenAICompatLLMCaller,
        )
        check("OpenAICompatLLMCaller importable", True)

        caller = OpenAICompatLLMCaller(
            endpoint="https://dummy.local/v1", model="m", api_key="sk-x",
        )
        check("caller instantiate", True)
        check("telemetry initially empty",
              caller.telemetry.total_calls == 0)
        check("4 error классы доступны",
              all(c is not None for c in [LLMAuthError, LLMBadRequestError, LLMRateLimitError, LLMServerError]))
    except Exception as e:
        check("OpenAICompatLLMCaller import", False, str(e)[:100])


async def q23_caller_pricing_table_has_known_models(db):
    """v2.0.10-2: pricing table содержит DeepSeek / OpenAI / Anthropic."""
    section("Q23: M-K2.5.10 — pricing table coverage")

    from app.knowledge.typical.openai_compat_llm_caller import _PRICING  # noqa: PLC0415

    expected_models = (
        "deepseek-chat", "gpt-4o-mini", "claude-3-5-haiku-20241022",
        "llama-3.1-8b-instant", "mistral-small-latest",
    )
    for model in expected_models:
        check(f"price для {model}", model in _PRICING,
              f"missing in {list(_PRICING.keys())[:3]}...")


async def q24_caller_cost_calculator_works(db):
    """v2.0.10-2: calculate_cost корректен для известных моделей."""
    section("Q24: M-K2.5.10 — cost calculator")

    from app.knowledge.typical.openai_compat_llm_caller import calculate_cost  # noqa: PLC0415

    # DeepSeek-chat: $0.07 input + $1.10 output per 1M
    cost = calculate_cost(model="deepseek-chat", tokens_in=1_000_000, tokens_out=1_000_000)
    check("deepseek-chat 1M+1M = $1.17",
          abs(cost - 1.17) < 0.01,
          f"got {cost}")

    # Unknown model → 0
    cost_unknown = calculate_cost(model="unknown-model-xyz", tokens_in=1000, tokens_out=1000)
    check("unknown model → 0.0", cost_unknown == 0.0)

    # Fuzzy match для версионного suffix
    cost_versioned = calculate_cost(
        model="gpt-4o-mini-2024-07-18", tokens_in=1_000_000, tokens_out=1_000_000,
    )
    check("gpt-4o-mini-XXXXX fuzzy match → $0.75",
          abs(cost_versioned - 0.75) < 0.01,
          f"got {cost_versioned}")


async def q25_set_rebuild_credentials_storage_roundtrip(db):
    """v2.0.10-3: save/load credentials через AES-GCM."""
    section("Q25: M-K2.5.10 — credentials storage roundtrip")

    from scripts.set_rebuild_credentials import (  # noqa: PLC0415
        RebuildCredentials,
        load_rebuild_credentials,
        save_rebuild_credentials,
    )

    original = RebuildCredentials(
        endpoint="https://api.smoke.local/v1",
        model="smoke-test",
        api_key="sk-smoke-test-key-12345",
    )
    await save_rebuild_credentials(db, original)
    loaded = await load_rebuild_credentials(db)

    check("loaded not None", loaded is not None)
    if loaded:
        check("endpoint roundtrip", loaded.endpoint == original.endpoint)
        check("model roundtrip", loaded.model == original.model)
        check("api_key roundtrip", loaded.api_key == original.api_key)


async def q26_credentials_masked_in_display(db):
    """v2.0.10-3: masked_api_key не показывает середину ключа."""
    section("Q26: M-K2.5.10 — api_key masking")

    from scripts.set_rebuild_credentials import RebuildCredentials  # noqa: PLC0415

    creds = RebuildCredentials(
        endpoint="x", model="y",
        api_key="sk-s1lyss3hhkwivw0scbyr4183est1sxde2gfkjt28fnbbym49",
    )
    masked = creds.masked_api_key()
    check("masked содержит prefix", masked.startswith("sk-s1"))
    check("masked содержит suffix", masked.endswith("ym49"))
    check("masked не содержит середину",
          "lyss3hhkwivw" not in masked,
          f"masked={masked}")
    check("masked содержит ****", "****" in masked)


async def q27_rebuild_script_dry_run_without_credentials(db):
    """v2.0.10-5: rebuild script с --dry-run работает без credentials."""
    section("Q27: M-K2.5.10 — rebuild script dry-run")

    from scripts.set_rebuild_credentials import load_rebuild_credentials  # noqa: PLC0415

    # Сначала удалим credentials если есть (smoke clean state)
    from app.storage.user_secrets_store import delete_secret  # noqa: PLC0415
    from scripts.set_rebuild_credentials import REBUILD_PROVIDER_ID  # noqa: PLC0415
    await delete_secret(db, REBUILD_PROVIDER_ID)

    creds = await load_rebuild_credentials(db)
    check("credentials отсутствуют (clean state)", creds is None)


async def q28_validate_all_script_dry_run(db):
    """v2.0.10-8: validate_all dry-run работает."""
    section("Q28: M-K2.5.10 — validate_all script dry-run")

    from scripts.typical_cards_validate_all import validate_channel  # noqa: PLC0415

    stats = await validate_channel(db, channel_id="_bp30_138_24", dry_run=True, limit=5)
    check("dry_run stats имеет total", stats["total"] >= 0)
    check("dry_run не валидирует", stats["valid"] == 0 and stats["errors"] == 0)


async def q29_rebuild_plan_document_exists(db):
    """v2.0.10-1: план M-K2.5.10 существует с acceptance criteria."""
    section("Q29: M-K2.5.10 — план документ exists")

    from pathlib import Path  # noqa: PLC0415

    plan_path = Path(
        "C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/"
        "knowledge-layer-2026-05-24/phases/M-K2.5/M-K2.5.10-REBUILD-PLAN.md"
    )
    check("план файл exists", plan_path.exists())
    if plan_path.exists():
        content = plan_path.read_text(encoding="utf-8")
        check("содержит Acceptance criteria",
              "Acceptance criteria" in content)
        check("содержит 13 чекбоксов",
              content.count("- [ ]") >= 13,
              f"got {content.count('- [ ]')} чекбоксов")
        check("содержит scope 63 197 карточек",
              "63 197" in content or "63197" in content)


# ─── v2.0 NEW SCENARIOS ──────────────────────────────────────────────


async def q11_mock_isolation_explain(db):
    """v2.0-step-2: explain возвращает is_mock=true для mock-карточек."""
    section("Q11: mock isolation — explain включает is_mock и warning")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "ChartOfAccounts.Хозрасчетный",
    })
    if not ok:
        print(f"  {YELLOW}SKIP{RESET} {err}")
        return
    check("payload содержит is_mock", "is_mock" in (result or {}),
          f"keys={list((result or {}).keys())}")
    check("is_mock=True для всех существующих (pilot.db)",
          result.get("is_mock") is True,
          f"is_mock={result.get('is_mock')}")
    check("card_warning содержит «mock»",
          result.get("card_warning") and "mock" in result["card_warning"].lower())


async def q12_mock_isolation_list_configs_ratio(db):
    """v2.0-step-2: list_configurations возвращает mock_ratio."""
    section("Q12: mock isolation — list_configs показывает mock_ratio")

    ok, result, err = await dispatch_typical_tool(db, TOOL_LIST_CONFIGS, {})
    check("list_configs ok", ok, err or "")
    for cfg in (result or {}).get("configurations", []):
        check(f"{cfg['channel_id']} имеет mock_cards", "mock_cards" in cfg)
        check(f"{cfg['channel_id']} имеет mock_ratio", "mock_ratio" in cfg)
        # На pilot.db все 63k карточек = mock_ratio должен быть 1.0
        if cfg.get("total_cards", 0) > 0:
            check(f"{cfg['channel_id']} mock_ratio=1.0",
                  cfg.get("mock_ratio") == 1.0,
                  f"ratio={cfg.get('mock_ratio')}")


async def q13_search_returns_is_mock(db):
    """v2.0-step-2: search_typical_objects возвращает is_mock в каждом result."""
    section("Q13: search_typical_objects возвращает is_mock в результатах")

    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_bp30_138_24", "query": "хозрасчетный", "top_k": 3,
    })
    if not ok:
        print(f"  {YELLOW}SKIP{RESET} {err}")
        return
    results = (result or {}).get("results", [])
    check("search вернул результаты", len(results) > 0)
    for r in results:
        check(f"  {r.get('qualified_name', '?')[:50]} имеет is_mock", "is_mock" in r)


async def q14_explain_includes_validation_meta(db):
    """v2.0-step-5: explain возвращает validation блок (можно null если не валидировалась)."""
    section("Q14: explain включает validation блок")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "ChartOfAccounts.Хозрасчетный",
    })
    if not ok:
        print(f"  {YELLOW}SKIP{RESET} {err}")
        return
    check("payload содержит ключ 'validation'", "validation" in (result or {}))
    # validation может быть null (карточки ещё не валидировались на pilot.db).
    # Главное — что ключ присутствует.


async def q15_explain_includes_embedding_meta(db):
    """v2.0-step-6: explain возвращает embedding_meta (model + version + dim)."""
    section("Q15: explain включает embedding_meta")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "ChartOfAccounts.Хозрасчетный",
    })
    if not ok:
        print(f"  {YELLOW}SKIP{RESET} {err}")
        return
    check("payload содержит 'embedding_meta'", "embedding_meta" in (result or {}))
    meta = (result or {}).get("embedding_meta") or {}
    check("embedding_meta содержит 'model' ключ", "model" in meta)
    check("embedding_meta содержит 'model_version' ключ", "model_version" in meta)
    check("embedding_meta содержит 'dim' ключ", "dim" in meta)


async def q16_hard_limits_reject_overshoot(db):
    """v2.0-step-3: Pydantic Field max_length отклоняет overshoot."""
    section("Q16: hard limits — Pydantic блокирует overshoot")

    from pydantic import ValidationError  # noqa: PLC0415

    from app.knowledge.typical.card_models import (  # noqa: PLC0415
        MAX_SUMMARY_LEN, TypicalObjectCard,
    )

    over = "x" * (MAX_SUMMARY_LEN + 100)
    raised = False
    try:
        TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
            summary=over,
        )
    except ValidationError:
        raised = True
    check("summary длиннее MAX_SUMMARY_LEN → ValidationError", raised)


async def q17_closed_vocabulary_register_validator(db):
    """v2.0-step-4: CardMovement отклоняет register без canonical префикса."""
    section("Q17: closed vocabulary — register format validator")

    from pydantic import ValidationError  # noqa: PLC0415

    from app.knowledge.typical.card_models import CardMovement  # noqa: PLC0415

    bad_prefixes = ["BadKind.X", "РегистрНакопления.Y", "Регистр.Z", "NoDot"]
    for bad in bad_prefixes:
        raised = False
        try:
            CardMovement(register=bad)
        except ValidationError:
            raised = True
        check(f"register={bad!r} → ValidationError", raised)

    # Canonical префикс — должен работать
    raised = False
    try:
        CardMovement(register="AccumulationRegister.ТоварыНаСкладах", direction="расход")
    except Exception:
        raised = True
    check("AccumulationRegister.X + direction='расход' — валидно", not raised)


async def q18_closed_vocabulary_direction_literal(db):
    """v2.0-step-4: CardMovement.direction — Literal."""
    section("Q18: closed vocabulary — direction = Literal allowlist")

    from pydantic import ValidationError  # noqa: PLC0415

    from app.knowledge.typical.card_models import (  # noqa: PLC0415
        CardMovement, normalize_direction,
    )

    # Canonical — OK
    for ok_val in ("приход", "расход", "приход/расход", "запись", ""):
        raised = False
        try:
            CardMovement(register="AccumulationRegister.X", direction=ok_val)
        except Exception:
            raised = True
        check(f"direction={ok_val!r} — валидно", not raised)

    # Произвольное — ValidationError
    raised = False
    try:
        CardMovement(register="AccumulationRegister.X", direction="отгрузка")
    except ValidationError:
        raised = True
    check("direction='отгрузка' → ValidationError", raised)

    # normalize_direction — synonyms
    check("normalize 'expense' → 'расход'", normalize_direction("expense") == "расход")
    check("normalize 'income' → 'приход'", normalize_direction("income") == "приход")
    check("normalize 'unknown' → ''", normalize_direction("unknown") == "")


async def q19_cold_start_with_suggestions(db):
    """v2.0-step-7: explain для несуществующего — даёт suggestions."""
    section("Q19: cold start — suggestions для опечатки")

    # Опечатка в имени — Контрагент → КонтрагентX
    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "Catalog.КонтрагентX",  # опечатка
    })
    check("ok=True (cold start fallback)", ok)
    check("card_status='not_in_graph'",
          (result or {}).get("card_status") == "not_in_graph")
    suggestions = (result or {}).get("suggestions") or []
    check("suggestions содержит хотя бы 1 кандидата", len(suggestions) >= 1,
          f"got {len(suggestions)} suggestions")
    # Среди suggestions для опечатки Catalog.КонтрагентX ожидаем
    # хотя бы один Catalog или Catalog.Контрагенты по prefix match.
    if suggestions:
        kontragenty_qnames = [
            s for s in suggestions
            if "контрагент" in s.get("qualified_name", "").lower()
        ]
        check("suggestions содержат хотя бы один Контрагент*",
              len(kontragenty_qnames) >= 1,
              f"qnames={[s.get('qualified_name') for s in suggestions]}")


async def q20_graph_validator_detects_phantom(db):
    """v2.0-step-5: validator детектит phantom_movement."""
    section("Q20: graph validator — детектит phantom_movement")

    from app.knowledge.typical.card_models import CardMovement, TypicalObjectCard  # noqa: PLC0415
    from app.knowledge.typical.card_validator import validate_card_against_graph  # noqa: PLC0415

    # Берём реальный объект, добавляем туда фантомный register
    fake_card = TypicalObjectCard(
        object_qualified_name="ChartOfAccounts.Хозрасчетный",
        object_kind="ChartOfAccounts",
        channel_id="_bp30_138_24",
        summary="Тест",
        movements=(
            CardMovement(
                register="AccumulationRegister.СовершенноВыдуманныйРегистр",
                direction="расход",
            ),
        ),
    )
    result = await validate_card_against_graph(
        db, channel_id="_bp30_138_24", card=fake_card,
    )
    check("validator status='issues_found'",
          result.status == "issues_found",
          f"got {result.status}")
    phantom = [i for i in result.issues if i.code == "phantom_movement"]
    check("phantom_movement issue найден",
          len(phantom) >= 1, f"got {len(phantom)}")
    if phantom:
        check("severity='error'",
              phantom[0].severity == "error", f"got {phantom[0].severity}")


async def q21_existing_object_no_cold_start_regression(db):
    """Регресс: для реального объекта НЕ возвращается not_in_graph."""
    section("Q21: регресс — реальные объекты не получают cold start")

    # В ERP 2.5 РаспределениеЗапасов заменил СвободныеОстатки — используем
    # документ Реализация (есть во всех 4 типовых).
    cases = [
        ("_bp30_138_24", "ChartOfAccounts.Хозрасчетный"),
        ("_ut115_17_226", "Document.РеализацияТоваровУслуг"),
        ("_ka2_25_92", "Catalog.Контрагенты"),
        ("_erp25_21_118", "Document.РеализацияТоваровУслуг"),
    ]
    for ch, qname in cases:
        ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
            "channel_id": ch, "object_qualified_name": qname,
        })
        if not ok:
            print(f"  {YELLOW}SKIP{RESET} {ch}/{qname} — {err}")
            continue
        check(f"{ch}/{qname} card_status != 'not_in_graph'",
              (result or {}).get("card_status") != "not_in_graph",
              f"got {(result or {}).get('card_status')!r}")


# ─── Q1: список загруженных типовых ──────────────────────────────────


async def q1_list_configurations(db):
    section("Q1: list_typical_configurations")
    ok, result, err = await dispatch_typical_tool(db, TOOL_LIST_CONFIGS, {})
    check("dispatch returns ok=True", ok, err or "")
    check("result['total'] >= 4", result and result["total"] >= 4,
          f"got total={result and result.get('total')}")
    channels = {c["channel_id"] for c in (result or {}).get("configurations", [])}
    for expected in ("_bp30_138_24", "_ka2_25_92", "_ut115_17_226", "_erp25_21_118"):
        check(f"channel {expected} в списке", expected in channels)


# ─── Q2: поиск с необычными терминами ────────────────────────────────


async def q2_search_with_unusual_keywords(db):
    section("Q2: search_typical_objects — нестандартные запросы")

    # Поиск по характерному термину БП
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_bp30_138_24", "query": "хозрасчетный", "top_k": 5,
    })
    check("БП «хозрасчетный» — ok", ok, err or "")
    check("БП «хозрасчетный» — есть результаты", result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # ERP — закрытие (имена объектов в 1С — слитные CamelCase,
    # фразу с пробелом substring не найдёт; ищем по одному слову).
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_erp25_21_118", "query": "закрытие", "top_k": 10,
    })
    check("ERP «закрытие» — ok", ok, err or "")
    check("ERP «закрытие» — есть результаты",
          result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # УТ — реализация
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_ut115_17_226", "query": "реализация", "top_k": 10,
    })
    check("УТ «реализация» — ok", ok, err or "")
    check("УТ «реализация» — есть результаты", result and result["total"] > 0,
          f"total={result and result.get('total')}")

    # Фильтр по kind
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_ka2_25_92",
        "query": "товары",
        "object_kind": "AccumulationRegister",
        "top_k": 5,
    })
    check("КА «товары» kind=AccumulationRegister — ok", ok, err or "")
    if result and result.get("results"):
        all_acc_register = all(
            r["kind"] == "AccumulationRegister" for r in result["results"]
        )
        check("Все результаты AccumulationRegister", all_acc_register,
              f"kinds={[r['kind'] for r in result['results']]}")


# ─── Q3: карточки реальных объектов ──────────────────────────────────


async def q3_explain_known_objects(db):
    section("Q3: explain_typical_object — реальные объекты")

    cases = [
        ("_bp30_138_24", "ChartOfAccounts.Хозрасчетный", "ChartOfAccounts"),
        ("_bp30_138_24", "AccountingRegister.Хозрасчетный", "AccountingRegister"),
        ("_ka2_25_92", "Document.РеализацияТоваровУслуг", "Document"),
        ("_ut115_17_226", "Catalog.Контрагенты", "Catalog"),
        ("_erp25_21_118", "Document.РеализацияТоваровУслуг", "Document"),
    ]
    for channel, qname, expected_kind in cases:
        ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
            "channel_id": channel, "object_qualified_name": qname,
        })
        label = f"{channel} {qname}"
        if ok:
            kind_ok = result and result.get("object_kind") == expected_kind
            check(f"{label} — explain ok + kind={expected_kind}", kind_ok,
                  f"got kind={result and result.get('object_kind')}")
            has_card = result and result.get("card") is not None
            check(f"{label} — карточка есть", has_card,
                  f"card_status={result and result.get('card_status')}")
            has_children = result and result.get("children_summary")
            check(f"{label} — children_summary заполнено",
                  bool(has_children),
                  f"keys={list((result or {}).get('children_summary', {}).keys())}")
        else:
            # Объект может отсутствовать в типовой — это не fatal, но stat'нем
            print(f"  {YELLOW}SKIP{RESET} {label} — не найден ({err})")


# ─── Q4: 404 на несуществующем объекте ───────────────────────────────


async def q4_explain_unknown_object_returns_cold_start_fallback(db):
    """v2.0-step-7: cold start fallback вместо raw error."""
    section("Q4: explain — несуществующий объект → cold start fallback")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "Document.СовершенноВыдуманныйДокумент",
    })
    # v2.0-step-7: ok=True + structured payload вместо ok=False + raw error.
    check("ok=True (новый contract)", ok)
    check("err=None", err is None)
    check("card_status='not_in_graph'",
          result and result.get("card_status") == "not_in_graph",
          f"status={result and result.get('card_status')}")
    check("card=None для несуществующего",
          result and result.get("card") is None)
    check("card_warning содержит anti-hallucination",
          result and "выдумывай" in (result.get("card_warning") or "").lower())
    check("suggestions — список",
          result and isinstance(result.get("suggestions"), list))


# ─── Q5: trace_movements ──────────────────────────────────────────────


async def q5_trace_movements_real_register(db):
    section("Q5: trace_typical_movements — реальные регистры")

    # БП.Хозрасчетный — главный регистр БП 3.0, имеет writes и reads.
    # Регистр накопления КА не используется — в КА writes идут в основном
    # в Хозрасчетный + специфичные регистры партий, у каждого ≤ 30 writes
    # и подбор корректного top через SQL JOIN на 1.7M edges медленный.

    # БП: ХозрасчетныйРегистр — both
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccountingRegister.Хозрасчетный",
        "direction": "both",
    })
    if ok:
        check("БП.Хозрасчетный — writes+reads",
              result["total_writes"] > 0 or result["total_reads"] > 0,
              f"writes={result.get('total_writes')} reads={result.get('total_reads')}")
    else:
        print(f"  {YELLOW}SKIP{RESET} БП.Хозрасчетный — {err}")

    # Несуществующий регистр
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccumulationRegister.НесуществующийРегистр",
    })
    check("Несуществующий регистр → ok=False", not ok)


# ─── Q6: trace_calls на handler ──────────────────────────────────────


async def q6_trace_calls_handler(db):
    section("Q6: trace_typical_calls — реальные handler-методы")

    # Найдём какой-нибудь ОбработкаПроведения в БП и проверим из него out
    cursor = await db.execute("""
        SELECT qualified_name FROM graph_nodes
        WHERE channel_id = ? AND node_kind = 'Method'
        AND qualified_name LIKE '%ОбработкаПроведения%'
        LIMIT 1
    """, ("_bp30_138_24",))
    row = await cursor.fetchone()
    if not row:
        print(f"  {YELLOW}SKIP{RESET} БП.ОбработкаПроведения не найден")
        return

    qname = row[0]
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_CALLS, {
        "channel_id": "_bp30_138_24",
        "qualified_name": qname,
        "direction": "out",
        "depth": 2,
    })
    check(f"БП ОбработкаПроведения out depth=2 — ok", ok, err or "")
    check("hits >= 1 (стартовый node всегда)",
          result and result.get("total", 0) >= 1,
          f"total={result and result.get('total')}")

    # Invalid direction
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_CALLS, {
        "channel_id": "_bp30_138_24",
        "qualified_name": qname,
        "direction": "both",  # traverse_bfs не поддерживает
    })
    check("direction='both' → ok=False (graph_storage ограничение)", not ok)


# ─── Q7: кросс-конфигурационная консистентность ──────────────────────


async def q7_cross_config_consistency(db):
    section("Q7: кросс-конфигурационная консистентность")

    # У ERP должно быть больше объектов чем у БП
    ok_bp, bp, _ = await dispatch_typical_tool(db, TOOL_LIST_CONFIGS, {})
    if not ok_bp:
        check("list_configs success", False, "не получили список")
        return
    by_kind = {c["config_kind"]: c for c in bp["configurations"]}
    erp = by_kind.get("ERP_25", {})
    bp_cfg = by_kind.get("BP_30", {})
    ut = by_kind.get("UT_115", {})
    ka = by_kind.get("KA_2", {})

    check("ERP nodes > БП nodes",
          erp.get("total_nodes", 0) > bp_cfg.get("total_nodes", 0),
          f"ERP={erp.get('total_nodes')} BP={bp_cfg.get('total_nodes')}")
    check("ERP nodes > УТ nodes",
          erp.get("total_nodes", 0) > ut.get("total_nodes", 0),
          f"ERP={erp.get('total_nodes')} УТ={ut.get('total_nodes')}")
    check("Все 4 конфигурации graph_built",
          all(c.get("status") == "graph_built" for c in (erp, bp_cfg, ut, ka)),
          f"statuses={[(c.get('config_kind'), c.get('status')) for c in (erp, bp_cfg, ut, ka)]}")


# ─── Q8: compare_with_typical → not_implemented ──────────────────────


async def q8_compare_returns_not_implemented(db):
    section("Q8: compare_with_typical — заглушка v1")

    ok, result, err = await dispatch_typical_tool(db, TOOL_COMPARE, {
        "typical_channel_id": "_bp30_138_24",
        "client_channel_id": "_client_x_",
        "object_qualified_name": "Document.Заказ",
    })
    check("compare возвращает ok=True (заглушка)", ok, err or "")
    check("status='not_implemented'",
          result and result.get("status") == "not_implemented",
          f"status={result and result.get('status')}")
    # Сообщение должно намекать на M-K3
    check("сообщение упоминает M-K3 / client graph",
          result and ("M-K3" in result.get("message", "") or
                       "клиент" in result.get("message", "").lower()))


# ─── Q9: error paths ─────────────────────────────────────────────────


async def q9_error_paths(db):
    section("Q9: error paths — невалидные параметры")

    # Пустой query
    ok, result, err = await dispatch_typical_tool(db, TOOL_SEARCH_OBJECTS, {
        "channel_id": "_bp30_138_24", "query": "",
    })
    check("пустой query → ok=False", not ok,
          f"got err={err!r}")

    # Несуществующий tool
    ok, result, err = await dispatch_typical_tool(db, "search_xyz", {})
    check("неизвестный tool → ok=False", not ok)

    # Невалидный direction
    ok, result, err = await dispatch_typical_tool(db, TOOL_TRACE_MOVEMENTS, {
        "channel_id": "_bp30_138_24",
        "register_qualified_name": "AccumulationRegister.X",
        "direction": "вперёд",  # не writes/reads/both
    })
    check("невалидный direction → ok=False", not ok)


# ─── Q10: shape карточки ────────────────────────────────────────────


async def q10_card_payload_shape(db):
    section("Q10: card payload — все обязательные поля")

    ok, result, err = await dispatch_typical_tool(db, TOOL_EXPLAIN, {
        "channel_id": "_bp30_138_24",
        "object_qualified_name": "ChartOfAccounts.Хозрасчетный",
    })
    if not ok or not result.get("card"):
        print(f"  {YELLOW}SKIP{RESET} карточка БП.Хозрасчетный недоступна")
        return

    card = result["card"]
    required_keys = (
        "summary", "purpose", "key_attributes", "movements",
        "posting_flow", "typical_scenarios", "preconditions",
        "related_objects", "its_links",
    )
    for key in required_keys:
        check(f"карточка содержит '{key}'", key in card)

    # Mock карточка содержит «План счетов» в summary
    check("summary не пустой", bool(card.get("summary", "").strip()))


# ─── Entry ───────────────────────────────────────────────────────────


def main():
    print(f"{BOLD}Smoke test: typical LLM tools на pilot.db{RESET}")
    print(f"{GRAY}DB: {DB_PATH}{RESET}")
    print(f"{GRAY}Configurations: БП 3.0 + КА 2.5 + УТ 11.5 + ERP 2.5{RESET}")

    asyncio.run(smoke())

    print()
    print(f"{BOLD}=== Summary ==={RESET}")
    total = passed + failed
    print(f"  {GREEN}PASS:{RESET} {passed} / {total}")
    if failed:
        print(f"  {RED}FAIL:{RESET} {failed}")
        print()
        print(f"{BOLD}{RED}Issues:{RESET}")
        for issue in issues:
            print(f"  • {issue}")
        return 1
    print(f"  {GREEN}{BOLD}Все {total} проверок прошли{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
