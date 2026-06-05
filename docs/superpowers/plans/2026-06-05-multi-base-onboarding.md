# Multi-base онбординг — авто-детекция конфигурации + анти-thrashing. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** При подключении новой клиентской базы по MCP она за секунды корректно сопоставляется со своей типовой (КА/УТ/ERP/БП/…), конфо-зависимые ответы сразу верные, без 4-минутного молочения и без дампа метаданных.

**Architecture:** Источник дизайна — `~/.gstack/projects/nikitakhvorostov1912-beep-analyst-workspace-design/Khvorostov-feature-m-k3-relational-cfe-design-20260605-200212.md` (APPROVED, Approach B). Семь фаз: (1) дискриминативная детекция КА⊃УТ, (2) миграция v24 + хранение источника, (3) live-пробы детекции через MCP, (4) авто-детект на коннекте + confidence-gate, (5) `loop.py` инжект конфы в промпт + buddy-аргументы + кап typical-вызовов + стиль ответа, (6) фронт-бейдж + override + состояния, (7) фикс бага индексера `get_metadata`. Фазы 1→2→3→4→5 строго последовательны по зависимостям; 6 зависит от 2+4; 7 независима (отдельный PR-кандидат).

**Tech Stack:** Backend FastAPI + Pydantic v2 + aiosqlite + pytest/pytest-asyncio (Python 3.12, venv `backend/.venv`). Frontend Next.js 15 + React 19 + Vitest 4 + Tailwind 4. MCP HTTP Streamable (1С MCP Toolkit). LLM OpenAI-compatible.

---

## Setup (один раз перед стартом)

- Backend-команды выполняются из `backend/` с активированным venv:
  - PowerShell: `backend\.venv\Scripts\Activate.ps1`
  - Проверка: `python -c "import aiosqlite, fastapi; print('ok')"`
- Frontend-команды выполняются из `frontend/`.
- Все коммиты атомарные. На ветке `feature/m-k3-relational-cfe`.
- Перед стартом фазы 4+ держи поднятыми сервера: `pwsh .claude/skills/awd-dev-up/scripts/up.ps1`.

## Ключевые проектные факты (вшиты в задачи ниже — не перепроверять на лету)

- `CURRENT_VERSION = 23` в `app/storage/migrations.py` → следующая свободная миграция **v24**.
- Существующий тест `test_known_configurations_have_distinct_signatures` проверяет ТОЛЬКО `characteristic_objects` → новое поле `discriminative_objects` его НЕ ломает.
- `mcp_connections.configuration` хранит `display_name` детекции («КА 2.5»), не typical-имя. Это сохраняется.
- detection-ключи (`ka_2_5`) ≠ typical `config_kind` (`KA_2`). Маппинг — новый.
- typical channel_id = `reserved_channel_id(kind, version)` (напр. `_ka2_25_92`). Берётся запросом из `typical_configurations`.
- `buddy.search_its`/`buddy.fetch_its` идут через `pool.client_for` → `_execute_mcp_tool` в `loop.py` (строки ~1959–1997). Инжект `configuration` — в блоке `if tool_name.startswith("buddy."):`.
- `MAX_BUDDY_CALLS_PER_TURN = 3` уже есть — НЕ трогать. Кап `search_typical_objects` — НОВЫЙ.
- `_build_full_system_prompt` (`loop.py:1140`) — pure-функция; в неё добавляется `config_block`.

---

## Phase 1 — Дискриминативная детекция (фикс КА⊃УТ)

Чистая логика, фундамент. Без БД и MCP. THE correctness-фикс.

### Task 1.1: Поле `discriminative_objects` в `ConfigurationSignature` + `discriminative_score()`

**Files:**
- Modify: `backend/app/knowledge/config_detection.py` (dataclass `ConfigurationSignature`, строки 39–67)
- Test: `backend/tests/test_config_detection.py`

- [ ] **Step 1: Написать падающий тест**

Добавить в `backend/tests/test_config_detection.py`:

```python
def test_signature_discriminative_score_method():
    """discriminative_score() = доля найденных дискрим-маркеров."""
    sig = ConfigurationSignature(
        key="t",
        display_name="T",
        characteristic_objects=frozenset({"A", "B"}),
        family="trade",
        discriminative_objects=frozenset({"X", "Y"}),
    )
    assert sig.discriminative_score(set()) == 0.0
    assert sig.discriminative_score({"X"}) == 0.5
    assert sig.discriminative_score({"X", "Y"}) == 1.0
    # объекты вне дискрим-набора не влияют
    assert sig.discriminative_score({"A", "B"}) == 0.0


def test_signature_empty_discriminative_score_is_zero():
    """Базовая конфа без дискрим-маркеров → discriminative_score == 0."""
    sig = ConfigurationSignature(
        key="base", display_name="Base",
        characteristic_objects=frozenset({"A"}), family="trade",
    )
    assert sig.discriminative_objects == frozenset()
    assert sig.discriminative_score({"A", "B", "C"}) == 0.0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_detection.py::test_signature_discriminative_score_method -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'discriminative_objects'`

- [ ] **Step 3: Реализовать поле + метод**

В `config_detection.py`, в `ConfigurationSignature` добавить поле ПОСЛЕ `family` (с дефолтом — обязательно, иначе сломаются позиционные конструкторы в KNOWN_CONFIGURATIONS, которые задают только 4 поля):

```python
    key: str
    display_name: str
    characteristic_objects: frozenset[str]
    family: str
    discriminative_objects: frozenset[str] = frozenset()

    def score(self, channel_objects: set[str]) -> float:
        """Возвращает score = |intersection| / |signature| (характерные объекты)."""
        if not self.characteristic_objects:
            return 0.0
        intersection = channel_objects & self.characteristic_objects
        return len(intersection) / len(self.characteristic_objects)

    def discriminative_score(self, channel_objects: set[str]) -> float:
        """Доля найденных ДИСКРИМИНАТИВНЫХ маркеров (специфичных только для
        этой конфы относительно её subset-сиблингов).

        0.0 если discriminative_objects пуст (базовая конфа семейства —
        выигрывает на characteristic score, когда сиблинг-маркеров нет).
        """
        if not self.discriminative_objects:
            return 0.0
        return len(channel_objects & self.discriminative_objects) / len(
            self.discriminative_objects
        )
```

- [ ] **Step 4: Запустить — убедиться, что проходит + ничего не сломано**

Run: `pytest tests/test_config_detection.py -v`
Expected: PASS (новые 2 теста + все старые — старые конструируют сигнатуры без `discriminative_objects`, дефолт спасает).

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_detection.py backend/tests/test_config_detection.py
git commit -m "feat(config_detection): discriminative_objects field + discriminative_score()"
```

### Task 1.2: Заполнить `discriminative_objects` для КА и ERP

**Files:**
- Modify: `backend/app/knowledge/config_detection.py` (KNOWN_CONFIGURATIONS — записи `erp_2_5` строки 124–143, `ka_2_5` строки 144–159)
- Test: `backend/tests/test_config_detection.py`

- [ ] **Step 1: Написать падающий тест**

```python
def test_ka_has_discriminative_markers_not_in_ut():
    """КА-дискрим-маркеры отсутствуют в УТ-сигнатуре (корень фикса КА⊃УТ)."""
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    assert ka.discriminative_objects, "КА обязана иметь дискрим-маркеры"
    # ни один КА-дискрим не входит в характерные УТ
    assert not (ka.discriminative_objects & ut.characteristic_objects)
    # эмпирически подтверждённый маркер на КА Демо
    assert "Документ.РасчетСебестоимостиТоваров" in ka.discriminative_objects


def test_erp_has_msfo_discriminative_not_in_ka():
    """ERP-дискрим (МСФО) отсутствует в КА (КА = ERP минус МСФО)."""
    erp = next(s for s in KNOWN_CONFIGURATIONS if s.key == "erp_2_5")
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    assert "РегистрБухгалтерии.МеждународныйУчет" in erp.discriminative_objects
    assert not (erp.discriminative_objects & ka.characteristic_objects)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_detection.py::test_ka_has_discriminative_markers_not_in_ut tests/test_config_detection.py::test_erp_has_msfo_discriminative_not_in_ka -v`
Expected: FAIL — `assert ka.discriminative_objects` ложно (frozenset пуст).

- [ ] **Step 3: Заполнить дискрим-наборы**

В записи `erp_2_5` (после `characteristic_objects={...}`) добавить аргумент:

```python
        discriminative_objects=frozenset({
            # ERP vs КА: МСФО + международный/налоговый учёт + производство
            "РегистрБухгалтерии.МеждународныйУчет",
            "РегистрНакопления.НалоговыеОбязательстваРезидентов",
            "Справочник.СтатьиАктивовПассивов",
            "Документ.ПроизводственнаяОперация",
            "Документ.ОтражениеЗарплатыВФинансовомУчете",
        }),
```

В записи `ka_2_5`:

```python
        discriminative_objects=frozenset({
            # КА vs УТ: себестоимость + регламентная ЗУП внутри КА
            "Документ.РасчетСебестоимостиТоваров",
            "Документ.ОтражениеЗарплатыВУчете",
            "Документ.НачислениеЗарплаты",
            "РегистрНакопления.ЗарплатаКВыплате",
        }),
```

УТ и остальные (БП/ЗУП/БГУ/УСО) — `discriminative_objects` НЕ задаём (дефолт `frozenset()`): УТ — базовая конфа trade-семьи (выигрывает на characteristic, когда КА/ERP-маркеров нет), остальные — в других семьях, конфликта надмножества нет.

- [ ] **Step 4: Запустить — убедиться, что проходит + анти-конфликт цел**

Run: `pytest tests/test_config_detection.py -v`
Expected: PASS, включая `test_known_configurations_have_distinct_signatures` (он смотрит только `characteristic_objects`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_detection.py backend/tests/test_config_detection.py
git commit -m "feat(config_detection): заполнить дискрим-маркеры КА/ERP (КА=РасчетСебестоимости, ERP=МСФО)"
```

### Task 1.3: Двухпроходная детекция (final_score = char + discriminative) + margin

**Files:**
- Modify: `backend/app/knowledge/config_detection.py` (`DetectionResult` строки 70–90, `detect_configuration_type` строки 225–278)
- Test: `backend/tests/test_config_detection.py`

- [ ] **Step 1: Написать падающие тесты (ядро фикса)**

```python
def test_ka_base_detected_as_ka_not_ut():
    """КА-база (надмножество УТ) детектится как КА, НЕ УТ. Корень бага."""
    # все характерные УТ + КА-маркеры (реальная картина КА Демо)
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ka_base = set(ut.characteristic_objects) | set(ka.characteristic_objects) \
        | set(ka.discriminative_objects)
    result = detect_configuration_type(ka_base)
    assert result.configuration_key == "ka_2_5"
    assert result.display_name == "КА 2.5"
    assert result.margin > 0.0  # КА явно специфичнее УТ


def test_pure_ut_base_stays_ut_with_clear_margin():
    """Чистая УТ-база (без КА/ERP-маркеров) → УТ, margin большой."""
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    result = detect_configuration_type(ut.characteristic_objects)
    assert result.configuration_key == "ut_11_5"
    assert result.margin >= 0.3  # УТ vs КА по characteristic — большой отрыв


def test_erp_base_beats_ka_via_msfo():
    """ERP-база (КА + МСФО) → ERP, не КА."""
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    erp = next(s for s in KNOWN_CONFIGURATIONS if s.key == "erp_2_5")
    erp_base = set(ka.characteristic_objects) | set(erp.characteristic_objects) \
        | set(erp.discriminative_objects)
    result = detect_configuration_type(erp_base)
    assert result.configuration_key == "erp_2_5"


def test_detection_result_has_margin_field():
    result = detect_configuration_type([])
    assert hasattr(result, "margin")
    assert result.margin == 0.0  # пустой канал
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_detection.py::test_ka_base_detected_as_ka_not_ut -v`
Expected: FAIL — текущий `max(score)` отдаёт `ut_11_5` (УТ и КА оба 1.0, УТ первый в dict). Также `AttributeError: 'DetectionResult' object has no attribute 'margin'`.

- [ ] **Step 3: Реализовать двухпроходную детекцию**

В `DetectionResult` добавить поле (с дефолтом — старые конструкторы в тестах задают 5 полей):

```python
    configuration_key: str
    display_name: str
    confidence: float
    family: str
    scores: dict[str, float]
    margin: float = 0.0
    runner_up_key: str | None = None
```

Переписать тело `detect_configuration_type` (от `channel_set = set(...)` до конца):

```python
    channel_set = set(channel_objects)

    # scores — характерные (для debug/UI и фоллбэка), как раньше.
    scores = {sig.key: sig.score(channel_set) for sig in known_configurations}

    if not channel_set:
        return DetectionResult(
            configuration_key="custom",
            display_name="Самописная",
            confidence=0.0,
            family="unknown",
            scores=scores,
            margin=0.0,
        )

    # Кандидаты: характерный score >= min_confidence.
    candidates = [
        sig for sig in known_configurations
        if sig.score(channel_set) >= min_confidence
    ]
    if not candidates:
        best_key, best_score = max(scores.items(), key=lambda kv: kv[1])
        return DetectionResult(
            configuration_key="custom",
            display_name="Самописная",
            confidence=best_score,
            family="unknown",
            scores=scores,
            margin=0.0,
        )

    # final_score = characteristic + discriminative. Дискрим разводит
    # subset-конфликт (КА⊃УТ): на КА-базе КА имеет disc>0, УТ disc=0.
    def final_score(sig: ConfigurationSignature) -> float:
        return sig.score(channel_set) + sig.discriminative_score(channel_set)

    ranked = sorted(candidates, key=final_score, reverse=True)
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None

    margin = final_score(winner) - (final_score(runner_up) if runner_up else 0.0)

    # confidence: для специфичной конфы — доля дискрим-маркеров; для базовой
    # (disc пуст) — характерный score. Всегда в [0,1], годен для бейджа/gate.
    confidence = (
        winner.discriminative_score(channel_set)
        if winner.discriminative_objects
        else winner.score(channel_set)
    )

    return DetectionResult(
        configuration_key=winner.key,
        display_name=winner.display_name,
        confidence=confidence,
        family=winner.family,
        scores=scores,
        margin=margin,
        runner_up_key=runner_up.key if runner_up else None,
    )
```

- [ ] **Step 4: Запустить — весь файл тестов**

Run: `pytest tests/test_config_detection.py -v`
Expected: PASS — новые тесты + все старые. Сверка старых:
- `test_ut_11_5_full_signature_detected`: УТ full → char 1.0, disc пуст → confidence 1.0 ≥ 0.99 ✓
- `test_erp_2_5_detected_with_partial_overlap`: `scores["erp_2_5"] > scores["ut_11_5"]` — `scores` остался характерным ✓
- `test_below_min_confidence_returns_custom`: нет кандидатов ≥0.30 → custom ✓
- `test_ut_and_erp_signatures_overlap...`: winner ∈ {ut,erp,ka}, family trade ✓

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_detection.py backend/tests/test_config_detection.py
git commit -m "fix(config_detection): двухпроходная детекция final=char+discriminative — КА⊃УТ больше не мисдетектится"
```

### Task 1.4: Gate-решение `gate_decision()` (auto / confirm / custom)

**Files:**
- Modify: `backend/app/knowledge/config_detection.py` (новые константы + функция в конце файла)
- Test: `backend/tests/test_config_detection.py`

- [ ] **Step 1: Написать падающий тест**

```python
from app.knowledge.config_detection import gate_decision, HIGH_CONFIDENCE, MARGIN_DELTA


def test_gate_auto_when_confident_and_separated():
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    ka_base = set(ut.characteristic_objects) | set(ka.characteristic_objects) \
        | set(ka.discriminative_objects)
    result = detect_configuration_type(ka_base)
    assert gate_decision(result) == "auto"


def test_gate_custom_for_unknown():
    result = detect_configuration_type(["Документ.НеведомаяZzz"])
    assert gate_decision(result) == "custom"


def test_gate_confirm_when_margin_small():
    """Искусственно близкий результат → confirm."""
    result = DetectionResult(
        configuration_key="ka_2_5", display_name="КА 2.5",
        confidence=0.9, family="trade", scores={}, margin=0.05,
    )
    assert gate_decision(result) == "confirm"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_detection.py::test_gate_auto_when_confident_and_separated -v`
Expected: FAIL — `ImportError: cannot import name 'gate_decision'`.

- [ ] **Step 3: Реализовать gate**

Добавить в `config_detection.py` (после `MIN_CONFIDENCE = 0.30`):

```python
# Confidence-gate пороги (B.3). Стартовые значения — тюнятся на 4 demo-базах
# (Open Q2 дизайн-дока). HIGH — минимальная уверенность для авто-линка;
# DELTA — минимальный отрыв победителя от руннер-апа по final_score.
HIGH_CONFIDENCE = 0.50
MARGIN_DELTA = 0.30
```

И функцию в конце файла:

```python
def gate_decision(
    result: DetectionResult,
    *,
    high_confidence: float = HIGH_CONFIDENCE,
    margin_delta: float = MARGIN_DELTA,
) -> str:
    """Решение онбординг-гейта по результату детекции (B.3).

    Returns:
        "custom"  — самописная (нет кандидата ≥ MIN_CONFIDENCE) → типовые не
                    подключаем, предлагаем ручной override.
        "auto"    — уверенно и с отрывом → авто-линк, бейдж «(авто)».
        "confirm" — кандидат есть, но близко к руннер-апу → 1 вопрос аналитику.
    """
    if result.is_custom:
        return "custom"
    if result.confidence >= high_confidence and result.margin >= margin_delta:
        return "auto"
    return "confirm"
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_config_detection.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_detection.py backend/tests/test_config_detection.py
git commit -m "feat(config_detection): gate_decision() auto/confirm/custom + пороги HIGH/DELTA"
```

---

## Phase 2 — Миграция v24 + хранение источника детекции

### Task 2.1: Миграция v24 — колонка `configuration_source`

**Files:**
- Modify: `backend/app/storage/migrations.py` (`CURRENT_VERSION` строка 77; новый блок MIGRATIONS_V24; новый `if current < 24` в `apply_migrations`)
- Test: `backend/tests/test_migrations.py` (создать, если нет — проверь `ls backend/tests/test_migrations*.py`)

- [ ] **Step 1: Написать падающий тест**

Создать/дополнить `backend/tests/test_migrations.py`:

```python
import aiosqlite
import pytest
from app.storage.migrations import apply_migrations, CURRENT_VERSION


@pytest.mark.asyncio
async def test_v24_adds_configuration_source_column():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cur = await conn.execute("PRAGMA table_info(mcp_connections)")
        cols = {row[1] for row in await cur.fetchall()}
        assert "configuration_source" in cols
        ver = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
        assert ver[0][0] == CURRENT_VERSION
        assert CURRENT_VERSION >= 24
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migrations_idempotent_second_run():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await apply_migrations(conn)  # не должно бросить / дублировать
        ver = await conn.execute_fetchall("SELECT MAX(version) FROM schema_version")
        assert ver[0][0] == CURRENT_VERSION
    finally:
        await conn.close()
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_migrations.py::test_v24_adds_configuration_source_column -v`
Expected: FAIL — `configuration_source` нет в колонках; `CURRENT_VERSION == 23`.

- [ ] **Step 3: Реализовать миграцию**

В `migrations.py` изменить строку 77:

```python
CURRENT_VERSION = 24
```

Добавить блок после `MIGRATIONS_V23` (после строки 702):

```python
# Миграция v24 (Multi-base онбординг, B.3): источник детекции конфигурации.
#
# configuration_source фиксирует, КАК была установлена mcp_connections.configuration:
#   'auto'      — авто-детект уверенно (confidence-gate = auto)
#   'ambiguous' — авто-детект неоднозначно (gate = confirm), записан best-guess,
#                 бейдж показывает «?» до подтверждения аналитиком
#   'confirmed' — аналитик подтвердил предложенный вариант
#   'manual'    — аналитик выбрал вручную (override), детекту не доверяя
#   'custom'    — самописная (gate = custom), типовые знания не подключаются
#   'failed'    — детекция не завершилась (база недоступна) — бейдж «↻»
#   NULL        — legacy / детект ещё не запускался
#
# Additive ALTER, без backfill: NULL для старых строк — корректное «не детектили».
MIGRATIONS_V24 = [
    "ALTER TABLE mcp_connections ADD COLUMN configuration_source TEXT",
]
```

Добавить блок в `apply_migrations` ПОСЛЕ блока `if current < 23` (после строки 988):

```python
    if current < 24:
        # configuration_source (v24, Multi-base онбординг B.3) — как установлена
        # configuration: auto/ambiguous/confirmed/manual/custom/failed/NULL.
        for stmt in MIGRATIONS_V24:
            await db.execute(stmt)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (24,),
        )
        await db.commit()
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_migrations.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage/migrations.py backend/tests/test_migrations.py
git commit -m "feat(migrations): v24 — configuration_source в mcp_connections"
```

### Task 2.2: `update_channel_configuration` пишет `configuration_source`

**Files:**
- Modify: `backend/app/knowledge/config_detection.py` (`update_channel_configuration` строки 281–307)
- Test: `backend/tests/test_config_detection.py`

- [ ] **Step 1: Написать падающий тест**

```python
@pytest.mark.asyncio
async def test_update_channel_configuration_writes_source(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('ch-s', 'S', 'http://localhost:6010/mcp', 'embedded')"
    )
    await db.commit()
    sig = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    result = detect_configuration_type(sig.characteristic_objects)
    await update_channel_configuration(db, "ch-s", result, source="auto")
    cur = await db.execute(
        "SELECT configuration, configuration_source FROM mcp_connections WHERE id='ch-s'"
    )
    row = await cur.fetchone()
    assert row[0] == "УТ 11.5"
    assert row[1] == "auto"


@pytest.mark.asyncio
async def test_update_channel_configuration_default_source_none(db):
    """Обратная совместимость: без source — пишем NULL (как раньше по смыслу)."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('ch-n', 'N', 'http://localhost:6010/mcp', 'embedded')"
    )
    await db.commit()
    result = detect_configuration_type(["Документ.РеализацияТоваровУслуг"])
    await update_channel_configuration(db, "ch-n", result)
    cur = await db.execute(
        "SELECT configuration_source FROM mcp_connections WHERE id='ch-n'"
    )
    assert (await cur.fetchone())[0] is None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_detection.py::test_update_channel_configuration_writes_source -v`
Expected: FAIL — `TypeError: update_channel_configuration() got an unexpected keyword argument 'source'`.

- [ ] **Step 3: Реализовать**

Заменить тело `update_channel_configuration`:

```python
async def update_channel_configuration(
    db,  # aiosqlite.Connection
    channel_id: str,
    result: DetectionResult,
    *,
    source: str | None = None,
) -> None:
    """Записывает результат детекции в mcp_connections.

    Args:
        source: значение configuration_source (auto/ambiguous/confirmed/
            manual/custom/failed). None — не меняем семантику источника
            (пишем NULL — «детект без явного источника»).
    """
    await db.execute(
        "UPDATE mcp_connections SET configuration = ?, configuration_source = ? "
        "WHERE id = ?",
        (result.display_name, source, channel_id),
    )
    await db.commit()
    logger.info(
        "Configuration detected для канала %s: %s (confidence %.2f, source=%s)",
        channel_id,
        result.display_name,
        result.confidence,
        source,
    )
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_config_detection.py -v`
Expected: PASS (включая старые `test_update_channel_configuration_*` — `source` имеет дефолт).

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_detection.py backend/tests/test_config_detection.py
git commit -m "feat(config_detection): update_channel_configuration пишет configuration_source"
```

### Task 2.3: `configuration_source` в API-моделях + SELECT/override endpoint

**Files:**
- Modify: `backend/app/models.py` (`MCPConnection` ~72, `MCPConnectionFull` ~131, `MCPConnectionUpdate` ~116)
- Modify: `backend/app/routes/connections.py` (`_CONNECTION_COLUMNS` ~133, `_row_tuple_to_dict` ~139, `_row_to_full` ~92, `update_connection` ~265)
- Test: `backend/tests/test_routes_connections.py` (дополнить; проверь имя файла `ls backend/tests/test_routes_connections*.py`)

- [ ] **Step 1: Написать падающий тест**

Дополнить `backend/tests/test_routes_connections.py` (используй существующий `client` fixture этого файла; если другой паттерн — скопируй из соседних тестов):

```python
@pytest.mark.asyncio
async def test_override_configuration_via_put(client):
    # создать подключение
    r = await client.post("/connections", json={
        "name": "Override", "endpoint": "http://localhost:6010/mcp", "kind": "embedded",
    })
    conn_id = r.json()["id"]
    # override конфигурации вручную
    r2 = await client.put(f"/connections/{conn_id}", json={
        "configuration": "КА 2.5", "configuration_source": "manual",
    })
    assert r2.status_code == 200
    body = r2.json()
    assert body["configuration"] == "КА 2.5"
    assert body["configuration_source"] == "manual"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_routes_connections.py::test_override_configuration_via_put -v`
Expected: FAIL — `MCPConnectionUpdate` с `extra="forbid"` отвергает `configuration`/`configuration_source` (422).

- [ ] **Step 3: Реализовать**

В `models.py`:
- В `MCPConnection` добавить после `configuration` (строка 86): `configuration_source: str | None = None`
- В `MCPConnectionFull` добавить после `configuration` (строка 144): `configuration_source: str | None = None`
- В `MCPConnectionUpdate` добавить (после `kind` строка 123):
```python
    configuration: str | None = Field(default=None, max_length=100)
    configuration_source: str | None = Field(default=None, max_length=20)
```

В `connections.py`:
- `_CONNECTION_COLUMNS` (строка 133) — добавить колонку в конец:
```python
_CONNECTION_COLUMNS = (
    "id, name, endpoint, channel, anon_enabled, kind, last_seen_at, created_at, "
    "mode, configuration, platform, ext_version, capabilities, fingerprint, "
    "configuration_source"
)
```
- `_row_tuple_to_dict` (строка 145) — добавить в возвращаемый dict:
```python
        "configuration_source": row[14] if len(row) > 14 else None,
```
- `_row_to_full` (строка 110) — добавить в конструктор `MCPConnectionFull(...)`:
```python
        configuration_source=row.get("configuration_source"),
```
- `update_connection` (строки 291–301) — добавить две ветки в сбор `updates`:
```python
    if body.configuration is not None:
        updates["configuration"] = body.configuration
    if body.configuration_source is not None:
        updates["configuration_source"] = body.configuration_source
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_routes_connections.py -v`
Expected: PASS (новый тест + существующие — поля Optional с дефолтами).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/routes/connections.py backend/tests/test_routes_connections.py
git commit -m "feat(connections): configuration_source в моделях/SELECT + ручной override через PUT"
```

---

## Phase 3 — Live-пробы детекции через MCP (decoupled от полного индекса)

Эмпирика: детекция = горстка targeted `name_mask`-проб (sub-second), без полного каталога.

> **Слой:** `config_detection.py` остаётся ЧИСТЫМ (без внешних зависимостей — требование дизайна, Dependencies). Весь MCP-I/O детекции — в НОВОМ модуле `config_probe.py`, который импортирует чистый `config_detection` + `indexer.live_metadata_suggest`. Это сохраняет правильную слоистость (indexer/probe выше, чем pure-detection) и делает monkeypatch предсказуемым.

### Task 3.1: `config_probe.py` — `ALL_MARKERS` + `collect_marker_presence()` + `detect_from_live()`

**Files:**
- Create: `backend/app/knowledge/config_probe.py`
- Test: `backend/tests/test_config_probe.py` (создать)

- [ ] **Step 1: Написать падающий тест (с фейковым MCP)**

Создать `backend/tests/test_config_probe.py`:

```python
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_config_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.config_probe'`.

- [ ] **Step 3: Реализовать модуль проб**

Создать `backend/app/knowledge/config_probe.py`:

```python
"""Live-пробы конфигурации через MCP (Multi-base онбординг, Phase 3).

Слой MCP-I/O поверх ЧИСТОГО config_detection. Детекция = targeted name_mask-пробы
по маркерам (sub-second), без полного индекса метаданных. config_detection при
этом не получает внешних зависимостей (требование дизайна).
"""
from __future__ import annotations

import asyncio
import logging

from app.knowledge.config_detection import (
    KNOWN_CONFIGURATIONS,
    DetectionResult,
    detect_configuration_type,
)
from app.knowledge.indexer import live_metadata_suggest

logger = logging.getLogger(__name__)


# Объединённый набор всех маркеров (характерные ∪ дискриминативные) по всем
# конфигурациям. Это РОВНО те object_path, по которым считается score, поэтому
# детекция по присутствию только этих маркеров даёт те же scores, что и полный
# каталог — но дёшево (targeted-пробы вместо полного индекса).
ALL_MARKERS: frozenset[str] = frozenset(
    obj
    for sig in KNOWN_CONFIGURATIONS
    for obj in (*sig.characteristic_objects, *sig.discriminative_objects)
)


async def collect_marker_presence(
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
    concurrency: int = 10,
) -> set[str]:
    """Параллельно пробит присутствие каждого маркера через MCP get_metadata.

    Для каждого маркера «Тип.Имя» делает targeted-пробу name_mask=<Имя>,
    limit=5 и считает маркер присутствующим, если среди результатов есть точное
    совпадение object_path. ~40 проб с ограничением параллелизма — sub-second
    суммарно на локальном MCP (эмпирика КА Демо :6012).

    Никогда не бросает наружу: пробы — best-effort; маркер, чья проба упала,
    считается отсутствующим (детекция деградирует консервативно).
    """
    sem = asyncio.Semaphore(concurrency)
    present: set[str] = set()

    async def probe(marker: str) -> None:
        short_name = marker.split(".")[-1]
        async with sem:
            try:
                objs = await live_metadata_suggest(
                    mcp_endpoint, short_name, 5, anon_headers=anon_headers,
                )
            except Exception:  # noqa: BLE001 — best-effort граница пробы
                return
        if any(o.object_path == marker for o in objs):
            present.add(marker)

    await asyncio.gather(*(probe(m) for m in ALL_MARKERS))
    return present


async def detect_from_live(
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
) -> DetectionResult:
    """Полный live-цикл детекции: пробы маркеров → detect_configuration_type.

    Отвязан от полного индекса (метаданных-каталога). Возвращает DetectionResult
    с margin/confidence — caller применяет gate_decision().
    """
    present = await collect_marker_presence(mcp_endpoint, anon_headers=anon_headers)
    return detect_configuration_type(present)
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_config_probe.py tests/test_config_detection.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/config_probe.py backend/tests/test_config_probe.py
git commit -m "feat(config_probe): live-пробы маркеров (collect_marker_presence + detect_from_live), config_detection остаётся чистым"
```

---

## Phase 4 — Авто-детект на коннекте + confidence-gate

> **Refinement B.1 (утверждённая эмпирика):** на ping триггерим именно ДЕТЕКТ-ПРОБЫ (Phase 3, sub-second), а НЕ полный `start_indexer`. Дизайн изначально писал «ping → start_indexer», но эмпирика отвязала детекцию от полного каталога. Полный индекс (`start_indexer`, для @-mention) остаётся ручным («Изучить базу») и чинится отдельно в Phase 7. Условие запуска детекта — `configuration IS NULL` (на «горячих» базах не дёргаем MCP повторно).

### Task 4.1: Модуль `onboarding.py` — детект на канал + gate→source

**Files:**
- Create: `backend/app/knowledge/onboarding.py`
- Test: `backend/tests/test_onboarding_detection.py` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_onboarding_detection.py`:

```python
"""Тесты онбординг-детекции на коннекте (Phase 4)."""
from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.config_detection import KNOWN_CONFIGURATIONS, detect_configuration_type
from app.knowledge.onboarding import run_detection_for_channel, should_run_detection
from app.storage.migrations import apply_migrations


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_should_run_detection_when_configuration_null(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c1','C','http://x/mcp','embedded')"
    )
    await db.commit()
    assert await should_run_detection(db, "c1") is True


@pytest.mark.asyncio
async def test_should_not_run_when_already_detected(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('c2','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    assert await should_run_detection(db, "c2") is False


@pytest.mark.asyncio
async def test_run_detection_writes_auto_for_confident(db, monkeypatch):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c3','C','http://x/mcp','embedded')"
    )
    await db.commit()
    ka = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ka_2_5")
    ut = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    present = set(ut.characteristic_objects) | set(ka.characteristic_objects) \
        | set(ka.discriminative_objects)

    async def fake_detect(endpoint, *, anon_headers=None):
        return detect_configuration_type(present)

    monkeypatch.setattr("app.knowledge.onboarding.detect_from_live", fake_detect)
    await run_detection_for_channel(db, "c3", "http://x/mcp")
    cur = await db.execute(
        "SELECT configuration, configuration_source FROM mcp_connections WHERE id='c3'"
    )
    row = await cur.fetchone()
    assert row[0] == "КА 2.5"
    assert row[1] == "auto"


@pytest.mark.asyncio
async def test_run_detection_writes_failed_on_mcp_error(db, monkeypatch):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('c4','C','http://x/mcp','embedded')"
    )
    await db.commit()

    async def boom(endpoint, *, anon_headers=None):
        raise RuntimeError("MCP недоступен")

    monkeypatch.setattr("app.knowledge.onboarding.detect_from_live", boom)
    await run_detection_for_channel(db, "c4", "http://x/mcp")
    cur = await db.execute(
        "SELECT configuration_source FROM mcp_connections WHERE id='c4'"
    )
    assert (await cur.fetchone())[0] == "failed"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_onboarding_detection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.onboarding'`.

- [ ] **Step 3: Реализовать модуль**

Создать `backend/app/knowledge/onboarding.py`:

```python
"""Онбординг-детекция конфигурации на подключении базы (Multi-base, Phase 4).

При первом успешном ping новой базы (configuration ещё не установлена) фоном
запускаем дешёвые live-пробы маркеров → дискриминативный детект → confidence-gate
→ пишем configuration + configuration_source. Не блокирует чат, не зависит от
полного индекса метаданных.
"""
from __future__ import annotations

import logging

import aiosqlite

from app.knowledge.config_detection import gate_decision, update_channel_configuration
from app.knowledge.config_probe import detect_from_live

logger = logging.getLogger(__name__)

# gate_decision → configuration_source
_GATE_TO_SOURCE = {
    "auto": "auto",
    "confirm": "ambiguous",
    "custom": "custom",
}


async def should_run_detection(db: aiosqlite.Connection, channel_id: str) -> bool:
    """True, если для канала ещё не установлена configuration (детект не делали).

    Не перезапускаем на «горячих» базах с известной конфой — иначе лишние
    MCP-вызовы на каждый ping. Форс — через ручной override / переиндексацию.
    """
    cur = await db.execute(
        "SELECT configuration FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return False
    return row[0] is None


async def run_detection_for_channel(
    db: aiosqlite.Connection,
    channel_id: str,
    mcp_endpoint: str,
    *,
    anon_headers: dict[str, str] | None = None,
) -> None:
    """Выполняет live-детект и пишет результат. Никогда не raise наружу.

    Сбой MCP → configuration_source='failed' (бейдж «↻»), НЕ ложный УТ.
    """
    try:
        result = await detect_from_live(mcp_endpoint, anon_headers=anon_headers)
    except Exception as exc:  # noqa: BLE001 — фон, best-effort
        logger.warning(
            "Онбординг-детект для канала %s не завершён: %s", channel_id, exc
        )
        await db.execute(
            "UPDATE mcp_connections SET configuration_source = 'failed' WHERE id = ?",
            (channel_id,),
        )
        await db.commit()
        return

    decision = gate_decision(result)
    source = _GATE_TO_SOURCE[decision]
    await update_channel_configuration(db, channel_id, result, source=source)
    logger.info(
        "Онбординг-детект канала %s: %s (gate=%s, margin=%.2f)",
        channel_id, result.display_name, decision, result.margin,
    )
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_onboarding_detection.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/onboarding.py backend/tests/test_onboarding_detection.py
git commit -m "feat(onboarding): фон-детект конфигурации на коннекте (gate→source, fail→failed)"
```

### Task 4.2: Триггер детекции из `ping_connection`

**Files:**
- Modify: `backend/app/routes/connections.py` (module-level set для tasks + хвост `ping_connection` перед `return`, строки ~447–467)
- Test: `backend/tests/test_routes_connections.py`

- [ ] **Step 1: Написать падающий тест**

```python
@pytest.mark.asyncio
async def test_ping_triggers_detection_when_unconfigured(client, monkeypatch):
    """После ping новой базы фоном запускается детекция (configuration NULL)."""
    import app.routes.connections as conns

    called = {}

    async def fake_run(db, channel_id, endpoint, *, anon_headers=None):
        called["channel_id"] = channel_id

    monkeypatch.setattr(conns, "run_detection_for_channel", fake_run)
    # ping-путь нужно довести до успеха — мокни MCPClient в этом тест-модуле
    # по образцу существующих ping-тестов (initialize/list_tools). Если их нет —
    # используй тот же фейк, что в test_ping_connection_success.

    r = await client.post("/connections", json={
        "name": "Fresh", "endpoint": "http://localhost:6010/mcp", "kind": "embedded",
    })
    conn_id = r.json()["id"]
    await client.post(f"/connections/{conn_id}/ping")
    # фон-таска создаётся синхронно внутри хендлера
    assert called.get("channel_id") == conn_id
```

> NB: если в `test_routes_connections.py` ещё нет успешного мок-ping — переиспользуй фикстуру/мок из существующего `test_ping_*` (там MCPClient уже подменяется). Тест проверяет ТОЛЬКО факт планирования детекции, не её результат.

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_routes_connections.py::test_ping_triggers_detection_when_unconfigured -v`
Expected: FAIL — `run_detection_for_channel` не существует в модуле / не вызывается.

- [ ] **Step 3: Реализовать триггер**

В `connections.py`:
- Импорт вверху:
```python
import asyncio
from app.knowledge.onboarding import run_detection_for_channel, should_run_detection
```
- Module-level set (после `logger`/`router`, рядом со строкой 35):
```python
# Fire-and-forget онбординг-детект — ссылка, чтобы GC не собрал task.
_DETECTION_TASKS: set[asyncio.Task] = set()
```
- В `ping_connection`, прямо перед финальным `return MCPPingWithTimestampResponse(...)` (после получения `last_seen`, строка ~454):
```python
    # Multi-base онбординг (B.1): на первом успешном ping новой базы фоном
    # детектируем конфигурацию. НЕ блокирует ответ ping. Только если конфа ещё
    # не установлена (configuration IS NULL) — на «горячих» базах не дёргаем MCP.
    try:
        if await should_run_detection(db, conn_id):
            task = asyncio.create_task(
                run_detection_for_channel(db, conn_id, endpoint),
                name=f"onboarding-detect-{conn_id}",
            )
            _DETECTION_TASKS.add(task)
            task.add_done_callback(_DETECTION_TASKS.discard)
    except Exception:  # noqa: BLE001 — детект-триггер не должен ломать ping
        logger.exception("Не удалось запланировать онбординг-детект для %s", conn_id)
```
> Анонимизация (осознанное упрощение): `ping_connection` сейчас в SELECT (строки 361–365) берёт только `endpoint, kind` — без `anon_enabled`. Детект-пробы идут БЕЗ anon-заголовков: они читают только метаданные объектов (имена типов), которые не PII (A-10 их не маркирует). Если позже понадобится anon — расширить SELECT на `anon_enabled` и вызвать `run_detection_for_channel(db, conn_id, endpoint, anon_headers={"X-Anon-Enabled": "true"})`.

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_routes_connections.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/connections.py backend/tests/test_routes_connections.py
git commit -m "feat(connections): ping_connection триггерит фон-детект конфы для новой базы"
```

---

## Phase 5 — loop.py B.4: конфа в промпт + buddy-аргументы + кап typical + стиль

### Task 5.1: `resolve_channel_typical_context()` — мост detected → typical channel_id

**Files:**
- Create: `backend/app/orchestrator/channel_config.py`
- Test: `backend/tests/test_channel_config_context.py` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_channel_config_context.py`:

```python
"""Тесты моста detected-конфа → typical channel_id (Phase 5)."""
from __future__ import annotations

import aiosqlite
import pytest

from app.orchestrator.channel_config import resolve_channel_typical_context
from app.storage.migrations import apply_migrations


@pytest.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    await apply_migrations(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def _seed_ka_typical(db):
    await db.execute(
        "INSERT INTO typical_configurations "
        "(config_kind, config_version, channel_id, display_name, status) "
        "VALUES ('KA_2','2.5.25.92','_ka2_25_92','Комплексная автоматизация 2.5','graph_built')"
    )
    await db.commit()


@pytest.mark.asyncio
async def test_resolve_maps_ka_display_to_typical_channel(db):
    await _seed_ka_typical(db)
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch")
    assert ctx.display_name == "КА 2.5"
    assert ctx.typical_channel_id == "_ka2_25_92"
    assert ctx.buddy_config_name == "Комплексная автоматизация"
    assert ctx.source == "auto"


@pytest.mark.asyncio
async def test_resolve_none_when_no_configuration(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind) "
        "VALUES ('ch2','C','http://x/mcp','embedded')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch2")
    assert ctx.display_name is None
    assert ctx.typical_channel_id is None


@pytest.mark.asyncio
async def test_resolve_typical_none_when_not_loaded(db):
    """Конфа детектнута, но типовая КА не загружена → typical_channel_id None."""
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch3','C','http://x/mcp','embedded','КА 2.5','auto')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch3")
    assert ctx.display_name == "КА 2.5"
    assert ctx.typical_channel_id is None  # типовая не загружена
    assert ctx.buddy_config_name == "Комплексная автоматизация"  # для buddy всё равно есть


@pytest.mark.asyncio
async def test_resolve_custom_returns_no_typical(db):
    await db.execute(
        "INSERT INTO mcp_connections (id, name, endpoint, kind, configuration, configuration_source) "
        "VALUES ('ch4','C','http://x/mcp','embedded','Самописная','custom')"
    )
    await db.commit()
    ctx = await resolve_channel_typical_context(db, "ch4")
    assert ctx.typical_channel_id is None
    assert ctx.buddy_config_name is None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_channel_config_context.py -v`
Expected: FAIL — `ModuleNotFoundError: app.orchestrator.channel_config`.

- [ ] **Step 3: Реализовать мост**

Создать `backend/app/orchestrator/channel_config.py`:

```python
"""Мост: detected-конфигурация канала → typical channel_id + buddy-имя.

loop.py использует это, чтобы (а) сказать LLM, какой типовой channel_id брать
для конфо-зависимых вопросов, (б) подставить configuration в buddy.search_its.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiosqlite

from app.knowledge.config_detection import KNOWN_CONFIGURATIONS
from app.knowledge.typical.registry import TypicalConfigKind

logger = logging.getLogger(__name__)

# detection display_name («КА 2.5») → detection key («ka_2_5»).
_DISPLAY_TO_KEY: dict[str, str] = {
    sig.display_name: sig.key for sig in KNOWN_CONFIGURATIONS
}

# detection key → typical config_kind (для запроса typical_configurations).
# bgu_2_0 не имеет typical-снапшота → отсутствует в маппинге.
_KEY_TO_TYPICAL_KIND: dict[str, TypicalConfigKind] = {
    "ut_11_5": TypicalConfigKind.UT_115,
    "erp_2_5": TypicalConfigKind.ERP_25,
    "ka_2_5": TypicalConfigKind.KA_2,
    "bp_3_0": TypicalConfigKind.BP_30,
    "zup_3_1": TypicalConfigKind.ZUP_31,
    "uso_2_5": TypicalConfigKind.USO_25,
}

# detection key → строка configuration для buddy.search_its (Open Q4 дизайна:
# Напарник ждёт имя без версии; «Управление торговлей» сработало в тесте).
_KEY_TO_BUDDY_CONFIG: dict[str, str] = {
    "ut_11_5": "Управление торговлей",
    "erp_2_5": "ERP Управление предприятием",
    "ka_2_5": "Комплексная автоматизация",
    "bp_3_0": "Бухгалтерия предприятия",
    "zup_3_1": "Зарплата и управление персоналом",
    "uso_2_5": "Управление строительной организацией",
}

_READY_TYPICAL_STATUSES = ("ready", "enriched", "graph_built")


@dataclass(frozen=True, slots=True)
class ChannelTypicalContext:
    """Контекст конфигурации канала для сборки промпта/диспетча buddy."""

    display_name: str | None        # «КА 2.5» (детект) или None
    typical_channel_id: str | None  # «_ka2_25_92» или None (типовая не загружена)
    typical_display_name: str | None
    buddy_config_name: str | None   # «Комплексная автоматизация» или None
    source: str | None              # auto/confirmed/manual/ambiguous/custom/failed

    @property
    def has_typical(self) -> bool:
        return self.typical_channel_id is not None


_EMPTY = ChannelTypicalContext(None, None, None, None, None)


async def resolve_channel_typical_context(
    db: aiosqlite.Connection,
    channel_id: str,
) -> ChannelTypicalContext:
    """Резолвит конфигурацию канала в typical channel_id + buddy-имя.

    Best-effort: при отсутствии конфы/типовой возвращает частично/полностью
    пустой контекст (loop.py работает как раньше — без инжекта).
    """
    cur = await db.execute(
        "SELECT configuration, configuration_source FROM mcp_connections WHERE id = ?",
        (channel_id,),
    )
    row = await cur.fetchone()
    if row is None or not row[0] or row[0] == "Самописная":
        return _EMPTY

    display_name, source = row[0], row[1]
    key = _DISPLAY_TO_KEY.get(display_name)
    if key is None:
        return ChannelTypicalContext(display_name, None, None, None, source)

    buddy_name = _KEY_TO_BUDDY_CONFIG.get(key)
    kind = _KEY_TO_TYPICAL_KIND.get(key)
    if kind is None:
        return ChannelTypicalContext(display_name, None, None, buddy_name, source)

    # Берём самую свежую готовую типовую этого kind.
    placeholders = ",".join("?" * len(_READY_TYPICAL_STATUSES))
    cur2 = await db.execute(
        f"SELECT channel_id, display_name FROM typical_configurations "
        f"WHERE config_kind = ? AND status IN ({placeholders}) "
        f"ORDER BY config_version DESC LIMIT 1",
        (kind.value, *_READY_TYPICAL_STATUSES),
    )
    trow = await cur2.fetchone()
    if trow is None:
        return ChannelTypicalContext(display_name, None, None, buddy_name, source)

    return ChannelTypicalContext(
        display_name=display_name,
        typical_channel_id=trow[0],
        typical_display_name=trow[1],
        buddy_config_name=buddy_name,
        source=source,
    )
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_channel_config_context.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/channel_config.py backend/tests/test_channel_config_context.py
git commit -m "feat(orchestrator): resolve_channel_typical_context — мост detected→typical channel_id + buddy-имя"
```

### Task 5.2: Блок конфигурации в system prompt

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (`_build_full_system_prompt` строки 1140–1167; вызов на 1381; новая helper-функция)
- Test: `backend/tests/test_loop_system_prompt.py` (создать или дополнить существующий тест loop — проверь `ls backend/tests/test_loop*.py`)

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_loop_system_prompt.py`:

```python
"""Тесты сборки config-блока system prompt (Phase 5)."""
from app.orchestrator.channel_config import ChannelTypicalContext
from app.orchestrator.loop import _build_full_system_prompt, _build_config_block


def test_config_block_with_typical():
    ctx = ChannelTypicalContext(
        display_name="КА 2.5", typical_channel_id="_ka2_25_92",
        typical_display_name="Комплексная автоматизация 2.5",
        buddy_config_name="Комплексная автоматизация", source="auto",
    )
    block = _build_config_block(ctx)
    assert "КА 2.5" in block
    assert "_ka2_25_92" in block


def test_config_block_empty_when_no_context():
    ctx = ChannelTypicalContext(None, None, None, None, None)
    assert _build_config_block(ctx) == ""


def test_full_prompt_includes_config_block():
    ctx = ChannelTypicalContext(
        display_name="КА 2.5", typical_channel_id="_ka2_25_92",
        typical_display_name="Комплексная автоматизация 2.5",
        buddy_config_name="Комплексная автоматизация", source="auto",
    )
    prompt = _build_full_system_prompt("", "", "", config_block=_build_config_block(ctx))
    assert "_ka2_25_92" in prompt
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_loop_system_prompt.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_config_block'`.

- [ ] **Step 3: Реализовать**

В `loop.py` добавить функцию перед `_build_full_system_prompt` (строка 1140):

```python
def _build_config_block(ctx) -> str:
    """Блок текущей конфигурации канала для system prompt (B.4 роутинг типовых).

    ctx — ChannelTypicalContext. Пусто, если конфа не детектнута.
    """
    if ctx is None or ctx.display_name is None:
        return ""
    lines = [f"═══════ ТЕКУЩАЯ КОНФИГУРАЦИЯ БАЗЫ ═══════\n\nБаза клиента: {ctx.display_name}."]
    if ctx.typical_channel_id:
        lines.append(
            f"Для вопросов про ТИПОВУЮ логику этой конфигурации используй "
            f"typical-инструменты с channel_id=`{ctx.typical_channel_id}` "
            f"({ctx.typical_display_name}). НЕ вызывай list_typical_configurations "
            f"ради channel_id — он уже известен. НЕ опирайся на другую типовую (УТ/ERP), "
            f"если она не совпадает с текущей."
        )
    else:
        lines.append(
            "Типовая для этой конфигурации не загружена локально — отвечай по живой "
            "базе (MCP) и ИТС (buddy), типовые-инструменты могут не дать данных."
        )
    return "\n".join(lines)
```

Изменить сигнатуру `_build_full_system_prompt`:

```python
def _build_full_system_prompt(
    mem_block: str,
    skills_block: str,
    todos_block: str,
    mentions_block: str = "",
    config_block: str = "",
) -> str:
    ...
    prompt_parts = [SYSTEM_PROMPT]
    if config_block:
        prompt_parts.append(config_block)
    if mem_block:
        prompt_parts.append(mem_block)
    if skills_block:
        prompt_parts.append(skills_block)
    if mentions_block:
        prompt_parts.append(mentions_block)
    if todos_block:
        prompt_parts.append(todos_block)
    return "\n\n".join(prompt_parts)
```

(config_block идёт сразу после статики — это важнейший контекст запроса.)

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_loop_system_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_system_prompt.py
git commit -m "feat(loop): _build_config_block — инжект текущей конфы + typical channel_id в system prompt"
```

### Task 5.3: Резолв контекста в `run_chat_loop` + прокидка в промпт

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (импорт; резолв после `mcp_endpoint = await lookup_mcp_endpoint(...)` строка 1279; вызов `_build_full_system_prompt` строка 1381)
- Test: интеграционный smoke ниже (Task 5.6) покрывает; для этого шага — компиляция + существующие loop-тесты.

- [ ] **Step 1: Добавить импорт + резолв**

В `loop.py` импорт (рядом с другими orchestrator-импортами, ~строка 124):

```python
from app.orchestrator.channel_config import resolve_channel_typical_context
```

После строки 1279 (`mcp_endpoint = await lookup_mcp_endpoint(...)`, внутри try) добавить резолв в переменную уровня функции. Поскольку `mcp_endpoint` берётся в try-блоке (строки 1240–1283), резолв вынеси СРАЗУ ПОСЛЕ этого try (после строки 1283), best-effort:

```python
    # Multi-base (B.4): контекст конфигурации канала — для инжекта в промпт
    # и подстановки configuration в buddy.search_its. Best-effort.
    try:
        channel_config_ctx = await resolve_channel_typical_context(db, request.channel_id)
    except Exception:
        logger.exception("resolve_channel_typical_context упал — без конфо-контекста")
        from app.orchestrator.channel_config import ChannelTypicalContext
        channel_config_ctx = ChannelTypicalContext(None, None, None, None, None)
```

- [ ] **Step 2: Прокинуть в промпт**

Изменить вызов на строке 1381:

```python
    full_system_prompt = _build_full_system_prompt(
        memory_system_block(memory_manager),
        _render_skills_block(skill_store, skill_usage),
        render_todos_for_prompt(session_id),
        mentions_block=mentions_context_block,
        config_block=_build_config_block(channel_config_ctx),
    )
```

- [ ] **Step 3: Прогнать существующие loop-тесты (регрессия)**

Run: `pytest tests/ -k "loop" -v`
Expected: PASS — конфо-контекст пуст в тестовых каналах (configuration NULL) → блок пустой → промпт как раньше. Если какой-то тест ассертит точный system prompt — обнови ожидание (блок пустой, добавочного текста нет).

- [ ] **Step 4: Commit**

```bash
git add backend/app/orchestrator/loop.py
git commit -m "feat(loop): резолв channel_config_ctx и инжект config-блока в system prompt"
```

### Task 5.4: Инжект `configuration` в `buddy.search_its` / `buddy.fetch_its`

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (блок `if tool_name.startswith("buddy."):` строки 1959–1982)
- Test: `backend/tests/test_loop_buddy_config.py` (создать — юнит на helper)

- [ ] **Step 1: Написать падающий тест helper'а**

Создать `backend/tests/test_loop_buddy_config.py`:

```python
from app.orchestrator.channel_config import ChannelTypicalContext
from app.orchestrator.loop import _inject_buddy_configuration


def test_inject_adds_configuration_for_search_its():
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    args = {"query": "настройка обеспечения"}
    out = _inject_buddy_configuration("buddy.search_its", args, ctx)
    assert out["configuration"] == "Комплексная автоматизация"
    assert out["query"] == "настройка обеспечения"


def test_inject_does_not_override_explicit_configuration():
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    args = {"query": "x", "configuration": "Бухгалтерия предприятия"}
    out = _inject_buddy_configuration("buddy.search_its", args, ctx)
    assert out["configuration"] == "Бухгалтерия предприятия"


def test_inject_noop_for_non_buddy_and_missing_ctx():
    ctx_empty = ChannelTypicalContext(None, None, None, None, None)
    args = {"query": "x"}
    assert "configuration" not in _inject_buddy_configuration("buddy.search_its", args, ctx_empty)
    ctx = ChannelTypicalContext("КА 2.5", "_ka2_25_92", "КА 2.5",
                                "Комплексная автоматизация", "auto")
    assert "configuration" not in _inject_buddy_configuration("buddy.other", dict(args), ctx)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_loop_buddy_config.py -v`
Expected: FAIL — `ImportError: cannot import name '_inject_buddy_configuration'`.

- [ ] **Step 3: Реализовать helper + встроить в loop**

В `loop.py` добавить helper (рядом с `_build_config_block`):

```python
def _inject_buddy_configuration(tool_name: str, tool_args: dict, ctx) -> dict:
    """Подставляет configuration=<buddy-имя конфы> в buddy.search_its/fetch_its.

    Фикс -32603 (Напарник на «голом» запросе без configuration). Не перетирает
    явно переданный LLM configuration. No-op для прочих buddy.* и пустого ctx.
    """
    if tool_name not in ("buddy.search_its", "buddy.fetch_its"):
        return tool_args
    if ctx is None or not ctx.buddy_config_name:
        return tool_args
    if tool_args.get("configuration"):
        return tool_args
    return {**tool_args, "configuration": ctx.buddy_config_name}
```

Встроить в блок buddy (после прохождения кап-проверки, перед маршрутизацией в MCP). Конкретно — в существующем блоке на строке 1959, ПОСЛЕ `if buddy_calls_so_far >= MAX_BUDDY_CALLS_PER_TURN: ... continue` (после строки 1982) добавить:

```python
                    # B.4: подставляем detected-конфу, если LLM не передал —
                    # иначе buddy.search_its даёт -32603 на «голом» запросе.
                    tool_args = _inject_buddy_configuration(
                        tool_name, tool_args, channel_config_ctx
                    )
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_loop_buddy_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_buddy_config.py
git commit -m "feat(loop): инжект configuration в buddy.search_its/fetch_its (фикс -32603)"
```

### Task 5.5: Кап `search_typical_objects` за ход + «данных достаточно»

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (новая константа рядом с `MAX_BUDDY_CALLS_PER_TURN` строка 205; гейт в блоке typical-tools перед строкой 1833)
- Test: `backend/tests/test_loop_typical_cap.py` (создать — юнит на helper-предикат)

- [ ] **Step 1: Написать падающий тест**

Создать `backend/tests/test_loop_typical_cap.py`:

```python
from app.orchestrator.loop import (
    MAX_TYPICAL_SEARCH_CALLS_PER_TURN,
    _typical_search_budget_exceeded,
)


def test_cap_constant_reasonable():
    assert 1 <= MAX_TYPICAL_SEARCH_CALLS_PER_TURN <= 10


def test_budget_not_exceeded_below_cap():
    calls = [{"name": "search_typical_objects"}] * (MAX_TYPICAL_SEARCH_CALLS_PER_TURN - 1)
    assert _typical_search_budget_exceeded(calls) is False


def test_budget_exceeded_at_cap():
    calls = [{"name": "search_typical_objects"}] * MAX_TYPICAL_SEARCH_CALLS_PER_TURN
    assert _typical_search_budget_exceeded(calls) is True


def test_other_tools_do_not_count():
    calls = [{"name": "execute_query"}] * 20 + [{"name": "search_typical_objects"}]
    assert _typical_search_budget_exceeded(calls) is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_loop_typical_cap.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Реализовать**

В `loop.py` добавить рядом со строкой 205:

```python
# 2026-06-05 (Multi-base B.4): кап вызовов search_typical_objects за ход. Модель
# при мисматче конфы молотила 18× search_typical (запрос 3:53). После кап-порога
# не выполняем поиск, а возвращаем модели подсказку «данных достаточно, отвечай».
# Отдельно от MAX_BUDDY_CALLS_PER_TURN (тот — внешний Напарник, это — RAG-граф).
MAX_TYPICAL_SEARCH_CALLS_PER_TURN = 6
```

Добавить helper-предикат (рядом с `_build_config_block`):

```python
def _typical_search_budget_exceeded(accumulated_tool_calls: list[dict]) -> bool:
    """True, если за ход уже сделано >= кап вызовов search_typical_objects."""
    n = sum(
        1 for c in accumulated_tool_calls
        if c.get("name") == "search_typical_objects"
    )
    return n >= MAX_TYPICAL_SEARCH_CALLS_PER_TURN
```

Встроить гейт в блок typical-tools. В начале блока `if is_typical_tool(tool_name):` (строка 1833), сразу внутри, ДО `dispatch_typical_tool`:

```python
                if is_typical_tool(tool_name):
                    # B.4: кап на search_typical_objects (анти-thrashing).
                    if (
                        tool_name == "search_typical_objects"
                        and _typical_search_budget_exceeded(accumulated_tool_calls)
                    ):
                        duration_ms = int((time.monotonic() - start_ts) * 1000)
                        cap_msg = (
                            f"Лимит поиска по типовой ({MAX_TYPICAL_SEARCH_CALLS_PER_TURN}) "
                            "за один ответ исчерпан. Данных достаточно — сформируй ответ "
                            "по уже найденному, не вызывай search_typical_objects снова."
                        )
                        yield format_sse("tool_result", ToolResultEvent(
                            id=tool_id, ok=False, error=cap_msg, duration_ms=duration_ms,
                        ))
                        accumulated_tool_calls.append({
                            "id": tool_id, "name": tool_name, "args": tool_args,
                            "result": None, "error": cap_msg, "duration_ms": duration_ms,
                        })
                        messages.append({
                            "role": "tool", "tool_call_id": tool_id, "content": cap_msg,
                        })
                        continue
                    tt_ok, tt_result, tt_error = await dispatch_typical_tool(
                        db, tool_name, tool_args,
                    )
                    ...  # остальное без изменений
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_loop_typical_cap.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_typical_cap.py
git commit -m "feat(loop): кап search_typical_objects за ход (анти-thrashing, B.4)"
```

### Task 5.6: B.4d — стиль ответа для how-to (практические шаги, не дамп)

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (SYSTEM_PROMPT — секция ФОРМАТ ОТВЕТА, строки 329–334)
- Test: `backend/tests/test_loop_system_prompt.py` (дополнить)

- [ ] **Step 1: Написать падающий тест**

Дополнить `backend/tests/test_loop_system_prompt.py`:

```python
from app.orchestrator.loop import SYSTEM_PROMPT


def test_system_prompt_has_howto_style_guidance():
    # B.4d: для «как сделать X» — практические шаги, не дамп реквизитов.
    assert "практическ" in SYSTEM_PROMPT.lower()
    assert "как сделать" in SYSTEM_PROMPT.lower() or "how-to" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_loop_system_prompt.py::test_system_prompt_has_howto_style_guidance -v`
Expected: FAIL — текста ещё нет.

- [ ] **Step 3: Реализовать**

В `SYSTEM_PROMPT`, в секции `═══════ ФОРМАТ ОТВЕТА ═══════` (после строки 334 `— TL;DR в 1 строке...`), добавить:

```
— Для вопросов «КАК СДЕЛАТЬ X» (настройка, оформление операции, методика): отвечай ПРАКТИЧЕСКИМИ ШАГАМИ — куда зайти, что включить, в каком порядке. НЕ вываливай полный список реквизитов/метаданных объекта, если пользователь не просил структуру. Дамп реквизитов — только на прямой вопрос «какие реквизиты / структура».
```

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_loop_system_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_system_prompt.py
git commit -m "feat(loop): B.4d стиль ответа how-to — практические шаги, не дамп реквизитов"
```

---

## Phase 6 — Frontend: бейдж конфигурации + override + состояния

### Task 6.1: Тип `configuration_source` + override в API-клиенте

**Files:**
- Modify: `frontend/lib/types.ts` (тип подключения, рядом со строкой 228 `configuration?: string | null`)
- Modify: `frontend/lib/api.ts` (функция обновления подключения / новый `updateConnectionConfiguration`)
- Test: `frontend/lib/__tests__/api.test.ts` (создать/дополнить — проверь `ls frontend/lib/__tests__`)

- [ ] **Step 1: Написать падающий тест**

Дополнить (или создать) `frontend/lib/__tests__/api.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { updateConnectionConfiguration } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("updateConnectionConfiguration", () => {
  it("PUT /connections/{id} с configuration + source", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "c1", configuration: "КА 2.5", configuration_source: "manual" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const res = await updateConnectionConfiguration("c1", "КА 2.5", "manual");
    expect(res.configuration).toBe("КА 2.5");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("PUT");
    expect(JSON.parse(opts.body)).toMatchObject({
      configuration: "КА 2.5",
      configuration_source: "manual",
    });
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `npx vitest run lib/__tests__/api.test.ts`
Expected: FAIL — `updateConnectionConfiguration` не экспортируется.

- [ ] **Step 3: Реализовать**

В `frontend/lib/types.ts` — в типе подключения (где `configuration?: string | null`, строка 228) добавить:

```ts
  configuration_source?: string | null;
```

В `frontend/lib/api.ts` добавить (использовать существующий `apiBase()`/`API_BASE` паттерн этого файла — сверься с соседними функциями):

```ts
export async function updateConnectionConfiguration(
  connId: string,
  configuration: string,
  source: "manual" | "confirmed",
): Promise<MCPConnection> {
  const res = await fetch(`${API_BASE}/connections/${connId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configuration, configuration_source: source }),
  });
  if (!res.ok) {
    throw new Error(`Не удалось сохранить конфигурацию (${res.status})`);
  }
  return res.json();
}
```

(`MCPConnection` импортируй из `@/lib/types`, если не импортирован. `API_BASE` — как в остальных функциях api.ts.)

- [ ] **Step 4: Запустить**

Run: `npx vitest run lib/__tests__/api.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/__tests__/api.test.ts
git commit -m "feat(frontend): тип configuration_source + updateConnectionConfiguration API"
```

### Task 6.2: Компонент `ConfigurationBadge` (детект + состояния + override)

**Files:**
- Create: `frontend/components/shell/ConfigurationBadge.tsx`
- Test: `frontend/components/shell/__tests__/ConfigurationBadge.test.tsx` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `frontend/components/shell/__tests__/ConfigurationBadge.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfigurationBadge } from "@/components/shell/ConfigurationBadge";

const base = { id: "c1", name: "B", endpoint: "http://x/mcp" } as any;

describe("ConfigurationBadge", () => {
  it("показывает detected-конфу с пометкой (авто)", () => {
    render(<ConfigurationBadge connection={{ ...base, configuration: "КА 2.5", configuration_source: "auto" }} onOverride={vi.fn()} />);
    expect(screen.getByText(/КА 2\.5/)).toBeInTheDocument();
    expect(screen.getByText(/авто/i)).toBeInTheDocument();
  });

  it("ambiguous → знак вопроса / требует подтверждения", () => {
    render(<ConfigurationBadge connection={{ ...base, configuration: "КА 2.5", configuration_source: "ambiguous" }} onOverride={vi.fn()} />);
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "ambiguous");
  });

  it("failed → состояние повтора (↻)", () => {
    render(<ConfigurationBadge connection={{ ...base, configuration: null, configuration_source: "failed" }} onOverride={vi.fn()} />);
    expect(screen.getByTestId("config-badge")).toHaveAttribute("data-state", "failed");
  });

  it("custom → Самописная", () => {
    render(<ConfigurationBadge connection={{ ...base, configuration: "Самописная", configuration_source: "custom" }} onOverride={vi.fn()} />);
    expect(screen.getByText(/Самописная/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `npx vitest run components/shell/__tests__/ConfigurationBadge.test.tsx`
Expected: FAIL — компонента нет.

- [ ] **Step 3: Реализовать компонент**

Создать `frontend/components/shell/ConfigurationBadge.tsx`. Использовать brand-токены (Signal `var(--accent)`, `var(--bg-2)`, `var(--warning)`, `var(--error)`), dropdown по образцу `TypicalSelector.tsx`, без декоративных эффектов (design-bans). 7 типовых-вариантов override + «Самописная»:

```tsx
"use client";

import { useState } from "react";
import { ChevronDown, Layers, RotateCw } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { MCPConnection } from "@/lib/types";

const OVERRIDE_OPTIONS = [
  "УТ 11.5", "ERP 2.5", "КА 2.5", "БП 3.0",
  "ЗУП 3.1", "УСО (ЖКХ)", "Самописная",
];

type State = "auto" | "confirmed" | "manual" | "ambiguous" | "failed" | "custom" | "none";

function deriveState(conn: MCPConnection): State {
  const s = (conn.configuration_source ?? null) as State | null;
  if (s) return s;
  return conn.configuration ? "confirmed" : "none";
}

const SOURCE_LABEL: Record<string, string> = {
  auto: "авто", confirmed: "подтверждено", manual: "вручную",
  ambiguous: "уточните", failed: "не завершено", custom: "самописная",
};

type Props = {
  connection: MCPConnection;
  onOverride: (configuration: string) => void;
  onRetry?: () => void;
};

export function ConfigurationBadge({ connection, onOverride, onRetry }: Props) {
  const [open, setOpen] = useState(false);
  const state = deriveState(connection);
  const label =
    state === "failed" ? "детекция…" : connection.configuration ?? "—";

  const toneClass =
    state === "failed"
      ? "border-[var(--error-40)] bg-[var(--error-12)] text-[var(--error)]"
      : state === "ambiguous"
      ? "border-[var(--warning-40)] bg-[var(--warning-12)] text-[var(--warning)]"
      : connection.configuration && state !== "custom" && state !== "none"
      ? "border-[var(--accent-32)] bg-[var(--accent-08)] text-[var(--fg-1)]"
      : "border-[var(--bd-2)] bg-[var(--bg-2)] text-[var(--fg-2)]";

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          data-testid="config-badge"
          data-state={state}
          className={cn(
            "flex items-center gap-2 h-9 px-3 rounded-md border transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-[var(--accent-20)]",
            toneClass,
          )}
          title="Конфигурация базы — нажми, чтобы изменить вручную"
        >
          {state === "failed" ? (
            <RotateCw className="h-3.5 w-3.5 flex-none" />
          ) : (
            <Layers className="h-3.5 w-3.5 flex-none" />
          )}
          <span
            className="text-[10px] tracking-[0.16em] uppercase flex-none"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            Конфа
          </span>
          <span className="text-[12.5px] font-semibold truncate max-w-[140px]">
            {label}
          </span>
          {SOURCE_LABEL[state] && state !== "failed" && (
            <span className="text-[10px] text-[var(--fg-3)]">
              ({SOURCE_LABEL[state]})
            </span>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)] flex-none" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="center" className="min-w-[260px]">
        <DropdownMenuLabel>Конфигурация базы</DropdownMenuLabel>
        {state === "failed" && onRetry && (
          <>
            <DropdownMenuItem onSelect={() => { setOpen(false); onRetry(); }}>
              <RotateCw className="h-3.5 w-3.5 mr-2" /> Повторить детекцию
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <div className="px-3 pb-1.5 text-[11px] text-[var(--fg-3)] leading-snug">
          Указать вручную, если детекция ошиблась:
        </div>
        {OVERRIDE_OPTIONS.map((opt) => (
          <DropdownMenuItem
            key={opt}
            className={cn(
              "cursor-pointer",
              connection.configuration === opt && "bg-[var(--accent-08)]",
            )}
            onSelect={() => { setOpen(false); onOverride(opt); }}
          >
            {opt}
            {connection.configuration === opt && (
              <span className="ml-auto text-[var(--accent)]">✓</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 4: Запустить**

Run: `npx vitest run components/shell/__tests__/ConfigurationBadge.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/shell/ConfigurationBadge.tsx frontend/components/shell/__tests__/ConfigurationBadge.test.tsx
git commit -m "feat(frontend): ConfigurationBadge — детект конфы + состояния (auto/ambiguous/failed/custom) + override"
```

### Task 6.3: Вмонтировать бейдж в Header рядом с селектором канала

**Files:**
- Modify: header-компонент (найди: `grep -rl "ChannelSelector\|TypicalSelector" frontend/components/shell frontend/app`)
- Test: визуальный smoke в Task 7.x / финальный (Playwright опционально). Для шага — unit на рендер контейнера, если у header есть тест; иначе пропусти unit и проверь сборкой.

- [ ] **Step 1: Найти место монтирования**

Run: `grep -rn "TypicalSelector" frontend/components frontend/app`
Найди компонент Header/Topbar, где рендерится `<TypicalSelector />`. Это же место — для `<ConfigurationBadge />` (рядом, слева от TypicalSelector: «какая это база» логически идёт раньше «сравнить с типовой»).

- [ ] **Step 2: Вмонтировать**

В найденном header-компоненте:
- получить активное подключение (по тому же паттерну, что текущий селектор канала — вероятно из хука/контекста подключений; сверься, как берётся `configuration` сейчас);
- отрендерить:
```tsx
{activeConnection && (
  <ConfigurationBadge
    connection={activeConnection}
    onOverride={(cfg) => handleConfigOverride(activeConnection.id, cfg)}
    onRetry={() => pingConnection(activeConnection.id)}
  />
)}
```
- `handleConfigOverride` вызывает `updateConnectionConfiguration(id, cfg, "manual")` и обновляет локальный стейт подключений (рефетч списка или оптимистично).

- [ ] **Step 3: Сборка + существующие тесты**

Run (frontend): `npm run build`
Expected: успешная сборка. Затем: `npx vitest run components/shell`
Expected: PASS (существующие тесты shell не сломаны).

- [ ] **Step 4: Commit**

```bash
git add frontend/components frontend/app
git commit -m "feat(frontend): ConfigurationBadge в Header + ручной override через updateConnectionConfiguration"
```

---

## Phase 7 — Фикс бага индексера get_metadata (separable, для @-mention каталога)

> Отдельный дефект (полный каталог = 0 объектов на любой базе с этим Toolkit). НЕ на критпути онбординга (детект идёт через пробы Phase 3), но чинит «Изучить базу»/@-mention. Может уехать отдельным PR.

### Task 7.1: `bulk_refresh_metadata_cache` — перечисление через meta_type вместо detail:False

**Files:**
- Modify: `backend/app/knowledge/indexer.py` (`bulk_refresh_metadata_cache` строки 419–567; новая helper-функция перечисления)
- Test: `backend/tests/test_knowledge_indexer.py` (дополнить — там уже есть фейковый MCP-паттерн)

- [ ] **Step 1: Написать падающий тест**

Сначала посмотри существующие фейки в `backend/tests/test_knowledge_indexer.py` (как мокается MCPClient/call_tool). Дополни тестом, что indexer перечисляет объекты по meta_type, а не зовёт `get_metadata(detail=False)`:

```python
@pytest.mark.asyncio
async def test_bulk_refresh_enumerates_by_meta_type(db, monkeypatch):
    """Indexer перечисляет объекты через meta_type=*, не detail:False (баг)."""
    calls = []

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def initialize(self): ...
        async def list_tools(self): return [{"name": "get_metadata"}]
        async def call_tool(self, name, args):
            calls.append(args)
            # эмулируем list-mode: вернуть пару объектов
            return {"success": True, "data": [
                {"ПолноеИмя": "Документ.РеализацияТоваровУслуг", "Синоним": "Реализация"},
                {"ПолноеИмя": "Справочник.Контрагенты", "Синоним": "Контрагенты"},
            ]}

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", FakeClient)
    progress = await bulk_refresh_metadata_cache(db, "ch", "http://x/mcp")
    assert progress.status == "done"
    assert progress.objects_written > 0
    # критично: ни один вызов не должен полагаться на detail:False как способ
    # перечисления — должен присутствовать meta_type.
    assert any("meta_type" in c for c in calls)
    assert all(c.get("detail") is not False or "meta_type" in c for c in calls)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_knowledge_indexer.py::test_bulk_refresh_enumerates_by_meta_type -v`
Expected: FAIL — текущий код зовёт `call_tool("get_metadata", {"detail": False})` (строка 476), `meta_type` отсутствует.

- [ ] **Step 3: Реализовать перечисление по meta_type**

Добавить в `indexer.py` константу + helper (перед `bulk_refresh_metadata_cache`):

```python
# Корневые типы метаданных для полного перечисления каталога (limit≤1000 —
# валидация 1C MCP). detail:False даёт СВОДКУ (счётчики по типам), не объекты —
# поэтому перечисляем постранично по каждому ключевому meta_type.
_ENUM_META_TYPES = (
    "Документ", "Справочник", "РегистрНакопления", "РегистрСведений",
    "РегистрБухгалтерии", "РегистрРасчета", "ПланСчетов", "ПланВидовХарактеристик",
    "ПланВидовРасчета", "Перечисление", "Отчет", "Обработка", "Константа",
    "БизнесПроцесс", "Задача", "ЖурналДокументов", "ОбщийМодуль", "Роль",
    "Подсистема", "Последовательность",
)
_ENUM_PAGE_LIMIT = 1000


async def _enumerate_all_objects(client) -> list[NormalizedMetadata]:
    """Перечисляет объекты по каждому meta_type (list-mode), агрегирует.

    get_metadata(meta_type="<Тип>", limit=1000) — постранично по типам.
    name_mask не задаём (нужен весь каталог). Дедуп по object_path.
    """
    seen: dict[str, NormalizedMetadata] = {}
    for meta_type in _ENUM_META_TYPES:
        try:
            result = await client.call_tool(
                "get_metadata",
                {"meta_type": meta_type, "limit": _ENUM_PAGE_LIMIT},
            )
        except Exception:  # noqa: BLE001 — один тип не должен валить весь индекс
            logger.warning("Перечисление meta_type=%s упало — пропускаю", meta_type)
            continue
        for obj in parse_metadata_result(result):
            seen[obj.object_path] = obj
    return list(seen.values())
```

Заменить в `bulk_refresh_metadata_cache` строку 476 (`result = await client.call_tool("get_metadata", {"detail": False})` + `objects = parse_metadata_result(result)`, строки 476–477) на:

```python
            objects = await _enumerate_all_objects(client)
```

(Остальное тело — diff/детект конфы — без изменений: оно работает над `objects`.)

- [ ] **Step 4: Запустить**

Run: `pytest tests/test_knowledge_indexer.py tests/test_knowledge_indexer_incremental.py -v`
Expected: PASS. Проверь, что существующие тесты, ожидавшие `call_tool(..., {"detail": False})`, обновлены под новый контракт (если такие были — поправь их ожидания на meta_type-перечисление).

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/indexer.py backend/tests/test_knowledge_indexer.py
git commit -m "fix(indexer): перечисление каталога через meta_type (detail:False давал 0 объектов)"
```

---

## Финальная верификация (после всех фаз)

### Task F.1: Полный backend + frontend прогон

- [ ] **Backend:** `pytest backend/tests -q` → все зелёные.
- [ ] **Frontend unit:** из `frontend/` → `npx vitest run` → зелёные.
- [ ] **Frontend build:** `npm run build` → без ошибок.
- [ ] **Quality gate:** `pwsh .claude/skills/awd-quality-gate/scripts/gate.ps1` → PASS (4/4; Playwright требует поднятых серверов).

### Task F.2: Живой smoke на КА Демо (Success Criteria дизайна)

Подними сервера (`awd-dev-up`), в Chrome:
- [ ] Подключи/пингани КА-базу (КА Демо :6012) → в течение ≤ T сек бейдж = «КА 2.5» (НЕ УТ). [SC-1, SC-2]
- [ ] Спроси «как делается настройка обеспечения» → ответ ссылается на КА, ≤ 8 tool-вызовов, ≤ 60 сек, практические шаги (не дамп реквизитов). [SC-3]
- [ ] Живой `execute_query` на свежей базе мгновенен (регрессии нет). [SC-5]
- [ ] (Если воспроизводимо) сбой MCP при детекте → бейдж «детекция не завершена ↻», не ложный УТ. [SC-6]

### Task F.3: Замер латентности (The Assignment, Open Q1)

- [ ] Прогнать `_enumerate_all_objects` (через «Изучить базу») на РЕАЛЬНОЙ большой базе (КА/ERP, не demo) → записать: объектов + секунд. Уточнить порог `T` в Success Criteria и при необходимости `HIGH_CONFIDENCE`/`MARGIN_DELTA` (Task 1.4) на 4 demo-базах.

---

## Открытые вопросы дизайна, перенесённые в реализацию (решать данными, не угадывать)

1. **Пороги `HIGH_CONFIDENCE=0.50` / `MARGIN_DELTA=0.30`** (Task 1.4) — стартовые. Подтвердить/подстроить на 4 demo-базах (КА/УТ/ERP/БП) в Task F.2.
2. **buddy `configuration` строка** (`_KEY_TO_BUDDY_CONFIG`, Task 5.1) — «Управление торговлей» подтверждено в тесте; «Комплексная автоматизация» vs «КА 2.5» для buddy — сверить живым вызовом в Task F.2. Если buddy ждёт иное — поправить ОДИН dict.
3. **Где показывать confirm для `ambiguous`** — в этом плане бейдж показывает состояние «уточните» + override-выпадашка (минимально, без right-rail per design-bans). Полноценный confirm-баннер/диалог — отдельная доработка, если по UX-проверке нужно.
4. **Латентность полного каталога** (Task 7.1, Open Q1) — детект-пробы (Phase 3) уже sub-second; полный `_enumerate_all_objects` на огромной базе не замерен → Task F.3.
