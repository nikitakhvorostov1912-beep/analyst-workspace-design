# 09 — Current State (что уже готово в workspace)

> Информация для агента/человека работающего над M6: какие инструменты, MCP, данные уже доступны локально и не требуют установки. Это **значительно ускоряет старт фаз**.

## Workspace расположение

`C:/CLOUDE_PR/` — корневой workspace со всеми инструментами.

## ✅ Установлено и работает

### MCP-серверы (готовы к использованию в Phase 12)

| MCP | Endpoint / Команда | Status | Используется в Phase |
|-----|---------------------|--------|----------------------|
| **MCP Toolkit** | `http://localhost:6010/mcp` (EPF v1.7.0) | ⏸ EPF не запущен в фоне | 12, 13a, 13b |
| **1c-buddy** | `http://localhost:6002/mcp` (Python venv) | ✅ Запущен фоновым процессом | 12 |
| **mcp-bsl-context** | `stdio` через `tools/mcp-bsl-context-0.3.2.jar` | ✅ Готов | 12 |
| **METR** | `stdio` через `tools/mcp-onec-test-runner.jar` | ✅ Готов | 12 |
| **EDT-MCP** | `http://localhost:8770/mcp` (плагин EDT) | ⏸ EDT не запущен | 12 (опционально) |

### 1c-buddy запущенный сервер

- Процесс: Python `tools/1c-buddy/.venv/Scripts/python.exe -m app`
- Порт: 6002 LISTEN
- Токен: **`ONEC_AI_TOKEN`** в **User environment Windows** (валидный, проверено через MCP initialize)
- 8 tools: `ask_1c_ai`, `explain_1c_syntax`, `check_1c_code`, `modify_1c_code`, `search_1c_documentation`, `search_its`, `fetch_its`, `diff_1c_documentation_versions`
- Логи: `tools/1c-buddy/1c-buddy.log`
- Старт-скрипт: `tools/1c-buddy/start-1c-buddy.bat`

### Источники для RAG (готовы к индексации в Phase 14)

| Источник | Путь | Размер | Готовность к индексации |
|----------|------|--------|--------------------------|
| **v8std** | `tools/v8std/` (git clone zeegin/v8std `81d48f1`) | 12.7 MB | ✅ — 317 .md файлов в `tools/v8std/content/` |
| **БСП SSL 3.1** | `tools/ssl_3_1/` (git clone, 3.1.12.205) | ~50 MB | ✅ — исходники для парсера ssl_api |
| **БСП SSL 3.2** | `tools/ssl_3_2/` (git clone, 3.2.1.412) | ~60 MB | ✅ — для будущей миграции на 8.5 |
| **.hbk файл платформы** | `C:/Program Files/1cv8/8.3.27.1989/1ceBsl.hbk` | ~30 MB | ⚠️ — нужен парсер (см. R2 в risks) |

### BSL Language Server (готов для Phase 15)

- **Jar:** `tools/bsl-language-server-0.30.0-rc.2-exec.jar` (113.7 MB)
- **JDK 21:** `tools/jdk-21/` (требуется для запуска BSL LS 0.30+)
- **Тестовая команда:** `tools/jdk-21/bin/java.exe -jar tools/bsl-language-server-0.30.0-rc.2-exec.jar --help`

### MetaVision (готов к использованию + форку для Phase 16)

- **Исходники:** `tools/MetaVision/` (git clone AndreyHhh/MetaVision)
- **Собранный jar:** `tools/MetaVision/build/libs/MetaVisionFor1C-1.0.jar` (28.6 MB, fat jar)
- **Distribution:** `tools/MetaVision/build/distributions/MetaVisionFor1C-1.0.zip`
- **JDK 17:** `tools/jdk-17/` (для сборки и запуска)
- **Старт-скрипт:** `tools/MetaVision/start-metavision.bat` (запускает через gradlew)
- **Проблема:** только GUI режим — для CLI нужен fork (Phase 16.1)

### Другие инструменты

- **JDK 17.0.19 Microsoft:** `tools/jdk-17/`
- **JDK 21.0.11 Microsoft:** `tools/jdk-21/`
- **Connector v2.6.1:** `tools/Connector/` (git clone vbondarevsky/Connector, MIT)
- **tools_ui_1c v25.2.1:** `tools/tools_ui_1c/` (git clone cpr1c/tools_ui_1c, GPL-3.0, 1000⭐)
- **MCP Toolkit EPF v1.7.0:** `tools/MCP_Toolkit_v1.7.0.epf`
- **YAxUnit 25.12:** `tools/yaxunit/YAxUnit-25.12.cfe`
- **Vanessa Automation 1.2.043.19:** `tools/vanessa-automation/vanessa-automation-single.epf`

## ⚙️ Что нужно проверить перед стартом Phase 12

```bash
# 1. Проверить что 1c-buddy запущен
curl http://localhost:6002/health

# 2. Если не запущен — запустить
cd C:/CLOUDE_PR/tools/1c-buddy
.\start-1c-buddy.bat

# 3. Проверить токен в env
echo $env:ONEC_AI_TOKEN  # должен быть установлен

# 4. Проверить JDK 21 для BSL LS
C:/CLOUDE_PR/tools/jdk-21/bin/java -version
# Должно вывести: openjdk version "21.0.11"

# 5. Проверить JDK 17 для MetaVision
C:/CLOUDE_PR/tools/jdk-17/bin/java -version
# Должно вывести: openjdk version "17.0.19"

# 6. Проверить что Python venv для 1c-buddy на месте
C:/CLOUDE_PR/tools/1c-buddy/.venv/Scripts/python.exe --version
# Должно вывести: Python 3.11.9
```

## 📁 Файлы памяти

В `~/.claude/projects/C--CLOUDE-PR/memory/` уже есть **3 справочных документа** с полным ресерчем 1С-экосистемы:

1. `1c-ecosystem-deep-research-2026-05-24.md` (~30 KB) — 11 направлений (MCP, dev/analyst, skills, RAG, IDE, DevOps, интеграции, perf, OneScript, сообщества)
2. `1c-ecosystem-extended-research-2026-05-24.md` (~35 KB) — 6 смежных доменов (Frontend, AI, Облака, Perf/Sec, Регуляторика, SAP опыт)
3. `1c-business-processes-data-structures-2026-05-24.md` (~40 KB) — структуры данных типовых + бизнес-процессы + ИТС + reverse engineering

Эти файлы автоматически подтягиваются в новые Claude Code сессии в проекте Cloude_PR.

**При работе в `analyst-workspace-design`** они не подтягиваются автоматически (wrong-project guard), но можно ссылаться:
- "См. справку: `C:/Users/Khvorostov/.claude/projects/C--CLOUDE-PR/memory/1c-business-processes-data-structures-2026-05-24.md`"

## 🎯 Master document для другой сессии

`C:/CLOUDE_PR/Стек_1С_AI_2026-05-24.md` (144 KB, 2452 строки) — единый документ со всем стеком + ресерчами + структурами данных + бизнес-процессами + регуляторикой 2026. Можно скинуть в любую сессию для контекста.

## 🚧 Не установлено / нужно сделать в фазах M6

- **Custom MCP сервер от 1С:Аналитик** (наш) — будет сделан в Phase 13a (EPF) / 13b (CFE)
- **PowerShell installer для CFE** — Phase 13b.5
- **CFE расширение АналитикПлюс** — Phase 13b
- **MetaVision CLI режим (fork)** — Phase 16.1
- **.hbk парсер** — Phase 14.4 (под риском)
- **sqlite-vec в backend** — Phase 14.1
- **Bundled JRE 17 для Electron installer** — Phase 18.1

## 🔗 Полезные ссылки внутри workspace

- **Глобальный CLAUDE.md:** `C:/Users/Khvorostov/.claude/CLAUDE.md`
- **Проектный CLAUDE.md:** `C:/CLOUDE_PR/CLAUDE.md` (workspace level)
- **Правила 1С:** `C:/CLOUDE_PR/.claude/rules/1c/` (31 файл, comol/ai_rules_1c adaptation)
- **Knowledge router:** `C:/CLOUDE_PR/.claude/rules/knowledge-router.md`
- **Проектный CLAUDE.md analyst-workspace-design:** `C:/CLOUDE_PR/projects/analyst-workspace-design/CLAUDE.md`
- **Проектные правила analyst-workspace-design:** `C:/CLOUDE_PR/projects/analyst-workspace-design/.claude/rules/`

## ⚠️ Wrong-project guard

В `analyst-workspace-design/.claude/CLAUDE.md` есть строгое правило:

> **Работаем ТОЛЬКО в `C:\CLOUDE_PR\projects\analyst-workspace-design\`**.
> НЕ ЛЕЗТЬ в `C:\CLOUDE_PR\projects\analyst-tools-1c\` (заброшенный v0).
> Если получил запрос на работу с другим проектом — переспросить пользователя.

**Для другой сессии:** при работе над M6 — пути относительно `analyst-workspace-design/`. Артефакты M6 кладём в:
- `.planning/phases/` — phase plans
- `.planning/milestones/` — milestone overview
- `backend/app/services/` — новые сервисы
- `frontend/components/` — новые компоненты
- `cfe-src/АналитикПлюс/` — CFE структура
- `epf-src/АналитикLite/` — EPF структура
- `installers/` — PowerShell скрипты

## ✅ Готовность к старту Phase 12

Все компоненты для Phase 12 (Multi-MCP Orchestration + Capability Discovery) готовы:
- 4-5 MCP серверов работают или готовы запускаться
- Все нужные runtimes (JDK 17, JDK 21, Python 3.11.9, Node 22.14)
- Документация архитектурного решения собрана
- Code skeletons готовы (см. [07-CODE-SKELETONS.md](./07-CODE-SKELETONS.md))

**Можно начинать Phase 12 task 12.1 (модель MCPConnection) сразу после ответов на open questions.**
