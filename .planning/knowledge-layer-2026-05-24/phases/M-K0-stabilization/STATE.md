---
milestone: M-K0
status: in_progress
started_at: "2026-05-25T10:30:00Z"
branch: "feature/m-k0-stabilization"
phases_total: 10
phases_done: 4
findings_total: 28
findings_done: 20
---

# M-K0 Stabilization — STATE

## Активность

| Phase | Subject | Status | Commits |
|-------|---------|--------|---------|
| **M-K0.1** | **Security Wave 0 (8 findings)** | **✅ DONE** | 7 commits |
| **M-K0.2** | **Backend Wave 1 (6 findings)** | **✅ DONE** | 5 commits |
| **M-K0.3** | **Perf Wave 2 (3 findings)** | **✅ DONE** | 3 commits |
| **M-K0.4** | **Prompts Wave 3 (3 findings)** | **✅ DONE** | 2 commits (PROMPT-2 в SEC-3) |
| M-K0.5 | Frontend Wave 4 (3 findings) | pending | — |
| M-K0.6 | Arch Wave 5 — ARCH-2 globals | pending | — |
| M-K0.7 | Docs+DevOps Wave 6 (4 findings) | pending | — |
| M-K0.8 | Coverage push 60%+ | pending | — |
| M-K0.9 | Security re-audit | pending | — |
| M-K0.10 | SUMMARY + handoff | pending | — |

## Текущая задача

**M-K0.5 → FE-1 prefers-reduced-motion** (CRITICAL).
Затем FE-3 контраст --fg-4, FE-4 attachment keys.

## Commits в M-K0

Wave 0 Security (7 commits):
```
c4f7602 SEC-1  SSRF guard для MCP endpoint                       CRITICAL
feda2d4 SEC-2  Electron CSP + sandbox + SEC-5 IPC whitelist      HIGH×2
8811287 SEC-4  SQL validator WITH+CTE bypass + RETURNING         HIGH
d2d68d7 SEC-6  CORS allow_headers wildcard → explicit            HIGH
ecb7e7d SEC-7  admin/reset rate-limit 3/hour                     HIGH
7f06bf9 SEC-12 X-LLM-API-Key deprecation indicators              LOW
f9807e6 SEC-3 + PROMPT-2 prompt injection hardening              HIGH×2
```

Wave 1 Backend Quality (5 commits):
```
<BE-1+2 commit>  BE-1 _pending Future + BE-2 task GC protection  CRITICAL×2
<BE-3 commit>    BE-3 silent failures → explicit error + warn    HIGH
<BE-4 commit>    BE-4 CLARIFY leak GeneratorExit try/finally     HIGH
<BE-5 commit>    BE-5 card_id matching по tool_call_id           HIGH
<BE-6 commit>    BE-6 SQLite batch commit                        HIGH
```

Wave 2 Performance (3 commits):
```
506a193 PERF-1  SQLite connection pool (5 conns + WAL)           CRITICAL
1f8ae78 PERF-2  LLMClient reuse через все итерации loop          CRITICAL
b1a378a PERF-3  React Context cache llm-config + connections     HIGH
```

Wave 3 Prompts (2 commits, +1 bonus в SEC-3):
```
afd26a8 PROMPT-1 Few-shot tool decision tree (19 examples)       CRITICAL
4e89944 PROMPT-3 Memory recall trigger (read first + when save)  CRITICAL
f9807e6 PROMPT-2 уже сделан как бонус в SEC-3                    (CRITICAL)
```

17 атомарных коммитов, 20 findings закрыто (8 SEC + 6 BE + 3 PERF + 3 PROMPT).

## Findings progress

| ID | Severity | Subject | Status |
|----|----------|---------|--------|
| SEC-1 | CRITICAL | SSRF: валидация MCP endpoint | ✅ done |
| SEC-2 | HIGH | Electron CSP + sandbox + webSecurity | ✅ done |
| SEC-3 | HIGH | Prompt injection unicode + history | ✅ done |
| SEC-4 | HIGH | SQL validator WITH + RETURNING | ✅ done |
| SEC-5 | HIGH | shell:open-path IPC whitelist | ✅ done |
| SEC-6 | HIGH | CORS allow_headers wildcard | ✅ done |
| SEC-7 | HIGH | admin/reset rate-limit + CSRF | ✅ done |
| SEC-12 | LOW | X-LLM-API-Key deprecation | ✅ done |
| PROMPT-2 | CRITICAL | Indirect injection tool_results | ✅ done (bonus в SEC-3) |
| BE-1 | CRITICAL | _pending dict race | ✅ done |
| BE-2 | CRITICAL | _run_auto_title task leak | ✅ done |
| BE-3 | HIGH | Silent failures (message_id=unknown) | ✅ done |
| BE-4 | HIGH | CLARIFY leak GeneratorExit | ✅ done |
| BE-5 | HIGH | _TOOL_FOR_CARD_TYPE 2× execute_query | ✅ done |
| BE-6 | HIGH | SQLite batch commit | ✅ done |
| PERF-1 | CRITICAL | SQLite single connection | ✅ done |
| PERF-2 | CRITICAL | LLMClient recreate per iter | ✅ done |
| PERF-3 | HIGH | 2 HTTP roundtrip per send | ✅ done |
| PROMPT-1 | CRITICAL | Few-shot tool decision tree | ✅ done |
| PROMPT-3 | CRITICAL | Memory recall trigger | ✅ done |
| FE-1 | CRITICAL | prefers-reduced-motion | pending ← следующий |
| FE-3 | HIGH | --fg-4 контраст | pending |
| FE-4 | HIGH | attachment keys | pending |
| ARCH-2 | HIGH | globals → contextvars | pending |
| DOC-1 | HIGH | ARCHITECTURE.md ревизия | pending |
| DOC-2 | MEDIUM | STATE.md loop.py цифр | pending |
| DEVOPS-1 | HIGH | EV/OV cert process init | pending |
| DEVOPS-5 | MEDIUM | Auto-update semver.gt | pending |

## Метрики Wave 0

- **Findings закрыто**: 9 (8 SEC + 1 PROMPT bonus) из 28 = **32%**
- **CRITICAL закрыто**: 2 из 9 (SEC-1, PROMPT-2)
- **HIGH закрыто**: 6 из 19
- **Тесты добавлено**: 31 unit (SSRF) + 5 integration (connections) +
  6 (SEC-4 WITH/RETURNING) + 1 (SEC-7 rate-limit) + 2 (SEC-12 deprecation) +
  6 (SEC-3 homoglyph) = **51 новый тест**
- **Backend pytest**: 896 passed (баseline 825 → +71 от sqlparse активации + мои)
- **Регрессии**: 0
- **Pre-existing flaky**: 2 (test_default_model, test_get_empty_NVIDIA_key — не моя зона)

## Что дальше (M-K0.2 Backend Quality)

Wave 1 — 6 findings, ~4 дня:
- BE-1 _pending race (CRITICAL) — самый сложный, asyncio loop affinity
- BE-2 _run_auto_title task leak (CRITICAL)
- BE-3 silent failures
- BE-4 CLARIFY leak GeneratorExit
- BE-5 _TOOL_FOR_CARD_TYPE matching
- BE-6 SQLite batch commit
