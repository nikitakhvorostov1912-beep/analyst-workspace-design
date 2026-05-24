"""Skill preprocessing — template vars + inline shell substitution.

Sprint 5 (Hermes A11): подстановка переменных вида ${ANALYST_SESSION_ID},
${ANALYST_CHANNEL_ID}, ${ANALYST_NOW} в теле skill'ов перед инжектом в prompt.

Inline shell `!`date +%Y-%m-%d`` опционально — отключён по умолчанию (require
opt-in через флаг shell_enabled). Это безопасный default — в production даже
доверенный skill не должен запускать subprocess'ы автоматически.

Cap output 4000 байт (как в Hermes).
"""

from __future__ import annotations

import logging
import re
import subprocess  # noqa: S404 — намеренно для inline shell, см. shell_enabled
import sys
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# 2026-05-24 (FINDING-17): на Windows подавляем создание консольного окна
# для дочерних shell-вызовов (когда backend запущен из Electron windowsHide).
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


# ${VAR} pattern. Не поддерживаем ${VAR:-default} — это не bash, namespace простой.
_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Inline shell: !`command`!  (восклицательные знаки чтобы не путать с обычными ` `)
_SHELL_RE = re.compile(r"!`([^`]+)`!")

MAX_OUTPUT_BYTES = 4_000


def build_default_context(
    *,
    session_id: str = "",
    channel_id: str = "",
    now: datetime | None = None,
) -> dict[str, str]:
    """Стандартный набор template-переменных."""
    now = now or datetime.now(UTC)
    return {
        "ANALYST_SESSION_ID": session_id,
        "ANALYST_CHANNEL_ID": channel_id,
        "ANALYST_NOW": now.isoformat(),
        "ANALYST_TODAY": now.strftime("%Y-%m-%d"),
    }


def preprocess_skill_body(
    body: str,
    *,
    context: dict[str, str] | None = None,
    shell_enabled: bool = False,
) -> str:
    """Подставляет ${VAR} и опционально выполняет !`shell`!.

    Args:
        body: исходный текст skill.
        context: dict переменных. None → пусто (все ${} останутся).
        shell_enabled: опт-ин для inline shell.

    Returns:
        Обработанный текст. Cap MAX_OUTPUT_BYTES.
    """
    if not body:
        return body

    out = body
    if context:
        def _sub_var(m: re.Match[str]) -> str:
            return context.get(m.group(1), m.group(0))
        out = _VAR_RE.sub(_sub_var, out)

    if shell_enabled:
        def _sub_shell(m: re.Match[str]) -> str:
            cmd = m.group(1).strip()
            try:
                # 5s timeout, нет shell pipes — exec по списку.
                # Для простоты разрешаем shell-syntax через shell=True, но
                # caller отвечает за trust skill body.
                result = subprocess.run(  # noqa: S602 — opt-in
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=5.0, check=False,
                    creationflags=_CREATE_NO_WINDOW,
                )
                output = (result.stdout or result.stderr or "").strip()
                return output[:200]
            except subprocess.TimeoutExpired:
                logger.warning("Skill shell timeout: %s", cmd[:80])
                return "[shell_timeout]"
            except Exception:
                logger.warning("Skill shell error: %s", cmd[:80], exc_info=True)
                return "[shell_error]"
        out = _SHELL_RE.sub(_sub_shell, out)

    if len(out) > MAX_OUTPUT_BYTES:
        out = out[:MAX_OUTPUT_BYTES] + "\n...[truncated]"
    return out
