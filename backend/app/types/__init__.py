"""Centralized typed registries для backend.

Содержит:
- `capabilities.py` — 23 capabilities matrix (M6 Phase 12, ADR-004)
- В будущем — Cards registry (Python side, для backend validation card types)

Все enums — через `Literal[...]` (Pydantic v2 friendly) или `IntFlag` если
нужны bitmasks. Не используем `enum.Enum` — он создаёт лишний namespace и
плохо serialize в JSON.
"""
