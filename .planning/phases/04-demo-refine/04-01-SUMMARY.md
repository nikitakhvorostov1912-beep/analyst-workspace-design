---
phase: "04-demo-refine"
plan: "01"
subsystem: anonymization
tags: [anon, security, frontend, backend, mcp]
dependency_graph:
  requires:
    - "03-04-SUMMARY.md"  # card_states table, load-more pattern
  provides:
    - anonymization-toggle
    - deanonymize-endpoint
    - anon-token-visual-highlight
    - card-reveal-button
  affects:
    - frontend/components/cards/
    - frontend/lib/
    - backend/app/routes/log_cards.py
    - backend/app/orchestrator/loop.py
    - backend/app/clients/mcp.py
    - backend/app/storage/migrations.py
tech_stack:
  added:
    - "React useMemo/useState for per-card reveal state"
    - "CustomEvent anon-toggle for localStorage sync across hooks"
    - "Tailwind amber-500/emerald-500 tokens for anon highlight"
  patterns:
    - "Strict Pydantic validation for anon tokens (regex ^\\[[A-Z]+-\\d+\\]$)"
    - "Recursive JSON traversal for token extraction (cards.py + anon-tokens.ts)"
    - "Cache-Control: no-store for deanonymize response (T-04-07)"
    - "Ownership check: session_id + message_id for card access (T-04-08)"
key_files:
  created:
    - "frontend/lib/anon-tokens.ts"
    - "frontend/lib/anon-tokens.test.ts"
    - "frontend/components/shell/AnonymizationToggle.tsx"
    - "frontend/components/shell/__tests__/AnonymizationToggle.test.tsx"
    - "frontend/components/cards/__tests__/TableCard.anon.test.tsx"
    - "backend/tests/test_anonymization.py"
    - "backend/tests/test_deanonymize_route.py"
  modified:
    - "backend/app/clients/mcp.py"
    - "backend/app/orchestrator/loop.py"
    - "backend/app/orchestrator/persistence.py"
    - "backend/app/orchestrator/cards.py"
    - "backend/app/routes/log_cards.py"
    - "backend/app/routes/chat.py"
    - "backend/app/storage/migrations.py"
    - "backend/app/models.py"
    - "frontend/components/shell/Header.tsx"
    - "frontend/components/chat/Markdown.tsx"
    - "frontend/components/chat/useChatStream.ts"
    - "frontend/components/cards/TableCard.tsx"
    - "frontend/components/cards/ObjectCard.tsx"
    - "frontend/components/cards/LogCard.tsx"
    - "frontend/components/cards/CardRenderer.tsx"
    - "frontend/lib/api.ts"
    - "frontend/lib/types.ts"
    - "frontend/lib/storage.ts"
decisions:
  - "Per-call anon forwarding via MCPClient headers (not per-session middleware)"
  - "Real values stored only in React state (revealedMap), never in DB or localStorage"
  - "Fallback MCP response parsers: mapping/map/replacements keys"
  - "card_id generated for TableCard and ObjectCard (not just LogCard)"
  - "extractAnonTokens runs in loop.py (not cards.py) to minimize coupling"
metrics:
  duration: "~2h"
  completed_date: "2026-05-15"
  backend_tests: 23
  frontend_tests: 25
  total_tests: 48
  files_created: 7
  files_modified: 18
---

# Phase 04 Plan 01: Anonymization End-to-End Summary

**One-liner:** JWT-free anon toggle with amber token highlight and per-card reveal via MCP submit_for_deanonymization — real values never persisted.

## What Was Done

### T-04-01-1: Backend — anon forwarding + deanonymize endpoint + migration v4

1. **MCPClient** (`clients/mcp.py`): already accepted `headers: dict | None` via `_extra_headers`. Verified headers flow into every `_post()` call correctly.

2. **run_chat_loop** (`orchestrator/loop.py`): added `x_anon_enabled: bool = False` parameter. Creates MCPClient with `{"X-Anon-Enabled": "true"}` headers when enabled. Also saves card_state for Table/Object cards (not just Log) when anon_enabled=True.

3. **POST /chat** (`routes/chat.py`): added `x_anon_enabled: str | None = Header(default=None, alias="X-Anon-Enabled")` parameter, parses "true" → bool, forwards to run_chat_loop.

4. **POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize** (`routes/log_cards.py`):
   - Ownership check (session_id + message_id)
   - Creates MCPClient with X-Anon-Enabled: true
   - Calls MCP `submit_for_deanonymization({tokens: [...]})`
   - Fallback parsers: mapping/map/replacements keys
   - Returns `DeanonymizeResponse(mapping=...)` with `Cache-Control: no-store, private`

5. **Models** (`models.py`): `DeanonymizeRequest` with Pydantic strict + per-token regex validation in `model_post_init`. `DeanonymizeResponse` with `mapping: dict[str, str]`.

6. **Migration v4** (`storage/migrations.py`): `ALTER TABLE card_states ADD COLUMN anon_tokens TEXT`. `CURRENT_VERSION = 4`.

7. **persistence.py**: `save_card_state` extended with `anon_tokens: list[str] | None`. `get_card_anon_tokens(db, card_id) → list[str]` added.

8. **cards.py**: `_extract_anon_tokens_from_payload()` recursive walker using `_ANON_TOKEN_RE`. `TableCardPayload.card_id`, `ObjectCardPayload.card_id` added (matching existing `LogCardPayload.card_id`).

**Tests**: 23 backend tests pass (9 test_anonymization + 8 test_deanonymize_route + 6 additional from test_log_cards_route).

### T-04-01-2: Frontend — toggle Header + visual highlight + Раскрыть button

1. **lib/storage.ts**: Added `getAnonEnabled()` and `setAnonEnabled()` with key `analyst.anon_enabled`.

2. **lib/anon-tokens.ts**: `ANON_TOKEN_RE`, `highlightAnonTokens(text, replacements?)`, `extractAnonTokens(value)` — pure functions, SSR-safe.

3. **AnonymizationToggle.tsx**: SSR-safe (useEffect reads localStorage on mount), dispatches `anon-toggle` CustomEvent, amber ON / neutral OFF styling with Lock/LockOpen icons, aria-pressed.

4. **Header.tsx**: `<AnonymizationToggle />` inserted in right block before `<ModelBadge />`.

5. **useChatStream.ts**: `X-Anon-Enabled: "true"` header added on POST /chat fetch when `getAnonEnabled()` returns true.

6. **Markdown.tsx**: `renderWithAnon(children)` helper applied to `p`, `td`, `li` renderers — passes text nodes through `highlightAnonTokens()`.

7. **TableCard.tsx**, **ObjectCard.tsx**, **LogCard.tsx**: 
   - `onDeanonymize?: (tokens: string[]) => Promise<Record<string,string>>` prop
   - `extractAnonTokens(payload)` via useMemo
   - Footer shows «Раскрыть реальные значения (N)» button when tokens present
   - Click → `await onDeanonymize(tokens)` → `setRevealedMap(mapping)`
   - After reveal: «Реальные значения» emerald badge, button disappears
   - Error → `publishToast({type: "error"})`

8. **CardRenderer.tsx**: `makeOnDeanonymize(cardId)` helper wires `deanonymizeCard()` API call into each card type.

9. **lib/api.ts**: `deanonymizeCard(sessionId, messageId, cardId, tokens)` function.

10. **lib/types.ts**: `DeanonymizeRequest`, `DeanonymizeResponse`, `card_id?` on all card payloads.

**Tests**: 25 frontend tests pass:
- 14 anon-tokens (highlightAnonTokens + extractAnonTokens)
- 5 AnonymizationToggle (default OFF, click ON/OFF, localStorage, CustomEvent)
- 6 TableCard.anon (amber highlight, Раскрыть button, click callback, success reveal, error toast)

## Metrics

| Metric | Value |
|--------|-------|
| Backend tests | 23 green |
| Frontend tests | 25 green |
| Backend coverage log_cards.py | 91.8% |
| Frontend type-check | PASS |
| Frontend lint | PASS (0 warnings) |
| TODO/FIXME/placeholder | 0 |
| Files created | 7 |
| Files modified | 18 |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

### Minor Adjustments

1. **LogCard.tsx incomplete at plan start** — The file had `onDeanonymize` in the interface and state variables declared but the reveal button was not rendered and `revealedMap` was not passed to `LogEntryRow`. Added `tokensInPayload` useMemo, `handleReveal()`, the anon footer section, and wired `revealedMap` to `LogEntryRow`.

2. **Pre-existing useChatStream test failures (10 tests)** — These failures existed before Plan 04-01 (confirmed via git stash). Not caused by our changes. Scope boundary: left as-is, noted here.

## Known Stubs

1. **MCP submit_for_deanonymization real response shape** — The actual 1С MCP Toolkit v1.7.0 response format for `submit_for_deanonymization` is not verified against live server. The backend endpoint has fallback parsers (`mapping` / `map` / `replacements` keys). After first E2E test with live 1С:
   - If MCP returns different key → add to fallback list in `deanonymize_card()`
   - If MCP returns array instead of dict → add another fallback branch

2. **Real values not shown after page reload** — Design intent: `revealedMap` is React state only, lost on reload. User must re-click «Раскрыть». This is documented in T-04-02 threat mitigations.

## Threat Flags

None — all new endpoints covered by plan's threat model (T-04-01..T-04-08).

## Commits

| Hash | Message |
|------|---------|
| `0096834` | feat(04-01): backend anon forwarding + deanonymize endpoint + migration v4 |
| `4f3dab2` | feat(04-01): frontend anon toggle + visual highlight + Раскрыть button |

## Self-Check

### Files exist
- [x] `frontend/lib/anon-tokens.ts`
- [x] `frontend/components/shell/AnonymizationToggle.tsx`
- [x] `backend/tests/test_anonymization.py`
- [x] `backend/tests/test_deanonymize_route.py`
- [x] `backend/app/routes/log_cards.py` (contains `deanonymize`)
- [x] `backend/app/clients/mcp.py` (has `_extra_headers`)
- [x] `backend/app/storage/migrations.py` (contains `MIGRATIONS_V4`)

### Commits exist
- [x] `0096834` — verified in git log
- [x] `4f3dab2` — verified in git log

## Self-Check: PASSED
