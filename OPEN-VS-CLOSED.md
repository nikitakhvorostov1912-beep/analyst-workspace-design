# Open vs Closed — Что под Apache 2.0, что Proprietary

**Status:** Active (M-K1.2 pre-flight, Q6 dual license resolved 2026-05-25)
**Source of truth:** LICENSE (Apache 2.0), LICENSE-EPF, LICENSE-CFE, NOTICE

## TL;DR

| Уровень | Лицензия | Где живёт | Что внутри |
|---|---|---|---|
| **Core** | Apache 2.0 | `backend/`, `frontend/`, `desktop/` | Чат-консоль, оркестратор, knowledge layer, MCP клиенты, UI |
| **EPF** | Proprietary | `epf-src/АналитикLite/` | Внешняя обработка для quick-start (M-K3) |
| **CFE** | Proprietary | `cfe-src/АналитикПлюс/` | Расширение конфигурации полнофункциональное (M-K3) |
| **Rulebook** | Proprietary | `backend/app/knowledge/rulebook/` | Diagnose Engine YAML (M-K3) |
| **Reference Library** | Proprietary | `knowledge-corpora/proprietary/` | 5 typical fingerprints (M-K5) |

## Принципы Open Core

1. **Core должен быть полнофункциональным**, даже без EPF/CFE — пользователь
   получает работающий чат-консоль с MCP подключением «из коробки»
2. **EPF/CFE добавляют 1С-side функциональность** которую невозможно
   реализовать только в backend (capability response, Activity Stream подписки,
   HMAC SSO, BSL Diagnostics через CFE)
3. **API контракт между Core и EPF/CFE — публичный**: спецификация MCP
   `experimental.analyst-1c.features` (ADR-004) задокументирована и
   позволяет третьим лицам реализовать собственный EPF/CFE
4. **Reference Library — premium**: 5 fingerprint'ов типовых конфигураций
   собранных вручную с учётом специфики (УТ/ERP/КА/БГУ/ЗУП) — продаются как
   премиум-сервис, не Open Source

## Detailed boundary

### `backend/` — Apache 2.0

Включает всё содержимое директории, кроме:
- `backend/app/knowledge/rulebook/` — **Proprietary** (Diagnose Engine YAML)
- `backend/app/knowledge/corpora/proprietary/` — **Proprietary** (если когда-то
  появится bundled proprietary corpora — пока нет, всё локально качается)

### `frontend/` — Apache 2.0

Включает всё содержимое директории. Никаких proprietary компонентов.

### `desktop/` — Apache 2.0

Электрон-обёртка, electron-builder config, updater logic, IPC handlers.

**Важно:** бандл (`.exe` installer) при сборке может включать `АналитикLite.epf`
в `resources/` — это **proprietary asset** внутри installer. Installer
распространяется как **single proprietary deliverable** для конечного
пользователя, хотя его части по отдельности — open + proprietary.

### `epf-src/` — Proprietary

Будет создан в M-K3. До этого момента — папка не существует.

Структура (будущее):
```
epf-src/АналитикLite/
├── manifest.json      ← НЕ исходник, отдельно
├── Module.bsl         ← Proprietary
├── Forms/...          ← Proprietary
├── README-EPF.md      ← Apache 2.0 (документация)
└── ...
```

### `cfe-src/` — Proprietary

Будет создан в M-K3 Phase 13b. До этого момента — папка не существует.

Структура (будущее):
```
cfe-src/АналитикПлюс/
├── Configuration.xml  ← Proprietary
├── CommonModules/АП_*.xml  ← Proprietary (Q1 prefix)
├── Subsystems/АналитикПлюс/...  ← Proprietary
└── ...
```

### `knowledge-corpora/` — смешанный

- `knowledge-corpora/public/` — Apache 2.0 (если копируем sfaqer/БСП с
  атрибуцией) или просто символические ссылки на upstream tools/
- `knowledge-corpora/proprietary/` — **Proprietary** (M-K5 Reference Library)

## Что мы НЕ можем делать (виральные лицензии)

- `tools_ui_1c` (GPL-3.0) — опционально интегрируется в EPF через checkbox
  «Включить tools_ui_1c (GPL-3.0)». **Если пользователь включает**, EPF
  становится GPL-3.0 (виральная заразность). Документировано в LICENSE-EPF.

- Никаких иных GPL/AGPL зависимостей в Core, EPF или CFE без явного
  обсуждения и checkbox в installer.

## Что мы НЕ можем брать в Core (но можем использовать как внешние tools)

- `tools_ui_1c` — GPL-3.0. **НЕ копируем в Core/EPF/CFE напрямую**, только
  через опциональный checkbox в installer
- Любая БСП-обработка от 1С, помеченная как «закрытая» (типовая поставка УТ)
- Лицензированные платные библиотеки (Apdex, KIP, etc.)

## Что мы МОЖЕМ брать в Core с атрибуцией

- `tools/v8std/` (sfaqer MIT, atrib NOTICE)
- `tools/ssl_3_*/src/` (БСП CC-BY-4.0, atrib NOTICE)
- `tools/OnesTemplates/` (comol MIT, atrib NOTICE)
- `tools/bsl-language-server-*.jar` (MIT, subprocess use)
- sqlite-vec, FastEmbed, BGE-M3 (Apache 2.0)

## API контракт (публичный, MCP-native)

Третье лицо может реализовать собственный EPF/CFE если придерживается:

1. MCP `initialize` response с `experimental.analyst-1c.features` (ADR-004)
2. 23 capabilities namespaced (`mcp.*`, `tools_ui.*`, `cfe.*`) — см.
   `backend/app/types/capabilities.py`
3. HTTP/SSE endpoints (`/initialize`, `/tools/list`, `/tools/call`, etc.)
4. HMAC SSO протокол (если используется CFE-only фича `cfe.hmac_sso`) —
   спецификация в M-K3 Phase 13b.4.1

Это сделано **намеренно** — open contract без vendor lock-in, но фактическая
реализация капитальных компонентов (наш EPF/CFE) — proprietary.

## История изменений

| Дата | Изменение | Phase |
|---|---|---|
| 2026-05-25 | Initial creation. MIT → Apache 2.0 для Core. LICENSE-EPF + LICENSE-CFE + NOTICE созданы. | M-K1.2 |
| TBD M-K3 | Создание `epf-src/` и `cfe-src/` папок с фактическим Proprietary контентом | M-K3 Phase 13a/13b |
| TBD M-K5 | Создание `knowledge-corpora/proprietary/` с Reference Library | M-K5 |
