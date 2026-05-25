/**
 * useCapability — React hook для feature gating на основе MCP capability discovery.
 *
 * M-K1.10 (M6 Phase 12.7 + ADR-004).
 *
 * Backend сохраняет capabilities в `MCPConnection.capabilities` (миграция v11),
 * заполняется при `/connections/{id}/ping` через `discover_capabilities()`.
 *
 * Использование:
 * ```tsx
 * const canActivityStream = useCapability(connection, 'cfe.activity_stream');
 * if (!canActivityStream) return <UpgradeCTA feature="cfe.activity_stream" />;
 * ```
 *
 * Hook чистый — никаких side-effects (поэтому не React `useEffect` под капотом,
 * а простой derivation). Возвращает stable boolean который React сравнит по
 * value для re-render оптимизации.
 */

import { useMemo } from 'react';

import {
  type Capability,
  type ChannelMode,
  hasCapability,
  validateCapabilityList,
} from '@/lib/capabilities';
import type { MCPConnection } from '@/lib/types';

/**
 * Проверяет наличие конкретной capability в канале.
 *
 * @param connection — MCPConnection с полем capabilities (M-K1.6)
 * @param feature — capability namespace.feature (e.g. 'cfe.activity_stream')
 * @returns true если capability присутствует в connection.capabilities
 *
 * Гарантии:
 * - undefined/null connection → false (нет канала = нет capability)
 * - missing capabilities[] field → false (legacy row, ещё не прошла discovery)
 * - unknown feature (not в registry) → false (forward-compat)
 */
export function useCapability(
  connection: MCPConnection | null | undefined,
  feature: Capability,
): boolean {
  return useMemo(() => {
    if (!connection) return false;
    const caps = validateCapabilityList(connection.capabilities ?? []);
    return hasCapability(caps, feature);
  }, [connection, feature]);
}

/**
 * Возвращает все валидные capabilities канала (отфильтровано через registry).
 * Полезно для debug-панелей и rendering списков «что доступно».
 */
export function useCapabilities(
  connection: MCPConnection | null | undefined,
): ReadonlyArray<Capability> {
  return useMemo(() => {
    if (!connection?.capabilities) return [];
    return validateCapabilityList(connection.capabilities);
  }, [connection]);
}

/**
 * Возвращает ChannelMode (mcp_only/epf/cfe) канала.
 *
 * Используется для:
 * - UI badge «работает EPF / CFE / только MCP»
 * - Conditional UI (показывать ли «Обновить до CFE» CTA)
 */
export function useChannelMode(
  connection: MCPConnection | null | undefined,
): ChannelMode {
  if (!connection) return 'mcp_only';
  return (connection.mode ?? 'mcp_only') as ChannelMode;
}

/**
 * Хук для UpgradeCTA — возвращает рекомендуемый upgrade path если
 * capability недоступна.
 *
 * - capability доступна → null (CTA не показывать)
 * - capability cfe.* + текущий mode = 'mcp_only' → 'install_epf_then_cfe'
 * - capability cfe.* + текущий mode = 'epf' → 'install_cfe'
 * - capability mcp.* отсутствует → 'check_mcp_toolkit' (что-то странное)
 * - tools_ui.* + не установлен tools_ui_1c → 'install_tools_ui_optional'
 */
export type UpgradeAction =
  | null
  | 'install_epf_then_cfe'
  | 'install_cfe'
  | 'check_mcp_toolkit'
  | 'install_tools_ui_optional';

export function useUpgradeAction(
  connection: MCPConnection | null | undefined,
  feature: Capability,
): UpgradeAction {
  const hasCap = useCapability(connection, feature);
  const mode = useChannelMode(connection);

  if (hasCap) return null;
  if (feature.startsWith('cfe.')) {
    if (mode === 'mcp_only') return 'install_epf_then_cfe';
    if (mode === 'epf') return 'install_cfe';
    return 'install_cfe'; // mode = 'cfe' но capability нет — нестандартно
  }
  if (feature.startsWith('mcp.')) {
    return 'check_mcp_toolkit';
  }
  if (feature.startsWith('tools_ui.')) {
    return 'install_tools_ui_optional';
  }
  return null;
}
