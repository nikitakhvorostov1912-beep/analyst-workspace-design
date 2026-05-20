/* eslint-disable */
// Brand tokens reference — exported as window.STENCIL for use by other modules.
const STENCIL = {
  // Brand core
  signal: '#ff6a3d',
  signalTint: '#ffb38a',
  signalDeep: '#c84a23',
  ink: '#15161a',
  sand: '#f3f1ec',
  sand2: '#e7e4dc',
  sand3: '#ddd9cf',

  // Dark surfaces
  bg0: '#0a0a0a', bg1: '#141414', bg2: '#1a1a1a', bg3: '#202020', bg4: '#262626',

  // FG / borders
  fg1: '#e5e5e5', fg2: '#b3b3b3', fg3: '#8a8a8a', fg4: '#5c5c5c',
  bd1: '#1f1f1f', bd2: '#2a2a2a', bd3: '#3a3a3a',

  // Semantic
  success: '#7cf0c4', warning: '#f7c948', error: '#f87171',

  // Type
  mono: "'IBM Plex Mono', ui-monospace, monospace",
  sans: "'IBM Plex Sans', sans-serif",
  jbm:  "'JetBrains Mono', ui-monospace, monospace",
};

window.STENCIL = STENCIL;

/* ============================================================================
 * pal(theme) — comprehensive palette helper for both themes.
 * Use everywhere instead of reaching into S.bg1 / S.bd2 directly so the same
 * component renders correctly in both light (Sand) and dark (Ink).
 * ============================================================================ */
function pal(theme) {
  const isDark = theme !== 'light';
  return {
    isDark,
    // Surfaces
    bg0:  isDark ? STENCIL.bg0 : STENCIL.sand,         // App background
    bg1:  isDark ? STENCIL.bg1 : '#faf8f3',            // Card / panel surface
    bg2:  isDark ? STENCIL.bg2 : STENCIL.sand2,        // Raised / hover
    bg3:  isDark ? STENCIL.bg3 : STENCIL.sand3,        // Inputs / depressed
    bg4:  isDark ? STENCIL.bg4 : '#cfcabd',            // Strongest sand step
    // Borders
    bd1:  isDark ? STENCIL.bd1 : 'rgba(21,22,26,.06)', // Hairline
    bd2:  isDark ? STENCIL.bd2 : 'rgba(21,22,26,.10)', // Standard
    bd3:  isDark ? STENCIL.bd3 : 'rgba(21,22,26,.18)', // Heavy
    // Foreground
    fg1:  isDark ? STENCIL.fg1 : STENCIL.ink,
    fg2:  isDark ? STENCIL.fg2 : 'rgba(21,22,26,.72)',
    fg3:  isDark ? STENCIL.fg3 : 'rgba(21,22,26,.55)',
    fg4:  isDark ? STENCIL.fg4 : 'rgba(21,22,26,.4)',
    // Code surface (always dark — code blocks keep ink ground regardless)
    code: '#0d0e11',
    codeFg: '#e5e5e5',
    codeDim: '#5c5c5c',
    // Brand colors don't shift between themes
    signal: STENCIL.signal,
    signalTint: STENCIL.signalTint,
    signalDeep: STENCIL.signalDeep,
    ink: STENCIL.ink,
    success: STENCIL.success,
    warning: STENCIL.warning,
    error:   STENCIL.error,
    // Font stacks (passthrough)
    mono: STENCIL.mono, sans: STENCIL.sans, jbm: STENCIL.jbm,
  };
}
window.pal = pal;
