/**
 * Capability matrix — 23 feature flags для Multi-MCP + EPF/CFE delivery.
 *
 * G10 (M-K0.10): создан как pre-flight для M-K1.
 *
 * Источник истины: backend/app/types/capabilities.py (single source).
 * Должен быть синхронизирован вручную (или через codegen в M-K1.10).
 *
 * Использование:
 * - useCapability(feature) hook — feature gating per канал
 * - UpgradeCTA — показ «эта фича в CFE» если capability отсутствует
 * - SourceSelector — фильтрация tools по mode
 */

// ---------------------------------------------------------------------------
// Base (8) — всегда доступны при любом MCP канале
// ---------------------------------------------------------------------------

export const CAPABILITIES_BASE = [
  'mcp.execute_query',
  'mcp.get_metadata',
  'mcp.get_object',
  'mcp.get_link_of_object',
  'mcp.find_references',
  'mcp.get_access_rights',
  'mcp.get_event_log',
  'mcp.get_bsl_syntax_help',
] as const;

export type CapabilityBase = (typeof CAPABILITIES_BASE)[number];

// ---------------------------------------------------------------------------
// Conditional (3) — зависят от установленных расширений
// ---------------------------------------------------------------------------

export const CAPABILITIES_CONDITIONAL = [
  'tools_ui.query_console',
  'mcp.execute_code',
  'mcp.submit_for_deanonymization',
] as const;

export type CapabilityConditional = (typeof CAPABILITIES_CONDITIONAL)[number];

// ---------------------------------------------------------------------------
// CFE extended (12) — только при подключении CFE АналитикПлюс
// ---------------------------------------------------------------------------

export const CAPABILITIES_CFE = [
  'cfe.activity_stream',
  'cfe.posting_trace',
  'cfe.bsl_diagnostics',
  'cfe.method_overrides',
  'cfe.hmac_sso',
  'cfe.refactor_planner',
  'cfe.compliance_check',
  'cfe.knowledge_graph',
  'cfe.rls_tracer',
  'cfe.deadlock_tracer',
  'cfe.posting_explainer',
  'cfe.subsystem_metadata',
] as const;

export type CapabilityCFE = (typeof CAPABILITIES_CFE)[number];

// ---------------------------------------------------------------------------
// Union
// ---------------------------------------------------------------------------

export type Capability = CapabilityBase | CapabilityConditional | CapabilityCFE;

export const ALL_CAPABILITIES: ReadonlyArray<Capability> = [
  ...CAPABILITIES_BASE,
  ...CAPABILITIES_CONDITIONAL,
  ...CAPABILITIES_CFE,
];

// Sanity check at module load
if (ALL_CAPABILITIES.length !== 23) {
  throw new Error(`Expected 23 capabilities, got ${ALL_CAPABILITIES.length}`);
}

// ---------------------------------------------------------------------------
// Channel modes
// ---------------------------------------------------------------------------

export type ChannelMode = 'mcp_only' | 'epf' | 'cfe';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Возвращает набор capabilities ожидаемый для данного режима канала.
 * См. backend/app/types/capabilities.py:filter_capabilities_for_mode.
 */
export function expectedCapabilitiesForMode(
  mode: ChannelMode,
): ReadonlyArray<Capability> {
  if (mode === 'mcp_only') return CAPABILITIES_BASE;
  if (mode === 'epf')
    return [...CAPABILITIES_BASE, ...CAPABILITIES_CONDITIONAL];
  if (mode === 'cfe') return ALL_CAPABILITIES;
  throw new Error(`Unknown channel mode: ${mode}`);
}

/**
 * Фильтрует список capabilities до известных нам. Незнакомые игнорируются
 * с console.warn (forward-compat).
 */
export function validateCapabilityList(caps: string[]): Capability[] {
  const valid: Capability[] = [];
  const known = new Set(ALL_CAPABILITIES);
  for (const cap of caps) {
    if (known.has(cap as Capability)) {
      valid.push(cap as Capability);
    } else {
      if (process.env.NODE_ENV !== 'production') {
        // eslint-disable-next-line no-console
        console.warn(`[capabilities] unknown capability ignored: ${cap}`);
      }
    }
  }
  return valid;
}

/**
 * Проверка одного capability для use в useCapability hook (M-K1.10).
 */
export function hasCapability(
  activeCapabilities: ReadonlyArray<Capability> | undefined | null,
  feature: Capability,
): boolean {
  if (!activeCapabilities) return false;
  return activeCapabilities.includes(feature);
}
