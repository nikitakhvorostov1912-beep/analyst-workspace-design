"""Pilot CLI: прогоняет парсеры (XML metadata + BSL + Queries) на
выгрузке типовой конфигурации (`DumpConfigToFiles`).

Запуск:
    cd backend
    python -m scripts.typical_pilot \
        --kind KA_2 \
        --version "2.5.25.92" \
        --snapshot "C:\\...\\data\\typical-snapshots\\ka2-2.5.25.92" \
        --db "data/pilot.db"

Что делает:
1. Применяет миграции (создаёт `typical_configurations` + `typical_indexing_runs`)
2. Создаёт snapshot-запись в БД
3. Прогоняет XML parser → собирает count_by_kind метрики
4. Прогоняет BSL parser по всем модулям → собирает методы / regions / parse_errors
5. Прогоняет Query parser по найденным методам → собирает tables / virtual_tables
6. Финализирует UPDATE status = PARSED + сохраняет JSON-сводку в БД

Результат — сводный отчёт в stdout + запись в БД для последующих phases.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import aiosqlite

# Добавляем backend/ в sys.path чтобы import app.* работал при запуске
# через `python -m scripts.typical_pilot`
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.typical import (  # noqa: E402
    BSLModule,
    ConfigurationStatus,
    IndexingPhase,
    IndexingRunStatus,
    MetadataKind,
    TypicalConfigKind,
    create_configuration,
    create_run,
    discover_metadata_files,
    extract_queries_from_method,
    parse_configuration_tree,
    parse_module,
    update_configuration_status,
    update_run_progress,
)
from app.storage.migrations import apply_migrations  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pilot")


async def _ensure_db(db_path: Path) -> aiosqlite.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(db_path))
    await conn.execute("PRAGMA foreign_keys = ON")
    await apply_migrations(conn)
    return conn


async def _phase_parse_metadata(
    db: aiosqlite.Connection,
    config_id: int,
    snapshot_dir: Path,
) -> dict:
    """Phase: parse XML metadata. Возвращает summary."""
    run = await create_run(db, config_id, IndexingPhase.PARSE_METADATA)
    await update_run_progress(db, run.id, status=IndexingRunStatus.IN_PROGRESS)

    started = time.perf_counter()
    # Skip Roles + Pictures + Templates — массивные но не нужны для пилота
    skip = {
        MetadataKind.ROLE,
        MetadataKind.COMMON_PICTURE,
        MetadataKind.COMMON_TEMPLATE,
        MetadataKind.COMMON_ATTRIBUTE,
    }

    try:
        configuration = parse_configuration_tree(snapshot_dir, skip_kinds=skip)
    except Exception as exc:
        await update_run_progress(
            db, run.id,
            status=IndexingRunStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}",
            finished=True,
        )
        raise

    elapsed = time.perf_counter() - started
    summary = {
        "elapsed_s": round(elapsed, 2),
        "total_objects": configuration.total_objects,
        "count_by_kind": configuration.count_by_kind(),
        "configuration_name": configuration.name,
        "configuration_version": configuration.version,
        "configuration_vendor": configuration.vendor,
        "compatibility_mode": configuration.compatibility_mode,
    }
    await update_run_progress(
        db, run.id,
        status=IndexingRunStatus.COMPLETED,
        progress_pct=100,
        items_processed=configuration.total_objects,
        items_total=configuration.total_objects,
        metadata_patch=summary,
        finished=True,
    )
    logger.info(
        f"[parse_metadata] {configuration.total_objects} objects in {elapsed:.1f}s "
        f"({configuration.name} {configuration.version})"
    )
    return {"configuration": configuration, "summary": summary}


def _iter_bsl_files(snapshot_dir: Path) -> list[Path]:
    """Все BSL модули в выгрузке."""
    return sorted(snapshot_dir.rglob("*.bsl"))


async def _phase_parse_bsl(
    db: aiosqlite.Connection,
    config_id: int,
    snapshot_dir: Path,
    *,
    max_files: int | None = None,
) -> dict:
    """Phase: parse BSL modules. Возвращает summary + список BSLModule."""
    run = await create_run(db, config_id, IndexingPhase.PARSE_BSL)
    await update_run_progress(db, run.id, status=IndexingRunStatus.IN_PROGRESS)

    started = time.perf_counter()
    bsl_files = _iter_bsl_files(snapshot_dir)
    if max_files is not None:
        bsl_files = bsl_files[:max_files]

    await update_run_progress(db, run.id, items_total=len(bsl_files))

    parsed: list[tuple[Path, BSLModule]] = []
    total_methods = 0
    total_exports = 0
    total_regions = 0
    parse_error_files: list[str] = []
    error_modules: list[tuple[str, str]] = []

    for i, bsl_path in enumerate(bsl_files):
        try:
            raw = bsl_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = bsl_path.read_text(encoding="cp1251")
        try:
            module = parse_module(raw, module_path=str(bsl_path))
        except Exception as exc:
            error_modules.append((str(bsl_path), f"{type(exc).__name__}: {exc}"))
            continue
        parsed.append((bsl_path, module))
        total_methods += len(module.methods)
        total_exports += len(module.exported_methods)
        total_regions += len(module.regions)
        if module.has_errors:
            parse_error_files.append(str(bsl_path.relative_to(snapshot_dir)))

        if (i + 1) % 500 == 0:
            await update_run_progress(
                db, run.id,
                items_processed=i + 1,
                progress_pct=int((i + 1) / len(bsl_files) * 100),
            )

    elapsed = time.perf_counter() - started
    summary = {
        "elapsed_s": round(elapsed, 2),
        "total_bsl_files": len(bsl_files),
        "parsed_modules": len(parsed),
        "total_methods": total_methods,
        "total_exported": total_exports,
        "total_regions": total_regions,
        "parse_errors_count": len(parse_error_files),
        "parse_errors_first_10": parse_error_files[:10],
        "fatal_errors_count": len(error_modules),
        "fatal_errors_first_5": error_modules[:5],
    }
    await update_run_progress(
        db, run.id,
        status=IndexingRunStatus.COMPLETED,
        progress_pct=100,
        items_processed=len(bsl_files),
        metadata_patch=summary,
        finished=True,
    )
    logger.info(
        f"[parse_bsl] {len(parsed)}/{len(bsl_files)} files in {elapsed:.1f}s, "
        f"{total_methods} methods ({total_exports} Export), "
        f"{len(parse_error_files)} with parse errors, {len(error_modules)} fatal"
    )
    return {"summary": summary, "parsed": parsed}


async def _phase_parse_queries(
    db: aiosqlite.Connection,
    config_id: int,
    parsed_modules: list[tuple[Path, BSLModule]],
) -> dict:
    """Phase: parse queries from method bodies."""
    run = await create_run(db, config_id, IndexingPhase.PARSE_QUERIES)
    await update_run_progress(db, run.id, status=IndexingRunStatus.IN_PROGRESS)

    started = time.perf_counter()
    total_queries = 0
    total_tables = 0
    total_virtual_tables = 0
    virtual_kind_counter: Counter[str] = Counter()
    register_type_counter: Counter[str] = Counter()
    top_tables_counter: Counter[str] = Counter()

    for _path, module in parsed_modules:
        for method in module.methods:
            if not method.body_source:
                continue
            queries = extract_queries_from_method(
                method.body_source,
                source_method=method.name,
                method_line_offset=method.line_start - 1,
            )
            for q in queries:
                total_queries += 1
                total_tables += len(q.tables)
                total_virtual_tables += len(q.virtual_tables)
                for t in q.tables:
                    if not t.is_temp_table:
                        top_tables_counter[t.name] += 1
                for vt in q.virtual_tables:
                    virtual_kind_counter[vt.virtual_kind] += 1
                    register_type_counter[vt.register_type] += 1

    elapsed = time.perf_counter() - started
    summary = {
        "elapsed_s": round(elapsed, 2),
        "total_queries": total_queries,
        "total_table_refs": total_tables,
        "total_virtual_table_refs": total_virtual_tables,
        "virtual_kinds": dict(virtual_kind_counter.most_common()),
        "register_types": dict(register_type_counter.most_common()),
        "top_tables_top20": dict(top_tables_counter.most_common(20)),
    }
    await update_run_progress(
        db, run.id,
        status=IndexingRunStatus.COMPLETED,
        progress_pct=100,
        items_processed=total_queries,
        metadata_patch=summary,
        finished=True,
    )
    logger.info(
        f"[parse_queries] {total_queries} queries in {elapsed:.1f}s, "
        f"{total_virtual_tables} virtual tables, {total_tables} physical tables"
    )
    return {"summary": summary}


async def run_pilot(
    *,
    kind: TypicalConfigKind,
    version: str,
    snapshot_dir: Path,
    db_path: Path,
    max_bsl_files: int | None = None,
) -> dict:
    db = await _ensure_db(db_path)
    try:
        config = await create_configuration(
            db, kind, version, source_path=str(snapshot_dir)
        )
        logger.info(
            f"Created config #{config.id} channel={config.channel_id}"
        )

        meta_result = await _phase_parse_metadata(db, config.id, snapshot_dir)
        bsl_result = await _phase_parse_bsl(
            db, config.id, snapshot_dir, max_files=max_bsl_files
        )
        queries_result = await _phase_parse_queries(
            db, config.id, bsl_result["parsed"]
        )

        await update_configuration_status(
            db, config.channel_id, ConfigurationStatus.PARSED
        )

        return {
            "config": config.to_dict(),
            "metadata": meta_result["summary"],
            "bsl": bsl_result["summary"],
            "queries": queries_result["summary"],
        }
    except Exception:
        try:
            await update_configuration_status(
                db, config.channel_id, ConfigurationStatus.FAILED
            )
        except Exception:
            pass
        raise
    finally:
        await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pilot прогон парсеров на выгрузке типовой конфигурации"
    )
    parser.add_argument(
        "--kind", required=True, choices=[k.value for k in TypicalConfigKind],
        help="Тип конфигурации (UT_115 / ERP_25 / KA_2 / ...)",
    )
    parser.add_argument(
        "--version", required=True,
        help="Версия (например 2.5.25.92)",
    )
    parser.add_argument(
        "--snapshot", required=True,
        help="Путь к выгрузке DumpConfigToFiles",
    )
    parser.add_argument(
        "--db", default="data/pilot.db",
        help="Путь к SQLite БД (default: data/pilot.db)",
    )
    parser.add_argument(
        "--max-bsl-files", type=int, default=None,
        help="Ограничение количества BSL файлов (для отладки)",
    )
    args = parser.parse_args()

    snapshot_dir = Path(args.snapshot)
    if not snapshot_dir.is_dir():
        parser.error(f"Snapshot dir не найдена: {snapshot_dir}")

    config_file = snapshot_dir / "Configuration.xml"
    if not config_file.is_file():
        parser.error(f"В snapshot нет Configuration.xml: {config_file}")

    kind = TypicalConfigKind(args.kind)
    db_path = Path(args.db)

    try:
        result = asyncio.run(
            run_pilot(
                kind=kind,
                version=args.version,
                snapshot_dir=snapshot_dir,
                db_path=db_path,
                max_bsl_files=args.max_bsl_files,
            )
        )
    except Exception as exc:
        logger.exception(f"Pilot упал: {exc}")
        return 1

    print()
    print("===== PILOT SUMMARY =====")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
