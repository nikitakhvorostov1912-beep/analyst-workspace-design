"""CLI: прогон ИТС-KB phantom-eval (D1) на живом корпусе bsp_chunks.

Использует продуктовую БД (app.db через settings.sqlite_path). Требует, чтобы
БСП-корпус был проиндексирован (bsp_chunks непустой). Без корпуса детектору
нечего сверять → tp=0 (не ошибка, просто нет данных).

    python -m scripts.run_its_kb_eval

Exit code 0 если precision==1.0 и recall>=0.95, иначе 1 (для CI-гейта).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import aiosqlite  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.knowledge.its_kb_eval import (  # noqa: E402
    evaluate_phantom_detection,
    load_golden,
)


async def amain() -> int:
    settings = get_settings()
    db_path = settings.sqlite_path
    print(f"ИТС-KB phantom-eval на {db_path}")
    conn = await aiosqlite.connect(db_path)
    try:
        cur = await conn.execute("SELECT COUNT(*) FROM bsp_chunks")
        corpus = (await cur.fetchone())[0]
        print(f"bsp_chunks в корпусе: {corpus}")
        golden = load_golden()
        result = await evaluate_phantom_detection(conn, golden)
        print(result.summary())
        for failure in result.failures:
            print(f"  MISMATCH {failure['id']}: expected={failure['expected']} got={failure['got']}")
    finally:
        await conn.close()
    ok = result.precision == 1.0 and result.recall >= 0.95
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
