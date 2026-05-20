/* eslint-disable */
// Reusable Stencil primitives shared across screens.
// Names are prefixed with `St` to avoid collisions.

const S = window.STENCIL;

/* ---------- Marker — the orange square that anchors the wordmark ---------- */
function StMarker({ size = 12, color = S.signal, radius = 2, style }) {
  return (
    <span aria-hidden style={{
      display: 'inline-block', width: size, height: size,
      background: color, borderRadius: radius, flex: 'none', ...style,
    }} />
  );
}

/* ---------- Lockup: [■] АНАЛИТИК / 1.2.1 ---------- */
function StLockup({ size = 18, version = '1.2.1', subtitle = null, color = S.fg1, theme = 'dark' }) {
  const dimSlash = theme === 'dark' ? 'rgba(255,255,255,.22)' : 'rgba(0,0,0,.28)';
  const dimVer   = theme === 'dark' ? 'rgba(255,255,255,.55)' : 'rgba(0,0,0,.55)';
  const dimSub   = theme === 'dark' ? 'rgba(255,255,255,.45)' : 'rgba(0,0,0,.45)';
  const bar = Math.round(size * 0.52);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: '.28em', whiteSpace: 'nowrap',
        fontFamily: S.mono, fontWeight: 700, fontSize: size, lineHeight: 1,
        letterSpacing: '.02em', textTransform: 'uppercase', color,
      }}>
        <StMarker size={bar} style={{ marginRight: '.05em' }} />
        <span>АНАЛИТИК</span>
        {version && (
          <>
            <span style={{ color: dimSlash, fontWeight: 600, margin: '0 .05em' }}>/</span>
            <span style={{ color: dimVer, fontWeight: 500, letterSpacing: '.02em' }}>{version}</span>
          </>
        )}
      </div>
      {subtitle && (
        <div style={{
          marginTop: 6, fontFamily: S.jbm, fontWeight: 500,
          fontSize: Math.max(9, Math.round(size * 0.42)),
          letterSpacing: '.18em', textTransform: 'uppercase', color: dimSub,
        }}>{subtitle}</div>
      )}
    </div>
  );
}

/* ---------- App-icon glyph (squircle [А] with orange marker) ---------- */
function StGlyph({ size = 32, mode = 'ink' }) {
  // mode: 'ink' (black bg, white letter, orange dot)
  //       'signal' (orange bg, ink letter, ink dot)
  //       'sand' (sand bg, ink letter, orange dot)
  const radius = Math.round(size * 0.18);
  const mSize  = Math.max(3, Math.round(size * 0.14));
  const mOff   = Math.max(2, Math.round(size * 0.135));
  const fs     = Math.round(size * 0.5);
  const bg = mode === 'signal' ? S.signal : mode === 'sand' ? S.sand : S.ink;
  const fg = mode === 'signal' ? S.ink : mode === 'sand' ? S.ink : '#fff';
  const dot = mode === 'signal' ? S.ink : S.signal;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flex: 'none' }} aria-label="Аналитик">
      <rect x="0.5" y="0.5" width={size - 1} height={size - 1} rx={radius} ry={radius}
            fill={bg} stroke={mode === 'ink' ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.06)'} />
      <text x={size / 2} y={size / 2 + fs * 0.36} textAnchor="middle"
            fill={fg} fontFamily={S.mono} fontSize={fs} fontWeight="700">А</text>
      <rect x={mOff} y={mOff} width={mSize} height={mSize} rx={Math.max(1, mSize * 0.2)} fill={dot} />
    </svg>
  );
}

/* ---------- Section head: "04 · TITLE  ─────── tag" ---------- */
function StSectionHead({ num, title, tag, color = S.fg1, dim = S.fg3 }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 18 }}>
      {num && <span style={{ fontFamily: S.jbm, fontSize: 11, color: dim, letterSpacing: '.2em' }}>{num}</span>}
      <span style={{ fontFamily: S.mono, fontWeight: 600, fontSize: 14, letterSpacing: '.08em',
        textTransform: 'uppercase', color }}>{title}</span>
      <span style={{ flex: 1, height: 1, background: 'rgba(255,255,255,.07)' }} />
      {tag && <span style={{ fontFamily: S.jbm, fontSize: 10.5, color: dim, letterSpacing: '.18em',
        textTransform: 'uppercase' }}>{tag}</span>}
    </div>
  );
}

/* ---------- Chip pattern from logo sheet ---------- */
function StChip({ children, tone = 'muted', mono = true, theme = 'dark', style }) {
  const isDark = theme !== 'light';
  const colors = {
    muted:   { bg: isDark ? 'rgba(255,255,255,.02)' : 'rgba(0,0,0,.02)', bd: isDark ? S.bd2 : 'rgba(0,0,0,.1)', fg: isDark ? S.fg3 : 'rgba(0,0,0,.5)' },
    signal:  { bg: 'rgba(255,106,61,.1)',  bd: 'rgba(255,106,61,.32)', fg: S.signal },
    success: { bg: S.success + '20',       bd: S.success + '40', fg: S.success },
    warn:    { bg: S.warning + '20',       bd: S.warning + '40', fg: S.warning },
    error:   { bg: S.error + '20',         bd: S.error + '40',   fg: S.error },
    solid:   { bg: S.signal,               bd: S.signal,         fg: S.ink },
  };
  const c = colors[tone] || colors.muted;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: mono ? S.jbm : S.sans, fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase',
      padding: '4px 9px', border: `1px solid ${c.bd}`, borderRadius: 999, background: c.bg, color: c.fg,
      ...style,
    }}>{children}</span>
  );
}

/* ---------- StatusDot ---------- */
function StDot({ tone = 'success', pulse = false, size = 8 }) {
  const map = { success: S.success, warning: S.warning, error: S.error, signal: S.signal, muted: S.fg4 };
  return (
    <span aria-hidden style={{
      display: 'inline-block', width: size, height: size, borderRadius: '50%',
      background: map[tone] || S.fg4,
      boxShadow: pulse ? `0 0 0 3px ${(map[tone] || S.fg4)}24` : 'none',
    }} className={pulse ? 'pulse-dot' : ''} />
  );
}

/* ---------- Button (Stencil) ---------- */
function StButton({ kind = 'secondary', size = 'md', children, icon, mono = false, style, theme = 'dark' }) {
  const isDark = theme !== 'light';
  const SH = size === 'sm' ? 28 : size === 'lg' ? 40 : 32;
  const PX = size === 'sm' ? 10 : size === 'lg' ? 18 : 14;
  const FS = size === 'sm' ? 12 : 13;
  const palettes = {
    primary:   { bg: S.signal, bd: S.signal, fg: S.ink },
    secondary: { bg: isDark ? S.bg2 : S.sand2, bd: isDark ? S.bd2 : 'rgba(0,0,0,.1)', fg: isDark ? S.fg1 : S.ink },
    ghost:     { bg: 'transparent', bd: 'transparent', fg: isDark ? S.fg2 : 'rgba(0,0,0,.6)' },
    outline:   { bg: 'transparent', bd: isDark ? S.bd3 : 'rgba(0,0,0,.18)', fg: isDark ? S.fg1 : S.ink },
    danger:    { bg: 'transparent', bd: S.error + '40', fg: S.error },
  };
  const p = palettes[kind] || palettes.secondary;
  return (
    <button style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      height: SH, padding: `0 ${PX}px`, fontSize: FS,
      fontFamily: mono ? S.jbm : S.sans, fontWeight: 500, letterSpacing: mono ? '.05em' : 0,
      borderRadius: 8, border: `1px solid ${p.bd}`, background: p.bg, color: p.fg,
      cursor: 'pointer', whiteSpace: 'nowrap', ...style,
    }}>
      {icon}
      {children}
    </button>
  );
}

/* ---------- IconButton (square) ---------- */
function StIconBtn({ children, size = 28, theme = 'dark', active = false, style }) {
  const isDark = theme !== 'light';
  return (
    <button style={{
      width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      borderRadius: 7,
      border: `1px solid ${active ? (isDark ? S.bd3 : 'rgba(0,0,0,.18)') : 'transparent'}`,
      background: active ? (isDark ? S.bg2 : S.sand2) : 'transparent',
      color: isDark ? S.fg2 : 'rgba(0,0,0,.6)', cursor: 'pointer', ...style,
    }}>{children}</button>
  );
}

/* ---------- Tiny line-icons used everywhere ---------- */
const Icon = {
  Plus:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M12 5v14M5 12h14"/></svg>),
  Search: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>),
  Send:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>),
  Paperclip: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M21.4 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>),
  Settings: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.36.16.6.49.69.86.07.35.04.71-.09 1.05l-.04.09c-.13.34-.16.7-.09 1.05.09.37.33.7.69.86"/></svg>),
  HelpCircle: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><circle cx="12" cy="17" r=".5"/></svg>),
  Activity: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>),
  Cog:    (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="3"/><path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24"/></svg>),
  Check:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M20 6L9 17l-5-5"/></svg>),
  X:      (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M18 6L6 18M6 6l12 12"/></svg>),
  ChevDown: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="6 9 12 15 18 9"/></svg>),
  ChevRight:(p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="9 18 15 12 9 6"/></svg>),
  ChevLeft: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><polyline points="15 18 9 12 15 6"/></svg>),
  Download: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>),
  Eye:    (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>),
  EyeOff: (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>),
  Copy:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>),
  Database:(p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>),
  Code:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>),
  Trash:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>),
  Refresh:(p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>),
  Alert:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><circle cx="12" cy="17" r=".5"/></svg>),
  Sun:    (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>),
  Moon:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>),
  Book:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>),
  Panel:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></svg>),
  Pen:    (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>),
  Cog2:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>),
  Arrow:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>),
  ArrowUp:(p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>),
  Star:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>),
  Link:   (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>),
  Spark:  (p) => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>),
};

Object.assign(window, { StMarker, StLockup, StGlyph, StSectionHead, StChip, StDot, StButton, StIconBtn, Icon });
