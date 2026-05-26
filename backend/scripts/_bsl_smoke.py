"""Быстрый smoke-прогон BSL parser на уже выгруженных модулях.

Не использует БД (чтобы не конфликтовать с typical_pilot.py). Просто
парсит все *.bsl в указанной папке, собирает метрики и показывает
top-N ошибок.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.knowledge.typical.bsl_ast import parse_module  # noqa: E402
from app.knowledge.typical.query_parser import extract_queries_from_method  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Папка для рекурсивного поиска *.bsl")
    parser.add_argument("--max", type=int, default=None, help="Лимит файлов (debug)")
    parser.add_argument("--queries", action="store_true", help="Также прогнать query parser")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"NOT_A_DIR: {root}", file=sys.stderr)
        return 1

    files = sorted(root.rglob("*.bsl"))
    if args.max:
        files = files[: args.max]

    print(f"Found {len(files)} BSL files")
    print("=" * 60)

    started = time.perf_counter()

    total_lines = 0
    total_methods = 0
    total_exports = 0
    total_regions = 0
    total_with_preproc = 0
    total_customization_markers = 0
    parse_error_files: list[Path] = []
    fatal_errors: list[tuple[Path, str]] = []
    biggest: list[tuple[int, Path]] = []
    directive_counter: Counter[str] = Counter()

    total_queries = 0
    virtual_tables_counter: Counter[str] = Counter()
    register_counter: Counter[str] = Counter()
    top_tables_counter: Counter[str] = Counter()

    for i, f in enumerate(files):
        try:
            try:
                src = f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                src = f.read_text(encoding="cp1251")
            module = parse_module(src, module_path=str(f))
        except Exception as exc:
            fatal_errors.append((f, f"{type(exc).__name__}: {exc}"))
            continue

        total_lines += module.total_lines
        total_methods += len(module.methods)
        total_exports += len(module.exported_methods)
        total_regions += len(module.regions)
        if module.has_preprocessor_branches:
            total_with_preproc += 1
        if module.has_errors:
            parse_error_files.append(f)

        for m in module.methods:
            if m.compile_directive:
                # Берём первое слово после &
                directive_counter[m.compile_directive.split("(")[0].strip()] += 1
            if m.customization_marker is not None:
                total_customization_markers += 1

        biggest.append((len(module.methods), f))

        if args.queries:
            for m in module.methods:
                if not m.body_source:
                    continue
                queries = extract_queries_from_method(m.body_source)
                for q in queries:
                    total_queries += 1
                    for t in q.tables:
                        if not t.is_temp_table:
                            top_tables_counter[t.name] += 1
                    for vt in q.virtual_tables:
                        virtual_tables_counter[vt.virtual_kind] += 1
                        register_counter[vt.register_type] += 1

        if (i + 1) % 500 == 0:
            elapsed_so_far = time.perf_counter() - started
            print(
                f"  [{i + 1}/{len(files)}] {elapsed_so_far:.1f}s "
                f"({(i + 1) / elapsed_so_far:.1f} files/sec)"
            )

    elapsed = time.perf_counter() - started
    biggest.sort(reverse=True)

    print()
    print(f"===== SUMMARY ({elapsed:.1f}s) =====")
    print(f"Files parsed:        {len(files) - len(fatal_errors)}/{len(files)}")
    print(f"Files/sec:           {len(files) / elapsed:.1f}")
    print(f"Total lines:         {total_lines:,}")
    print(f"Total methods:       {total_methods:,}")
    print(f"  exported:          {total_exports:,}")
    print(f"Total regions:       {total_regions:,}")
    print(f"Modules with #Если:  {total_with_preproc}")
    print(f"// Доработка marks:  {total_customization_markers}")
    print()
    print("Compile directives (top 15):")
    for d, c in directive_counter.most_common(15):
        print(f"  {d.ljust(40)} {c}")
    print()
    print(f"Parse errors (tree-sitter found issue):  {len(parse_error_files)}")
    for p in parse_error_files[:5]:
        print(f"  - {p.relative_to(root)}")
    print()
    print(f"Fatal errors (parser crashed):  {len(fatal_errors)}")
    for p, exc in fatal_errors[:5]:
        print(f"  - {p.relative_to(root)} :: {exc}")
    print()
    print("Top 5 biggest modules (by method count):")
    for count, p in biggest[:5]:
        print(f"  {count:4d} methods - {p.relative_to(root)}")

    if args.queries:
        print()
        print(f"===== QUERIES =====")
        print(f"Total queries found:   {total_queries:,}")
        print(f"Virtual table kinds:")
        for k, c in virtual_tables_counter.most_common():
            print(f"  {k.ljust(30)} {c}")
        print(f"Register types:")
        for k, c in register_counter.most_common():
            print(f"  {k.ljust(30)} {c}")
        print(f"Top 10 tables:")
        for t, c in top_tables_counter.most_common(10):
            print(f"  {t.ljust(50)} {c}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
