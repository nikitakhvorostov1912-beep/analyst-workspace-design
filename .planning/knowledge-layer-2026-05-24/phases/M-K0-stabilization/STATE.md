---
milestone: M-K0
status: in_progress
started_at: "2026-05-25T10:30:00Z"
branch: "feature/m-k0-stabilization"
phases_total: 10
phases_done: 0
findings_total: 28
findings_done: 0
---

# M-K0 Stabilization — STATE

## Активность

| Phase | Subject | Status | Started | Commit |
|-------|---------|--------|---------|--------|
| M-K0.1 | Security Wave 0 (8 findings) | in_progress | 2026-05-25 | — |
| M-K0.2 | Backend Wave 1 (6 findings) | pending | — | — |
| M-K0.3 | Perf Wave 2 (3 findings) | pending | — | — |
| M-K0.4 | Prompts Wave 3 (3 findings) | pending | — | — |
| M-K0.5 | Frontend Wave 4 (3 findings) | pending | — | — |
| M-K0.6 | Arch Wave 5 — ARCH-2 globals | pending | — | — |
| M-K0.7 | Docs+DevOps Wave 6 (4 findings) | pending | — | — |
| M-K0.8 | Coverage push 60%+ | pending | — | — |
| M-K0.9 | Security re-audit | pending | — | — |
| M-K0.10 | SUMMARY + handoff | pending | — | — |

## Текущая задача

**M-K0.1 → SEC-1 SSRF guard** (первая из 8 security findings)

## Commits в M-K0

(нет пока)

## Findings progress

| ID | Severity | Subject | Status |
|----|----------|---------|--------|
| SEC-1 | CRITICAL | SSRF: валидация MCP endpoint | in_progress |
| SEC-2 | HIGH | Electron CSP + sandbox | pending |
| SEC-3 | HIGH | Prompt injection unicode + history | pending |
| SEC-4 | HIGH | SQL validator WITH + RETURNING | pending |
| SEC-5 | HIGH | shell:open-path IPC whitelist | pending |
| SEC-6 | HIGH | CORS allow_headers wildcard | pending |
| SEC-7 | HIGH | admin/reset rate-limit + CSRF | pending |
| SEC-12 | LOW | X-LLM-API-Key deprecation | pending |
| BE-1 | CRITICAL | _pending dict race | pending |
| BE-2 | CRITICAL | _run_auto_title task leak | pending |
| BE-3 | HIGH | Silent failures (message_id=unknown) | pending |
| BE-4 | HIGH | CLARIFY leak GeneratorExit | pending |
| BE-5 | HIGH | _TOOL_FOR_CARD_TYPE 2× execute_query | pending |
| BE-6 | HIGH | SQLite batch commit | pending |
| PERF-1 | CRITICAL | SQLite single connection | pending |
| PERF-2 | CRITICAL | LLMClient recreate per iter | pending |
| PERF-3 | HIGH | 2 HTTP roundtrip per send | pending |
| PROMPT-1 | CRITICAL | Few-shot tool decision tree | pending |
| PROMPT-2 | CRITICAL | Indirect injection tool_results | pending |
| PROMPT-3 | CRITICAL | Memory recall trigger | pending |
| FE-1 | CRITICAL | prefers-reduced-motion | pending |
| FE-3 | HIGH | --fg-4 контраст | pending |
| FE-4 | HIGH | attachment keys | pending |
| ARCH-2 | HIGH | globals → contextvars | pending |
| DOC-1 | HIGH | ARCHITECTURE.md ревизия | pending |
| DOC-2 | MEDIUM | STATE.md loop.py цифр | pending |
| DEVOPS-1 | HIGH | EV/OV cert process init | pending |
| DEVOPS-5 | MEDIUM | Auto-update semver.gt | pending |
