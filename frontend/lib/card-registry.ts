/**
 * Cards registry — 19 типов inline cards для chat-консоли.
 *
 * G11 (M-K0.10): создан как pre-flight для M-K3 17.7.
 *
 * 19 типов = 6 existing (table/object/log/metric/references/code) +
 *            13 новых из Knowledge Layer + M6 handoff (M-K3/M-K4):
 *
 * Распределение по фазам:
 * - existing (6) — уже в orchestrator/cards.py
 * - M-K3.17 (3) — GraphCard, DiagnoseCard, BSLDiagnostics
 * - M-K4.16 (5) — TimelineCard, PostingTrace, ProcessCard, Metrics, MetaVisionGraph
 * - M-K4.17 (4) — StandardsCitation, ITSArticle, BSPMethod, PlatformHelp
 * - M-K5 (1) — ComparisonCard
 * - phase 15 (1) — Antipattern (через BSL LS)
 *
 * Использование:
 * - CardRenderer (M-K3) — dispatch по `type` поле
 * - Backend `app/orchestrator/cards.py` — validation card type перед persist
 *   (если backend начнёт типизированно работать с new cards в M-K3+)
 */

// ---------------------------------------------------------------------------
// Existing cards (already in production, 6)
// ---------------------------------------------------------------------------

export const CARD_TYPES_EXISTING = [
  'table', // execute_query results
  'object', // get_object_by_link
  'log', // get_event_log
  'metric', // KPI / counter
  'references', // find_references_to_object
  'code', // bsl_syntax_help / code snippets
] as const;

export type CardTypeExisting = (typeof CARD_TYPES_EXISTING)[number];

// ---------------------------------------------------------------------------
// New cards — Knowledge Layer + M6 (13)
// ---------------------------------------------------------------------------

export const CARD_TYPES_KNOWLEDGE = [
  // M-K3 17.7 — Knowledge Graph + Diagnose
  'graph',           // L2 Knowledge Graph (React Flow)
  'diagnose',        // L4 Diagnose Engine result
  'bsl_diagnostics', // BSL LS warnings (Phase 15)

  // M-K4 — Activity Stream + Behavioral
  'timeline',         // Activity Stream events
  'posting_trace',    // Per-document posting trace
  'process',          // L4 reasoning chain
  'metrics',          // OPS-2 telemetry dashboard
  'metavision_graph', // MetaVision visualization (if Phase 16.0 GO)

  // M-K4 17.7 — L5 RAG citations
  'standards_citation', // ИТС standard citation
  'its_article',        // Полный ИТС article preview
  'bsp_method',         // БСП method documentation
  'platform_help',      // .hbk parser output (если M-K2.4 SUCCESS)

  // M-K3 Phase 15 — antipattern detection
  'antipattern', // A1-A11 antipattern warning

  // M-K5
  'comparison', // vs Типовой comparison
] as const;

export type CardTypeKnowledge = (typeof CARD_TYPES_KNOWLEDGE)[number];

// ---------------------------------------------------------------------------
// Union
// ---------------------------------------------------------------------------

export type CardType = CardTypeExisting | CardTypeKnowledge;

export const ALL_CARD_TYPES: ReadonlyArray<CardType> = [
  ...CARD_TYPES_EXISTING,
  ...CARD_TYPES_KNOWLEDGE,
];

// Sanity check (6 existing + 14 new = 20)
// NB: считаем 14 потому что в этом файле перечисли 14 новых
if (ALL_CARD_TYPES.length !== 20) {
  throw new Error(`Expected 20 card types, got ${ALL_CARD_TYPES.length}`);
}

// ---------------------------------------------------------------------------
// Capability requirements per card type
// ---------------------------------------------------------------------------

import type { Capability } from './capabilities';

/**
 * Связь card type → required capability. Если capability отсутствует —
 * фронт показывает UpgradeCTA вместо реальной карточки.
 *
 * `null` = карточка работает на любом канале (existing 6 + некоторые
 * Knowledge cards которые из локальной БД).
 */
export const CARD_REQUIRES_CAPABILITY: Record<CardType, Capability | null> = {
  // Existing — capability-agnostic (работают через базовый MCP)
  table: 'mcp.execute_query',
  object: 'mcp.get_object',
  log: 'mcp.get_event_log',
  metric: null,
  references: 'mcp.find_references',
  code: 'mcp.get_bsl_syntax_help',

  // Knowledge — некоторые работают из локальной БД, некоторые требуют CFE
  graph: 'cfe.knowledge_graph',
  diagnose: null, // L4 rulebook YAML — locally evaluable
  bsl_diagnostics: 'cfe.bsl_diagnostics',
  timeline: 'cfe.activity_stream',
  posting_trace: 'cfe.posting_trace',
  process: 'cfe.posting_explainer',
  metrics: null, // OPS-2 telemetry — local SQLite
  metavision_graph: 'cfe.knowledge_graph', // (либо MetaVisionGraph fallback)
  standards_citation: null, // sfaqer v8std локальный
  its_article: null,
  bsp_method: null, // ssl_3_2 локальный
  platform_help: null, // если есть .hbk
  antipattern: 'cfe.bsl_diagnostics', // через BSL LS в CFE
  comparison: null, // reference configurations — local
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Проверка может ли данный канал отрендерить карточку этого типа.
 */
export function canRenderCard(
  cardType: CardType,
  activeCapabilities: ReadonlyArray<Capability> | undefined | null,
): boolean {
  const required = CARD_REQUIRES_CAPABILITY[cardType];
  if (required === null) return true; // capability-agnostic
  if (!activeCapabilities) return false;
  return activeCapabilities.includes(required);
}

/**
 * Возвращает required capability для карточки — для показа UpgradeCTA.
 */
export function getRequiredCapability(cardType: CardType): Capability | null {
  return CARD_REQUIRES_CAPABILITY[cardType];
}
