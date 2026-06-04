# Seed Skills Pack — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Встроенная ИИ Аналитика стартует НЕ холодной — при первом запуске уже знает базовые проверенные плейбуки аналитика 1С (анти-галлюцинация, движения регистров, RLS, журнал, ОПП-реестр), отфильтрованные под тип конфигурации канала.

**Architecture:** Новый read-only `MemoryProvider` (`SeedSkillProvider`), который грузит curated-скиллы из бандл-каталога `app/skills/seed/*.md`, фильтрует по типу конфигурации канала (`applies_to`) и отдаёт их через `system_prompt_block()`. Регистрируется в `MemoryManager` рядом с `MarkdownStore`. Скиллы immutable, едут с приложением, куратор их не трогает (они вне `SkillStore` → provenance менять не нужно). Self-learning `agent`-скиллы продолжают расти поверх (подход C — гибрид).

**Tech Stack:** Python 3.12, FastAPI, pytest. Ноль новых зависимостей (front-matter парсим руками, как уже делают `skill_store`/`bundles`).

**Scope (YAGNI):** Только always-on seed-ядро (5 скиллов) + провайдер + фильтр по конфиге + тесты. Bundles-слэши (`/закрытие-месяца`) — ОТДЕЛЬНЫЙ follow-up план (механизм `BundleRegistry` уже есть, наполнение поверх seed-скиллов — позже).

**Открытые допущения (на ревью пользователя):**
- Подход **C** (гибрид) принят по умолчанию (рекомендация brainstorming; MCQ был отклонён — двигаюсь на разумном дефолте).
- v1-набор = 5 скиллов (см. ниже). Расширение — после обкатки.
- `config_kind` для клиентских каналов (UUID) в v1 = `None` → инжектятся только `applies_to: ["*"]`-скиллы (безопасный дефолт: не подсовывать ERP-совет неизвестной базе). Детект конфигурации per-channel для не-типовых каналов — follow-up.

---

## File Structure

| Файл | Ответственность | Действие |
|---|---|---|
| `backend/app/skills/seed_provider.py` | `SeedSkill` (модель+парсер front-matter), `load_seed_skills()`, `SeedSkillProvider(MemoryProvider)` | Create |
| `backend/app/skills/seed/*.md` | Контент seed-скиллов (5 шт.) | Create |
| `backend/app/orchestrator/memory_integration.py` | Регистрация `SeedSkillProvider` в `MemoryManager` + резолв `config_kind` | Modify (`:29-31`) |
| `backend/tests/test_seed_provider.py` | Юнит-тесты парсинга/фильтра/инжекта/edge-cases | Create |

---

## Task 1: SeedSkill модель + парсер front-matter

**Files:**
- Create: `backend/app/skills/seed_provider.py`
- Test: `backend/tests/test_seed_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_seed_provider.py
from app.skills.seed_provider import SeedSkill, parse_seed_skill


def test_parse_seed_skill_basic():
    text = (
        "---\n"
        "id: query-discipline\n"
        "title: Дисциплина запроса\n"
        "applies_to: [\"*\"]\n"
        "tags: [query, grounding]\n"
        "---\n"
        "\n"
        "Сначала get_metadata, потом execute_query. Не выдумывай имена таблиц.\n"
    )
    skill = parse_seed_skill(text)
    assert skill.id == "query-discipline"
    assert skill.title == "Дисциплина запроса"
    assert skill.applies_to == ["*"]
    assert "get_metadata" in skill.body
    assert skill.applies(None) is True          # "*" инжектится всегда
    assert skill.applies("erp25") is True


def test_parse_seed_skill_config_specific():
    text = (
        "---\n"
        "id: opp-reestr\n"
        "title: ОПП без шапки\n"
        "applies_to: [\"erp25\", \"ka2\"]\n"
        "---\n"
        "Тело.\n"
    )
    skill = parse_seed_skill(text)
    assert skill.applies("erp25") is True
    assert skill.applies("ut115") is False
    assert skill.applies(None) is False          # неизвестная база → не подсовываем


def test_parse_seed_skill_missing_id_raises():
    import pytest
    with pytest.raises(ValueError, match="id"):
        parse_seed_skill("---\ntitle: x\n---\nbody\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.skills.seed_provider'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/skills/seed_provider.py
"""SeedSkillProvider — предустановленные («seed») навыки аналитика 1С.

В отличие от SkillStore (agent/user, мутабельные, per-channel), seed-скиллы:
- immutable, едут с приложением (каталог app/skills/seed/*.md);
- куратор их НЕ трогает (они вне SkillStore → provenance не нужен);
- фильтруются по типу конфигурации канала через front-matter `applies_to`.

Формат файла (front-matter руками, без PyYAML — как skill_store/bundles):
    ---
    id: query-discipline
    title: Дисциплина запроса
    applies_to: ["*"]            # "*" = любая конфигурация
    tags: [query, grounding]
    ---

    <markdown-тело плейбука>
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.memory.provider import MemoryProvider

logger = logging.getLogger(__name__)


def _parse_inline_list(value: str) -> list[str]:
    """`["a", "b"]` или `[a, b]` → ['a', 'b']. Пустой/мусор → []."""
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    out: list[str] = []
    for part in v.split(","):
        p = part.strip().strip("\"'")
        if p:
            out.append(p)
    return out


@dataclass
class SeedSkill:
    """Один предустановленный навык."""

    id: str
    title: str = ""
    applies_to: list[str] = field(default_factory=lambda: ["*"])
    tags: list[str] = field(default_factory=list)
    body: str = ""

    def applies(self, config_kind: str | None) -> bool:
        """`*` инжектится всегда; иначе только если kind в applies_to.

        config_kind=None (неизвестная база) → инжектятся только `*`-скиллы.
        """
        if "*" in self.applies_to:
            return True
        if config_kind is None:
            return False
        return config_kind in self.applies_to


def parse_seed_skill(text: str) -> SeedSkill:
    """Парсит md с front-matter. ValueError если нет `id`."""
    if not text.startswith("---"):
        raise ValueError("seed skill: нет front-matter (должен начинаться с '---')")
    _, _, rest = text.partition("---\n")
    fm, sep, body = rest.partition("\n---")
    if not sep:
        raise ValueError("seed skill: незакрытый front-matter")

    sid = ""
    title = ""
    applies_to: list[str] = ["*"]
    tags: list[str] = []
    for line in fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "id":
            sid = val.strip("\"'")
        elif key == "title":
            title = val.strip("\"'")
        elif key == "applies_to":
            applies_to = _parse_inline_list(val) or ["*"]
        elif key == "tags":
            tags = _parse_inline_list(val)

    if not sid:
        raise ValueError("seed skill: отсутствует обязательный 'id'")
    return SeedSkill(
        id=sid, title=title or sid, applies_to=applies_to, tags=tags,
        body=body.lstrip("\n").strip("- \n") if body else "",
    )
```

> Примечание по парсингу тела: `body.partition("\n---")` отрезает front-matter; ведущие переводы строк и закрывающие дефисы front-matter снимаем через `lstrip`/`strip`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -v`
Expected: PASS (3 теста)

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/seed_provider.py backend/tests/test_seed_provider.py
git commit -m "feat(skills): SeedSkill модель + парсер front-matter"
```

---

## Task 2: load_seed_skills() + SeedSkillProvider

**Files:**
- Modify: `backend/app/skills/seed_provider.py`
- Test: `backend/tests/test_seed_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# добавить в tests/test_seed_provider.py
from pathlib import Path
from app.skills.seed_provider import load_seed_skills, SeedSkillProvider


def _write(dir_: Path, name: str, text: str) -> None:
    (dir_ / name).write_text(text, encoding="utf-8")


def test_load_seed_skills_skips_malformed(tmp_path):
    _write(tmp_path, "ok.md",
           "---\nid: a\ntitle: A\napplies_to: [\"*\"]\n---\nтело A\n")
    _write(tmp_path, "bad.md", "нет фронтматтера\n")
    _write(tmp_path, "ignore.txt", "не md")
    skills = load_seed_skills(tmp_path)
    assert [s.id for s in skills] == ["a"]          # bad.md и .txt пропущены


def test_provider_system_prompt_filters_by_config(tmp_path):
    _write(tmp_path, "g.md",
           "---\nid: g\ntitle: Общий\napplies_to: [\"*\"]\n---\nобщее тело\n")
    _write(tmp_path, "e.md",
           "---\nid: e\ntitle: ERP\napplies_to: [\"erp25\"]\n---\nerp тело\n")

    p_erp = SeedSkillProvider(seed_dir=tmp_path, config_kind="erp25")
    p_erp.initialize()
    block_erp = p_erp.system_prompt_block()
    assert "Общий" in block_erp and "ERP" in block_erp

    p_unknown = SeedSkillProvider(seed_dir=tmp_path, config_kind=None)
    p_unknown.initialize()
    block_unknown = p_unknown.system_prompt_block()
    assert "Общий" in block_unknown and "ERP" not in block_unknown


def test_provider_empty_dir_returns_empty(tmp_path):
    p = SeedSkillProvider(seed_dir=tmp_path / "missing", config_kind=None)
    p.initialize()
    assert p.system_prompt_block() == ""
    assert p.is_external is False
    assert p.name == "seed-skills"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -k "load or provider" -v`
Expected: FAIL — `ImportError: cannot import name 'load_seed_skills'`

- [ ] **Step 3: Write minimal implementation**

```python
# добавить в backend/app/skills/seed_provider.py

def load_seed_skills(dir_path: Path) -> list[SeedSkill]:
    """Грузит все *.md из dir_path. Битые файлы пропускает с warning.

    Сортировка по имени файла → детерминированный порядок в промпте.
    """
    skills: list[SeedSkill] = []
    if not dir_path.exists():
        return skills
    for path in sorted(dir_path.glob("*.md")):
        try:
            skills.append(parse_seed_skill(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            logger.warning("seed skill пропущен (%s): %s", path.name, exc)
    return skills


class SeedSkillProvider(MemoryProvider):
    """Read-only провайдер предустановленных навыков аналитика.

    Инжектит в SYSTEM_PROMPT те seed-скиллы, чей applies_to матчит
    config_kind канала ("*" — всегда). Tool'ов не предоставляет.
    """

    name = "seed-skills"
    is_external = False

    def __init__(self, seed_dir: Path, config_kind: str | None) -> None:
        self._dir = Path(seed_dir)
        self._config_kind = config_kind
        self._skills: list[SeedSkill] = []

    def initialize(self) -> None:
        self._skills = load_seed_skills(self._dir)
        logger.info(
            "SeedSkillProvider: %d скиллов загружено (config_kind=%s)",
            len(self._skills), self._config_kind,
        )

    def system_prompt_block(self) -> str:
        applicable = [s for s in self._skills if s.applies(self._config_kind)]
        if not applicable:
            return ""
        parts = ["## Базовые навыки аналитика 1С"]
        for s in applicable:
            parts.append(f"### {s.title}\n{s.body}".strip())
        return "\n\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -v`
Expected: PASS (6 тестов)

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/seed_provider.py backend/tests/test_seed_provider.py
git commit -m "feat(skills): load_seed_skills + SeedSkillProvider с фильтром по конфиге"
```

---

## Task 3: Контент seed-скиллов (5 шт.)

**Files:**
- Create: `backend/app/skills/seed/01-query-discipline.md`
- Create: `backend/app/skills/seed/02-register-movements.md`
- Create: `backend/app/skills/seed/03-rls-rights-audit.md`
- Create: `backend/app/skills/seed/04-event-log-triage.md`
- Create: `backend/app/skills/seed/05-realizations-no-header.md`
- Test: `backend/tests/test_seed_provider.py`

- [ ] **Step 1: Write the failing test (контент загружается и валиден)**

```python
# добавить в tests/test_seed_provider.py
def test_shipped_seed_pack_loads():
    from app.skills.seed_provider import load_seed_skills
    seed_dir = Path(__file__).resolve().parent.parent / "app" / "skills" / "seed"
    skills = load_seed_skills(seed_dir)
    ids = {s.id for s in skills}
    assert {"query-discipline", "register-movements", "rls-rights-audit",
            "event-log-triage", "realizations-no-header"} <= ids
    for s in skills:                       # все непустые и с телом
        assert s.title and s.body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py::test_shipped_seed_pack_loads -v`
Expected: FAIL — каталог пуст, `ids` не содержит ожидаемых

- [ ] **Step 3: Создать контент**

`backend/app/skills/seed/01-query-discipline.md`:
```markdown
---
id: query-discipline
title: Дисциплина запроса (анти-галлюцинация)
applies_to: ["*"]
tags: [query, grounding]
---

Перед `execute_query` всегда сначала уточни структуру через `get_metadata`
по нужному объекту. Никогда не выдумывай имена таблиц, реквизитов, регистров
и измерений — бери их только из метаданных. Если поле/объект не подтверждён
метаданными — скажи аналитику честно «такого объекта в этой базе нет», а не
строй запрос наугад. `Документ.*` и подобный синтаксис не существует.
```

`backend/app/skills/seed/02-register-movements.md`:
```markdown
---
id: register-movements
title: Движения регистров по документу
applies_to: ["*"]
tags: [registers, movements]
---

Чтобы показать, что именно провёл документ, не пересказывай его шапку — смотри
ДВИЖЕНИЯ. Для регистров накопления это таблица `<Документ>.RegisterRecords`
(набор записей движений) и сами регистры (Остатки/Обороты). Для вопросов
«куда списалось / откуда взялось» используй связку WRITES_TO (документ → регистр)
и READS_FROM (регистр → потребитель). Проверяй полноту: число строк движений
должно биться с табличной частью, иначе сообщи о расхождении.
```

`backend/app/skills/seed/03-rls-rights-audit.md`:
```markdown
---
id: rls-rights-audit
title: Аудит прав и RLS
applies_to: ["*"]
tags: [rights, rls, security]
---

На вопросы «кто может видеть/делать X», «почему пользователь не видит документ»
используй `get_access_rights` для роли/пользователя и разбирай право ПОИМЁННО
(Чтение/Изменение/Проведение/…), а не «в целом». Ограничения RLS проверяй
per-right: одно и то же РазрешениеНаОбъект может иметь разные RLS-условия на
разные права. Не делай вывод «доступа нет» без проверки конкретного права.
```

`backend/app/skills/seed/04-event-log-triage.md`:
```markdown
---
id: event-log-triage
title: Разбор журнала регистрации
applies_to: ["*"]
tags: [event-log, errors]
---

На «ошибки за период / что случилось вчера» используй `get_event_log` с явными
фильтрами: уровень (Ошибка/Предупреждение), период (дата от/до), при нужде —
пользователь/событие. Не угадывай период — уточни у аналитика, если он не задан.
В ответе группируй по тексту ошибки + считай частоту, а не вываливай сырой лог
построчно.
```

`backend/app/skills/seed/05-realizations-no-header.md`:
```markdown
---
id: realizations-no-header
title: Реестр реализаций «без шапки»
applies_to: ["erp25", "ka2", "ut115"]
tags: [query, sales, opp]
---

Запрос «покажи реализации/ОПП за <период> без шапки» означает: вывести СТРОКИ
табличной части (товары/услуги), а не реквизиты документа. Запрашивай табличную
часть документа реализации с отбором по периоду и (если задано) организации/
контрагенту, выбирай номенклатуру/количество/сумму. «Без шапки» = не группируй
по документу, отдавай построчную детализацию.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py::test_shipped_seed_pack_loads -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/seed/
git commit -m "feat(skills): seed-pack v1 — 5 проверенных плейбуков аналитика 1С"
```

---

## Task 4: Резолв config_kind по каналу

**Files:**
- Modify: `backend/app/skills/seed_provider.py`
- Test: `backend/tests/test_seed_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# добавить в tests/test_seed_provider.py
from app.skills.seed_provider import config_kind_from_channel_id


def test_config_kind_from_reserved_channel():
    assert config_kind_from_channel_id("_erp25_25_178") == "erp25"
    assert config_kind_from_channel_id("_ut115_18_193") == "ut115"


def test_config_kind_from_client_channel_is_none():
    # UUID-канал клиента — тип неизвестен синхронно → None
    assert config_kind_from_channel_id("900ae5ca-35e1-4e4a-93e8-83e0b516664d") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -k config_kind -v`
Expected: FAIL — `ImportError: cannot import name 'config_kind_from_channel_id'`

- [ ] **Step 3: Write minimal implementation**

```python
# добавить в backend/app/skills/seed_provider.py
import re as _re

# зарезервированные namespace типовых каналов: `_erp25_25_178` → "erp25"
_RESERVED_KIND_RE = _re.compile(r"^_(?P<kind>[a-z]+[0-9]+)_")


def config_kind_from_channel_id(channel_id: str) -> str | None:
    """Тип конфигурации из reserved-id типового канала, иначе None.

    Клиентские каналы (UUID и т.п.) → None (тип неизвестен синхронно;
    детект для них — отдельный follow-up).
    """
    m = _RESERVED_KIND_RE.match(channel_id or "")
    return m.group("kind") if m else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py -k config_kind -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/seed_provider.py backend/tests/test_seed_provider.py
git commit -m "feat(skills): config_kind_from_channel_id для фильтра seed-скиллов"
```

---

## Task 5: Проводка SeedSkillProvider в orchestrator

**Files:**
- Modify: `backend/app/orchestrator/memory_integration.py` (`:29-31`)
- Test: `backend/tests/test_seed_provider.py`

- [ ] **Step 1: Прочитать текущий код проводки**

Run: `sed -n '20,45p' backend/app/orchestrator/memory_integration.py`
Цель — увидеть точные строки вокруг `manager.add_provider(store)`, чтобы вставить регистрацию seed-провайдера сразу после MarkdownStore.

- [ ] **Step 2: Write the failing test (провайдер реально подключён к manager)**

```python
# добавить в tests/test_seed_provider.py
def test_memory_integration_registers_seed_provider(monkeypatch, tmp_path):
    from app.orchestrator import memory_integration as mi
    manager = mi.build_memory_manager(channel_id="_erp25_25_178")  # см. Step 3
    names = {p.name for p in manager.providers()}
    assert "seed-skills" in names
```

- [ ] **Step 3: Write minimal implementation**

В `memory_integration.py`, сразу после `manager.add_provider(store)` (строка ~31) добавить:

```python
    # Seed-скиллы: предустановленные навыки аналитика, фильтр по типу конфигурации
    from pathlib import Path
    from app.skills.seed_provider import (
        SeedSkillProvider,
        config_kind_from_channel_id,
    )

    seed_dir = Path(__file__).resolve().parent.parent / "skills" / "seed"
    manager.add_provider(
        SeedSkillProvider(
            seed_dir=seed_dir,
            config_kind=config_kind_from_channel_id(channel_id),
        )
    )
```

Если функция-обёртка ещё не выделена — извлечь существующее тело (создание `MemoryManager` + регистрация провайдеров) в `build_memory_manager(channel_id: str) -> MemoryManager` и вернуть `manager`, чтобы тест Step 2 мог её вызвать. Существующий вызывающий код заменить на `manager = build_memory_manager(channel_id)`.

- [ ] **Step 4: Run tests (модуль + регрессия памяти)**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_provider.py tests/test_orchestrator_loop_skills_integration.py -v`
Expected: PASS (новые + не сломалась существующая интеграция скиллов)

- [ ] **Step 5: Commit**

```bash
git add backend/app/orchestrator/memory_integration.py backend/tests/test_seed_provider.py
git commit -m "feat(skills): подключить SeedSkillProvider в orchestrator memory"
```

---

## Task 6: Регрессия + quality gate

- [ ] **Step 1: Полный прогон backend-тестов**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: всё зелёное, новый `test_seed_provider.py` в покрытии.

- [ ] **Step 2: Lint**

Run: `cd backend && .venv/Scripts/python -m ruff check app/skills/seed_provider.py tests/test_seed_provider.py`
Expected: `All checks passed`

- [ ] **Step 3: Smoke — seed-блок реально попадает в system prompt**

Run:
```bash
cd backend && .venv/Scripts/python -c "from app.orchestrator.memory_integration import build_memory_manager; m=build_memory_manager('_erp25_25_178'); print(m.build_system_prompt()[:400])"
```
Expected: вывод содержит «## Базовые навыки аналитика 1С» + заголовки скиллов (включая ERP-специфичный «Реестр реализаций»).

- [ ] **Step 4: Commit (если были правки по линту)**

```bash
git add -A && git commit -m "chore(skills): lint + smoke seed-pack"
```

---

## Self-Review

**Spec coverage:**
- Always-on seed-ядро → Tasks 1-3 ✓
- Фильтр по типу конфигурации (`applies_to`) → Task 1 (`applies`) + Task 4 (`config_kind`) + Task 2 (фильтр в `system_prompt_block`) ✓
- Инжект в SYSTEM_PROMPT через provider-паттерн → Task 2 + Task 5 ✓
- Immutable / куратор не трогает → seed вне SkillStore (архитектурно), provenance не менялся ✓
- G0-safe (только проверенный контент, неизвестная база → только `*`) → Task 1 `applies(None)`, Task 3 контент из M-K3 ✓
- Тесты → каждый таск ✓

**Placeholder scan:** код полный в каждом шаге, контент 5 скиллов написан целиком, команды с ожидаемым выводом. Заглушек нет.

**Type consistency:** `SeedSkill.id/title/applies_to/tags/body`, `applies(config_kind)`, `load_seed_skills(dir)->list[SeedSkill]`, `SeedSkillProvider(seed_dir, config_kind)`, `config_kind_from_channel_id(str)->str|None`, `build_memory_manager(channel_id)->MemoryManager` — имена согласованы между тасками 1→5.

**Out of scope (зафиксировано):** bundles-слэши `/закрытие-месяца`, авто-майнинг из M-K3 трасс (подход B), детект конфигурации для клиентских UUID-каналов — отдельные follow-up планы.
