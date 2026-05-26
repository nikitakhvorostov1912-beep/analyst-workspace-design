"""Typical Configurations Knowledge package (M-K2.5).

Снапшоты типовых конфигураций 1С (УТ / ERP / КА / БП / ЗУП / УСО /
Документооборот) — структура / код / графы / описательные карточки.

Phases:
- M-K2.5.0 (this) — Infrastructure: registry + storage + migration v17
- M-K2.5.1 — BSL Parser AST
- M-K2.5.2 — Query Parser
- M-K2.5.3 — XML Metadata Parser
- M-K2.5.4 — Semantic Graph Builder (6 graphs via graph_storage)
- M-K2.5.5 — Object Cards Generator (LLM, embedding только описаний)
- M-K2.5.6 — LLM Tools (search_typical / explain_object / ...)
- M-K2.5.7 — Frontend UI
- M-K2.5.8 — Run all 7 configurations

См. `.planning/.../M-K2.5/M-K2.5-PLAN.md` для полного плана и
`.planning/.../M-K2.5/ADR-003-typical-configurations.md` для дизайн-решений.
"""

from app.knowledge.typical.bsl_ast import parse_file, parse_module, parse_string
from app.knowledge.typical.bsl_models import (
    BSLMethod,
    BSLMethodKind,
    BSLModule,
    BSLParameter,
    BSLRegion,
)
from app.knowledge.typical.registry import (
    DISPLAY_NAMES,
    RESERVED_PREFIXES,
    TypicalConfigKind,
    parse_version_tuple,
    reserved_channel_id,
)
from app.knowledge.typical.storage import (
    ConfigurationStatus,
    IndexingPhase,
    IndexingRunStatus,
    TypicalConfiguration,
    TypicalIndexingRun,
    create_configuration,
    create_run,
    delete_configuration,
    get_configuration_by_channel,
    get_configuration_by_kind_version,
    list_configurations,
    list_runs,
    update_configuration_status,
    update_run_progress,
)

__all__ = [
    # registry
    "TypicalConfigKind",
    "RESERVED_PREFIXES",
    "DISPLAY_NAMES",
    "reserved_channel_id",
    "parse_version_tuple",
    # storage — models
    "TypicalConfiguration",
    "TypicalIndexingRun",
    "ConfigurationStatus",
    "IndexingPhase",
    "IndexingRunStatus",
    # storage — operations
    "create_configuration",
    "get_configuration_by_channel",
    "get_configuration_by_kind_version",
    "list_configurations",
    "update_configuration_status",
    "delete_configuration",
    "create_run",
    "update_run_progress",
    "list_runs",
    # bsl_ast — models
    "BSLMethod",
    "BSLMethodKind",
    "BSLModule",
    "BSLParameter",
    "BSLRegion",
    # bsl_ast — operations
    "parse_module",
    "parse_string",
    "parse_file",
]
