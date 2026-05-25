"""Prompt injection scanner для данных из 1С / внешних источников.

Port of Hermes `agent/prompt_builder.py:_CONTEXT_THREAT_PATTERNS`.

Используется ПЕРЕД инжектом любого контента из 1С в SYSTEM_PROMPT
(MEMORY.md / USER.md, knowledge base, tool results, attachments).

Стратегия: regex-сканер обнаруживает 10 типов угроз. `scan()` возвращает
список найденных. `sanitize_for_prompt()` нейтрализует совпадения,
заменяя на `[REDACTED: <label>]` чтобы LLM их не выполняла.

SEC-3 (M-K0, 2026-05-25): добавлена unicode NFKD-нормализация перед
regex-проверкой. Атаки через homoglyphs (`Ignоre` с кириллической `о`,
`Ｉgnore` с fullwidth I, etc.) обходили простой `\\bignore\\b` без
NFKD-folding. Теперь все matches идут через canonical form, regex
ловит обоих: «обычный» и «костюмированный» injection.
"""

from __future__ import annotations

import re
import unicodedata

# 8 типов prompt injection threats (адаптировано из Hermes).
# Все паттерны case-insensitive. group(0) — целое совпадение для preview/redaction.
_THREAT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.IGNORECASE),
        "prompt_injection",
    ),
    (
        re.compile(r"забудь\s+(предыдущие|все|выше|предыдущ)", re.IGNORECASE),
        "prompt_injection_ru",
    ),
    (
        re.compile(r"do\s+not\s+tell\s+the\s+user", re.IGNORECASE),
        "deception_hide",
    ),
    (
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        "sys_prompt_override",
    ),
    (
        re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", re.IGNORECASE),
        "disregard_rules",
    ),
    (
        re.compile(
            r"act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'?t\s+have)\s+(restrictions|limits|rules)",
            re.IGNORECASE,
        ),
        "bypass_restrictions",
    ),
    (
        re.compile(r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", re.IGNORECASE),
        "html_comment_injection",
    ),
    (
        re.compile(r"<\s*div\s+style\s*=\s*[\"\'][\s\S]*?display\s*:\s*none", re.IGNORECASE),
        "hidden_div",
    ),
    (
        re.compile(
            r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)",
            re.IGNORECASE,
        ),
        "exfil_curl",
    ),
    (
        re.compile(r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", re.IGNORECASE),
        "translate_execute",
    ),
]


def _normalize(text: str) -> str:
    """SEC-3: канонизация unicode для defeats homoglyph-атак.

    NFKD: Compatibility Decomposition — превращает fullwidth/composite символы
    в их базовые формы (Ｉ → I, ﬁ → fi). Это не полная нормализация
    homoglyphs (NFKD не превратит кириллическую `о` в латинскую `o`), но
    закрывает большой класс fullwidth/circled/superscript injection-tricks.

    Также lower-case применяется самими паттернами (re.IGNORECASE).
    """
    return unicodedata.normalize("NFKD", text or "")


# SEC-3: ручной алиас-map для cross-script homoglyph defense.
# NFKD не объединяет кириллические/латинские/греческие буквы которые ВЫГЛЯДЯТ
# одинаково. Делаем отдельный pass: cyrillic → latin для букв с identical-look.
# Полная Unicode Homoglyph DB огромная — берём минимум для known attacks.
_HOMOGLYPH_MAP: dict[str, str] = {
    # Cyrillic → Latin (визуально неотличимы)
    "а": "a", "А": "A",
    "е": "e", "Е": "E",
    "о": "o", "О": "O",
    "р": "p", "Р": "P",
    "с": "c", "С": "C",
    "у": "y", "У": "Y",
    "х": "x", "Х": "X",
    "к": "k", "К": "K",
    "м": "m", "М": "M",
    "н": "h", "Н": "H",
    "т": "t", "Т": "T",
    "в": "b", "В": "B",
    "і": "i", "І": "I",  # украинская i — выглядит как латинская
    "ј": "j", "Ј": "J",  # сербская
    # Greek → Latin
    "α": "a", "ο": "o", "ρ": "p", "ε": "e", "ν": "v", "η": "n",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I",
    "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T",
    "Υ": "Y", "Χ": "X",
}


def _defang_homoglyphs(text: str) -> str:
    """Заменяет visual-identical буквы из других script на латинские эквиваленты.

    Используется ТОЛЬКО для scan/sanitize check — не модифицирует
    оригинальный текст пользователя.
    """
    return "".join(_HOMOGLYPH_MAP.get(ch, ch) for ch in text)


def _canonicalize_for_scan(text: str) -> str:
    """Полная цепочка нормализации для injection scan.

    1. NFKD — раскладывает composite символы
    2. Homoglyph map — кириллица/греч → латиница
    """
    return _defang_homoglyphs(_normalize(text))


def scan(text: str) -> list[tuple[str, str]]:
    """Найти все matches. Возвращает [(threat_label, matched_preview), ...].

    Empty list = clean. matched_preview обрезан до 120 символов для логов.

    SEC-3: двухпроходный scan:
    1. По оригинальному тексту — русские patterns (regex с кириллицей)
       и обычные английские без homoglyph-обхода.
    2. По canonical форме (NFKD + cyrillic→latin homoglyph defang) —
       английские patterns где атакующий использует кириллическую `о`,
       fullwidth Ｉ, греческую `α` etc.

    Defang применяется ТОЛЬКО для второго прохода — первый видит оригинал,
    иначе русские patterns бы сломались (русская «а» стала бы латинской).

    Дедупликация: один и тот же label не дублируется (если match есть
    и в оригинале, и в canonical — оставляем preview из оригинала).
    """
    if not text:
        return []
    canonical = _canonicalize_for_scan(text)
    hits: list[tuple[str, str]] = []
    seen_labels: set[str] = set()

    # Pass 1: оригинальный текст (русские + английские без homoglyph).
    for pattern, label in _THREAT_PATTERNS:
        m = pattern.search(text)
        if m:
            preview = m.group(0)[:120].replace("\n", " ")
            hits.append((label, preview))
            seen_labels.add(label)

    # Pass 2: canonical (только для homoglyph-варианта). Skip уже найденные.
    # Если text == canonical (нет homoglyph) — pass 2 не даст новых hits.
    if canonical != text:
        for pattern, label in _THREAT_PATTERNS:
            if label in seen_labels:
                continue
            m = pattern.search(canonical)
            if m:
                preview = m.group(0)[:120].replace("\n", " ")
                # Метим как homoglyph-вариант для admin визуально.
                hits.append((f"{label}_homoglyph", preview))
                seen_labels.add(label)

    return hits


def sanitize_for_prompt(text: str) -> str:
    """Заменить все matches на `[REDACTED: <label>]` чтобы LLM их не выполняла.

    Использовать ПЕРЕД инжектом контента из внешних источников (1С, файлы)
    в SYSTEM_PROMPT или в первое user сообщение.

    SEC-3: двухпроходный sanitize:
    1. Replace в оригинале — снимает «обычные» injection patterns
       (включая русские).
    2. Если после прохода 1 canonical форма всё ещё содержит match
       (homoglyph-версия) — оригинал заменяется ПОЛНОСТЬЮ на REDACTED
       marker, потому что точные границы homoglyph-substring без
       offset-tracking не определить.

    Trade-off: при homoglyph attack пользователь может потерять весь
    кусок контента (а не только injection-часть). Это безопаснее, чем
    пропустить injection.
    """
    if not text:
        return text

    # Pass 1: оригинал.
    result = text
    for pattern, label in _THREAT_PATTERNS:
        result = pattern.sub(f"[REDACTED: {label}]", result)

    # Pass 2: проверяем canonical для homoglyph residual.
    canonical = _canonicalize_for_scan(result)
    if canonical != result:
        for pattern, label in _THREAT_PATTERNS:
            if pattern.search(canonical):
                # Найден homoglyph-match. Безопасно заменяем весь блок.
                return f"[REDACTED: {label}_homoglyph]"

    return result


def is_safe(text: str) -> bool:
    """Удобный shorthand: True если scan() вернул пусто."""
    return not scan(text)
