# RISKS — Knowledge Layer 1С Аналитик

**Live document.** Обновляется по итогам каждого milestone или при обнаружении
новых рисков. Initial population — из M6 06-RISKS-AND-MITIGATION.md + M-K0
наблюдения.

**Status legend:** 🔴 HIGH (блокирует milestone) · 🟡 MEDIUM (увеличивает срок ≥ 30%)
· 🟢 LOW (известный, mitigated)

## Активные риски

### R-01: 🔴 1С:Напарник станет платным 01.10.2026

**Контекст:** Q-NEW resolved (Напарник primary, наш RAG fallback). Сейчас бесплатно.

**Impact:** Если ROI отрицательный, придётся срочно переключаться на наш RAG —
качество retrieval может просесть в конце M-K4 / начале M-K5.

**Mitigation:**
- Fallback corpus (sfaqer/v8std) собирается параллельно в M-K2 — готов к 01.09
- M-K4 OPS-2 Telemetry собирает metric «retrieval source used, hit rate, click
  rate» для обоих путей за 2-3 месяца до deadline
- Pricing API Напарника мониторится ежемесячно начиная с июля 2026

**Trigger:** анонс ценовой политики Напарника или его недоступность ≥ 24h
подряд → переключение в M-K5

---

### R-02: 🔴 MetaVision CLI fork может не получиться за 3 дня (Phase 16.0 Spike)

**Контекст:** Q4 resolved C (Spike 3 days). Если GUI-only архитектура жёстко
завязана на Swing — отделить CLI рискованно.

**Impact:** Если spike fail — Phase 16 сокращается с 20-28 дней до 8-10 дней
(только наш граф primary, кнопка «Открыть в MetaVision desktop»). Это **меньший
риск** — наш граф (TreeSitter+SQLite+React Flow) делается всегда для L4.

**Mitigation:**
- Spike имеет жёсткий 3-day timebox с decision gate
- Наш граф (L2) делается **до** Spike — Phase 16 не блокирует M-K3
- Готов план fallback (8-10 дней visualization-only) в M-K4-PLAN.md

**Trigger:** на день 3 spike'а — оценка PoC. Если CLI не выдаёт JSON → переход
на fallback план без обсуждения

---

### R-03: 🟡 .hbk parser платформы — закрытый формат 1С

**Контекст:** M-K2.4 spike (3 дня). v8327doc/v8std + БСП API уже покрывают
~80% типовых вопросов «как работает X». .hbk даёт remaining 20% (платформенный
help, скрытый от документации).

**Impact:** Если parser не получится — теряем источник для L5-3 «Спроси у
платформы». Но fallback на v8std покрывает основной use case.

**Mitigation:**
- Acceptance criterion для M-K2.4: «если за 3 дня не получится — fallback на
  v8std + БСП без .hbk, push .hbk в backlog M-K4»
- Альтернатива: bsl-language-server умеет читать .hbk → можно использовать как
  proxy (через subprocess `bsl-ls --hbk-extract`)
- Cost estimate $250 для embeddings .hbk заложен в budget M-K2 — если не
  используется, экономия

**Trigger:** на день 3 spike'а — go/no-go decision

---

### R-04: 🟡 БГУ/ЗУП могут иметь конфликты capabilities с УТ/ERP

**Контекст:** Q2 resolved D (УТ + ERP + КА + БГУ + ЗУП).

**Impact:** Capability `cfe.method_overrides` для документов ЗП ≠ для документов
УТ → могут быть смешанные результаты в smoke tests. Срок M-K3 +2 нед уже учтён.

**Mitigation:**
- Phase 13b.0 (новая, +0.5 дня) — feature-detection per configuration через
  `Метаданные.ВерсияСтандартныхПодсистем`
- Опциональные capabilities активируются если БСП >= 3.1.10 (общий minimum)
- Smoke tests разделены на 5 наборов — один per configuration type

**Trigger:** smoke fail на 2+ из 5 конфигураций → пересмотр scope (откатить
БГУ/ЗУП до M-K5)

---

### R-05: 🟡 BSL LS jar (113 MB) + JRE 17 (~80 MB) раздуют installer

**Контекст:** M-K3 + M6 Phase 15 (BSL LS streaming).

**Impact:** Текущий Electron installer 105.9 MB. После +193 MB → ~300 MB.
Это превышает M-K5 target «v2.0 installer ≤ 250 MB».

**Mitigation:**
- Bundled JRE 17 — использовать `jlink --add-modules java.base,...` для
  minimal JRE (~30-40 MB вместо 80)
- BSL LS jar — proguard-shrink для убирания неиспользуемых модулей (~50 MB
  вместо 113)
- Альтернатива: download-on-demand (как BGE-M3 модель в ADR-003) — BSL LS
  скачивается при первом use, не в installer

**Trigger:** installer ≥ 200 MB после Phase 15 → переход на download-on-demand

---

### R-06: 🟡 1c-buddy MCP отвалился (наблюдение M-K0)

**Контекст:** В начале M-K0 session — system reminder показал
«mcp__1c-buddy__* disconnected». Healthcheck + auto-restart нужен для prod.

**Impact:** Если canal connection отваливается во время user session —
runtime fallback должен сработать без потери сообщения

**Mitigation:**
- G1 (M-K1.1): seed 1c-buddy + healthcheck endpoint в MCP Orchestrator
- Circuit breaker pattern в `mcp_pool.py` (наши изменения PERF-1 + новая логика)
- Frontend: degraded mode badge «работаю на резервных стандартах» если primary
  отвалился

**Trigger:** healthcheck fail ≥ 30s → переход в fallback mode

---

### R-07: 🟢 SQL `\w` boundary edge case для русских keywords

**Контекст:** M-K0.9 re-audit MEDIUM, confidence 55 (theoretical).

**Impact:** Query типа `SELECT УДАЛИТЬ_ОК` теоретически может обойти fallback
regex scan. Но AST flatten() pass первым корректно классифицирует.

**Mitigation:** AST first, regex fallback — порядок корректен. Confidence 55
означает что не воспроизведён реальный exploit.

**Trigger:** SQL bypass обнаружен в smoke → срочный fix (regex с unicode
character class)

---

### R-08: 🟢 slowapi rate-limit на 127.0.0.1 в desktop (известно by design)

**Контекст:** M-K0.9 re-audit WARN, M-K5 commerce blocker.

**Impact:** Для single-user desktop OK. Для SaaS deployment все users делят
один rate-limit bucket — нужен ProxyFix middleware.

**Mitigation:** перенос в M-K5 milestone (commerce launch), вместе с
auth/multi-tenancy

**Trigger:** SaaS deployment начат → срочно ProxyFix + per-user key

---

### R-09: 🟢 DNS rebinding в SSRF (by design)

**Контекст:** M-K0.9 re-audit WARN. Python `socket.getaddrinfo` без cache,
OS resolver может cache.

**Impact:** Attacker с DNS контролем + TTL=0 теоретически может пробить guard.
Атак не наблюдалось.

**Mitigation:** документировано в `mcp_endpoint_validator.py` docstring.
Закрывается custom HTTP client с per-connection validation — out of scope.

**Trigger:** реальный exploit → custom HTTP client с DNS pinning

---

### R-10: 🟢 Backward compat `app.state.db = primary` (PERF-1)

**Контекст:** Pool создан, но 10+ direct-access call sites не мигрированы.

**Impact:** Race condition теоретически возможна если route через app.state.db
выполняется concurrent с pool.acquire(). Не наблюдалось.

**Mitigation:** plan миграции 10 sites в M-K1.6 (одновременно с DDL v11).
Атомарно per-route.

**Trigger:** наблюдение race condition в логах → срочная миграция

---

## Закрытые риски (для истории)

| ID | Subject | Closed | Phase | Note |
|---|---|---|---|---|
| (M-K0 R-S1) | SSRF в MCP endpoint | 2026-05-25 | M-K0.1 | SEC-1 |
| (M-K0 R-S2) | Prompt injection unicode | 2026-05-25 | M-K0.1 | SEC-3 (+M-K0.9 zero-width fix) |
| (M-K0 R-S3) | SQL bypass через WITH/CTE/RETURNING | 2026-05-25 | M-K0.1 | SEC-4 |
| (M-K0 R-S4) | SQLite single connection bottleneck | 2026-05-25 | M-K0.3 | PERF-1 |
| (M-K0 R-S5) | LLMClient recreate per iter | 2026-05-25 | M-K0.3 | PERF-2 |
| (M-K0 R-S6) | Log injection через X-Request-Id | 2026-05-25 | M-K0.9 | SEC-LOGINJ |

## Workflow

1. **Новый риск замечен** → добавить в активные с initial mitigation
2. **Trigger сработал** → следовать mitigation, поднять severity если не работает
3. **Risk closed** → переместить в «Закрытые» с reference на commit/phase
4. **Quarterly review** — пересмотр всех активных, удаление устаревших
