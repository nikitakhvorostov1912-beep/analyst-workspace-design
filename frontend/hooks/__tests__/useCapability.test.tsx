/**
 * Tests for hooks/useCapability (M-K1.10).
 */

import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  useCapabilities,
  useCapability,
  useChannelMode,
  useUpgradeAction,
} from '../useCapability';
import type { MCPConnection } from '@/lib/types';

const baseConnection: MCPConnection = {
  id: 'test',
  name: 'Test',
  endpoint: 'http://127.0.0.1:6010/mcp',
  channel: null,
  anon_enabled: false,
};

describe('useCapability', () => {
  it('returns false for null connection', () => {
    const { result } = renderHook(() => useCapability(null, 'mcp.execute_query'));
    expect(result.current).toBe(false);
  });

  it('returns false for undefined connection', () => {
    const { result } = renderHook(() =>
      useCapability(undefined, 'mcp.execute_query'),
    );
    expect(result.current).toBe(false);
  });

  it('returns false when capabilities field is missing (legacy row)', () => {
    const { result } = renderHook(() =>
      useCapability(baseConnection, 'mcp.execute_query'),
    );
    expect(result.current).toBe(false);
  });

  it('returns true when capability is present', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'cfe',
      capabilities: ['mcp.execute_query', 'cfe.activity_stream'],
    };
    const { result } = renderHook(() =>
      useCapability(connection, 'mcp.execute_query'),
    );
    expect(result.current).toBe(true);
  });

  it('returns false when capability is not in list', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'mcp_only',
      capabilities: ['mcp.execute_query'],
    };
    const { result } = renderHook(() =>
      useCapability(connection, 'cfe.activity_stream'),
    );
    expect(result.current).toBe(false);
  });

  it('filters unknown capabilities from connection', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      capabilities: ['totally.unknown.future_cap', 'mcp.execute_query'],
    };
    const { result } = renderHook(() =>
      useCapability(connection, 'mcp.execute_query'),
    );
    expect(result.current).toBe(true);
  });
});

describe('useCapabilities', () => {
  it('returns empty array for null connection', () => {
    const { result } = renderHook(() => useCapabilities(null));
    expect(result.current).toEqual([]);
  });

  it('returns validated capabilities (filters unknowns)', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      capabilities: [
        'mcp.execute_query',
        'cfe.activity_stream',
        'unknown.feature',
      ],
    };
    const { result } = renderHook(() => useCapabilities(connection));
    expect(result.current).toContain('mcp.execute_query');
    expect(result.current).toContain('cfe.activity_stream');
    expect(result.current).not.toContain('unknown.feature');
  });
});

describe('useChannelMode', () => {
  it('returns mcp_only for null connection', () => {
    const { result } = renderHook(() => useChannelMode(null));
    expect(result.current).toBe('mcp_only');
  });

  it('returns mcp_only when mode field is missing', () => {
    const { result } = renderHook(() => useChannelMode(baseConnection));
    expect(result.current).toBe('mcp_only');
  });

  it('returns cfe when mode is set', () => {
    const connection: MCPConnection = { ...baseConnection, mode: 'cfe' };
    const { result } = renderHook(() => useChannelMode(connection));
    expect(result.current).toBe('cfe');
  });
});

describe('useUpgradeAction', () => {
  it('returns null when capability already present', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'cfe',
      capabilities: ['cfe.activity_stream'],
    };
    const { result } = renderHook(() =>
      useUpgradeAction(connection, 'cfe.activity_stream'),
    );
    expect(result.current).toBeNull();
  });

  it('returns install_epf_then_cfe for cfe.* on mcp_only channel', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'mcp_only',
      capabilities: ['mcp.execute_query'],
    };
    const { result } = renderHook(() =>
      useUpgradeAction(connection, 'cfe.activity_stream'),
    );
    expect(result.current).toBe('install_epf_then_cfe');
  });

  it('returns install_cfe for cfe.* on epf channel', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'epf',
      capabilities: ['mcp.execute_query'],
    };
    const { result } = renderHook(() =>
      useUpgradeAction(connection, 'cfe.posting_trace'),
    );
    expect(result.current).toBe('install_cfe');
  });

  it('returns check_mcp_toolkit for missing mcp.* capability', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'mcp_only',
      capabilities: [],
    };
    const { result } = renderHook(() =>
      useUpgradeAction(connection, 'mcp.execute_query'),
    );
    expect(result.current).toBe('check_mcp_toolkit');
  });

  it('returns install_tools_ui_optional for missing tools_ui.*', () => {
    const connection: MCPConnection = {
      ...baseConnection,
      mode: 'mcp_only',
      capabilities: ['mcp.execute_query'],
    };
    const { result } = renderHook(() =>
      useUpgradeAction(connection, 'tools_ui.query_console'),
    );
    expect(result.current).toBe('install_tools_ui_optional');
  });
});
