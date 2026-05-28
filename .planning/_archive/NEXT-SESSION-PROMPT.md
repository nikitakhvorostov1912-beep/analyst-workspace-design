# Промт для следующей сессии — Phase v2.0 CRITICAL Preventive

Скопируй текст ниже в новую сессию Claude Code (в проекте
`analyst-workspace-design`). Все ссылки на файлы — относительные от
корня проекта.

---

## ВСТАВЛЯЙ ОТСЮДА ↓

Привет. Продолжаем M-K2.5 — выполняем **Phase v2.0 CRITICAL Preventive**
по уже подготовленному плану. Контекст в одном абзаце:

В предыдущих сессиях я закрыл M-K2.5 (8 фаз) с 4 типовыми
конфигурациями в pilot.db (БП 3.0 / КА 2.5 / УТ 11.5 / ERP 2.5):
2.2M узлов графа, 1.7M рёбер, 63 197 mock-карточек. После глубокого
research (deep-researcher, 60+ источников) выяснилось — карточки
не готовы к production из-за 9 критичных рисков. План v2.0 закрывает
их 7 атомарными шагами + smoke + closing. **Делаем именно его, в
указанном порядке.**

### Действия в этой сессии

1. **Прочитай ОБЯЗАТЕЛЬНО, прежде чем писать код:**
   - `.planning/knowledge-layer-2026-05-24/phases/M-K2.5/CARDS-V2-PLAN.md`
     раздел "Phase v2.0 — CRITICAL Preventive (полный вариант B)" —
     детальная схема 7 шагов с файлами, acceptance criteria, commit
     сообщениями
   - `.planning/knowledge-layer-2026-05-24/phases/M-K2.5/CARDS-V2-RESEARCH.md`
     — обоснование почему именно эти 9 рисков (60+ источников,
     mapping гэпов на решения)
   - `.planning/knowledge-layer-2026-05-24/phases/M-K2.5/SUMMARY.md` —
     состояние M-K2.5 на момент закрытия
   - `backend/app/knowledge/typical/card_models.py` — текущая схема
     карточки (frozen dataclass)
   - `backend/app/knowledge/typical/card_storage.py` — CRUD для карточек
   - `backend/app/knowledge/typical/tool.py` — 6 LLM-tools
   - `backend/app/storage/migrations.py` — где добавлять v19/v20/v21

2. **Создай новую ветку** `feature/m-k2.5.9-cards-v2-preventive` и
   делай атомарные коммиты по каждому шагу (см. план).

3. **Выполни 7 шагов СТРОГО ПО ПОРЯДКУ** (если шаг N падает на
   тестах — STOP, не идём на N+1, разбираемся):

   - **v2.0-step-1** (40 мин): П1 Pydantic BaseModel(frozen=True) вместо
     `@dataclass(frozen=True)` для TypicalObjectCard / CardAttribute /
     CardMovement. Сохраняем тот же публичный API (`to_dict`,
     `to_payload_json`, `from_payload_json`, property `embedding_text`).
     Backward compat: `model_validate(dict)` с `extra='ignore'`.
     Commit: `refactor(M-K2.5.9.1): TypicalObjectCard → Pydantic BaseModel(frozen=True)`

   - **v2.0-step-2** (30 мин): П6 Mock isolation — Migration v19 +
     колонка `is_mock` + UPDATE 63 197 mock-карточек на 1. Tool возвращает
     is_mock в payload. UI бейдж «Mock data — не верифицировано экспертом».
     Commit: `feat(M-K2.5.9.2): is_mock flag + UI warning для mock-карточек`

   - **v2.0-step-3** (45 мин): Гэп 11 Hard limits через Pydantic
     `Field(max_length=...)` для каждого list/str поля карточки.
     Промпт-шаблон тоже обновить с явными лимитами.
     Commit: `feat(M-K2.5.9.3): hard limits через Pydantic Field max_length`

   - **v2.0-step-4** (45 мин): П3 Closed vocabulary —
     `Literal["приход", "расход", ...]` для `CardMovement.direction`,
     prompt-template с явным списком допустимых values + правил
     формата register name.
     Commit: `feat(M-K2.5.9.4): closed vocabulary для movements direction + register format`

   - **v2.0-step-5** (2 часа): Гэп 7 Graph validation —
     новый `card_validator.py` с `validate_card_against_graph()`
     (GraphEval-стиль, граф = ground truth). Migration v20 с полями
     `validation_status` / `validation_issues` / `validated_at`.
     `tool._handle_explain` возвращает validation в payload.
     15 unit-тестов.
     Commit: `feat(M-K2.5.9.5): card validator против реального графа (GraphEval)`

   - **v2.0-step-6** (40 мин): П7 Embedding model versioning —
     поле `embedding_model_version` + Migration v21 + новый script
     `scripts/typical_cards_reembed.py` (требует `--confirm`).
     Commit: `feat(M-K2.5.9.6): embedding model versioning + explicit reembed`

   - **v2.0-step-7** (1 час): П8 Cold start fallback —
     обновить system prompt в `orchestrator/loop.py` (раздел про
     typical tools): при `card=null` или `total=0` НЕ галлюцинировать,
     явно сообщать «информации нет». `tool._handle_explain` для
     несуществующего возвращает структурированный `card_status="not_in_graph"`
     с подсказкой top-5 похожих имён. Frontend компонент not_found state.
     5 smoke-тестов на cold start.
     Commit: `feat(M-K2.5.9.7): cold start fallback без LLM-галлюцинаций`

   - **v2.0-step-8** (1 час): Smoke + регресс + closing —
     прогнать `python -m scripts.typical_smoke_questions` (должно
     стать 75+ из 75+), расширить smoke на 20 новых проверок,
     прогнать typical/* регресс (347+ должны быть зелёные), обновить
     STATE.md + SUMMARY.md, FF merge ветки в main + push.
     Commit: `closing(M-K2.5.9): Phase v2.0 critical preventive complete`

4. **Acceptance criteria** в финале (все обязательны):
   - [ ] Все 7 шагов закоммичены атомарно с указанными сообщениями
   - [ ] Mock карточки помечены `is_mock=1` и фильтруются в retrieval
   - [ ] `validate_card_against_graph` отлавливает фейковые регистры
   - [ ] Pydantic field validators отклоняют overlimit
   - [ ] TypicalObjectCard — BaseModel(frozen=True)
   - [ ] Closed vocabulary применён в prompt + Literal types в schema
   - [ ] Embedding model versioning в схеме (migration v21)
   - [ ] Cold start fallback без галлюцинаций (smoke проверка)
   - [ ] Все 347+ typical/* tests зелёные
   - [ ] Smoke 75+ проверок зелёные (старые 55 + 20+ новых)
   - [ ] FF merge в main + push

### Окружение

- Корень проекта: `C:\CLOUDE_PR\projects\analyst-workspace-design`
- Python: 3.11, venv в `backend/.venv` (если есть)
- Bash из MSYS: cwd часто теряется в background tasks → всегда префиксуй
  `cd /c/CLOUDE_PR/projects/analyst-workspace-design/backend && ...`
- БД: `C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db` —
  абсолютный путь обязательно (есть вторая пустая БД в `backend/data/`,
  не путайся)
- Существующая БД содержит: 4 типовые в `typical_configurations`,
  63 197 карточек в `typical_object_cards` (status=generated,
  llm_model='mock-generator-v1'), 2.2M узлов в `graph_nodes`,
  1.7M рёбер в `graph_edges`. Не удаляй ничего без подтверждения.

### Что важно держать в голове

- **Брутальная честность**: если тесты падают — не маскируй, разбирайся
- **Atomic commits**: 1 шаг = 1 commit, не сваливай
- **Backward compat**: 63k существующих карточек должны корректно
  читаться после миграций (Pydantic `extra='ignore'`)
- **Кодировка**: Windows cp1251 в консоли искажает русский. Всегда
  префиксуй `set PYTHONIOENCODING=utf-8 && python -X utf8 ...` для
  скриптов с русским output
- **Co-Authored-By**: в commit footers `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- **Не пушь в main без FF merge** — сначала ветка `feature/m-k2.5.9-cards-v2-preventive`,
  атомарные коммиты, в финале `git checkout main && git merge --ff-only feature/...`

### Если что-то непонятно

- Карта плана v2 в целом — `.planning/knowledge-layer-2026-05-24/phases/M-K2.5/CARDS-V2-PLAN.md`
  раздел 7 (зависимости фаз). Phase v2.0 — наша цель этой сессии.
  Остальные фазы (v2.A-H) — потом, не трогай в этой сессии.
- Уже закрытое M-K2.5 (commit `9272383` на main) — не переделывай.
- Если упёрся в decision-point — спроси меня, не угадывай.

Поехали — начни с прочтения CARDS-V2-PLAN.md раздел Phase v2.0.

## ВСТАВЛЯЙ ДО СЮДА ↑

---

## Что не нужно в новой сессии (явно)

- НЕ начинай M-K3
- НЕ трогай real LLM adapter (оставь mock, только пометим is_mock)
- НЕ генери карточки заново (только метаданные обновляем)
- НЕ парсь дополнительные типовые (ЗУП/УСО/Документооборот) — это
  отдельная задача после v2.0
- НЕ декомпозируй loop.py (это M-K3.0)

## Готовность

Если новая сессия закроет v2.0 (~7-8 часов) и пройдёт acceptance —
можно идти в **M-K3.0 decompose loop.py** или подключение **real LLM
adapter** (тогда обязательно перегенерировать карточки и снять
is_mock=1 → 0 для content-карточек).
