/* eslint-disable */
const S = window.STENCIL;

/* ============================================================================
 * App Shell — header (52px) · sidebar (260px) · main · composer (optional)
 * ============================================================================ */

function Header({ theme = 'dark', channel = { name: 'УТ · Клиент А · ProdDB', kind: 'УТ', ok: true } }) {
  const isDark = theme !== 'light';
  const bg  = isDark ? S.bg1 : S.sand;
  const bd  = isDark ? S.bd1 : 'rgba(0,0,0,.08)';
  const fg2 = isDark ? S.fg2 : 'rgba(0,0,0,.6)';

  return (
    <header style={{
      gridColumn: '1 / -1', display: 'grid',
      gridTemplateColumns: '260px 1fr auto', alignItems: 'center', gap: 18,
      height: 52, padding: '0 14px',
      background: bg, borderBottom: `1px solid ${bd}`,
    }}>
      {/* Left: brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <StIconBtn theme={theme}><Icon.Panel /></StIconBtn>
        <StGlyph size={28} mode="ink" />
        <StLockup size={15} version="1.2.1" subtitle={null} theme={theme}
          color={isDark ? S.fg1 : S.ink} />
      </div>

      {/* Center: channel selector */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <ChannelSelector channel={channel} theme={theme} />
      </div>

      {/* Right: toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <StChip tone="warn" theme={theme} mono>АНОНИМ · ВКЛ</StChip>
        <StChip tone="muted" theme={theme} mono style={{ marginLeft: 4 }}>
          <StDot tone="success" size={6} /> MIMO-32B
        </StChip>
        <div style={{ width: 8 }} />
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 8, height: 30, padding: '0 10px',
          fontFamily: S.jbm, fontSize: 11, letterSpacing: '.08em',
          background: isDark ? S.bg2 : S.sand2, color: isDark ? S.fg2 : 'rgba(0,0,0,.6)',
          border: `1px solid ${isDark ? S.bd2 : 'rgba(0,0,0,.1)'}`, borderRadius: 7, cursor: 'pointer',
        }}>
          <Icon.Search /> <span>SEARCH</span>
          <kbd style={{
            fontFamily: S.jbm, fontSize: 9, letterSpacing: '.1em',
            padding: '1px 5px', border: `1px solid ${isDark ? S.bd2 : 'rgba(0,0,0,.1)'}`,
            borderRadius: 4, color: isDark ? S.fg3 : 'rgba(0,0,0,.45)',
          }}>⌘K</kbd>
        </button>
        <div style={{ width: 4 }} />
        <StIconBtn theme={theme}><Icon.Activity /></StIconBtn>
        <StIconBtn theme={theme}><Icon.HelpCircle /></StIconBtn>
        <StIconBtn theme={theme}>{isDark ? <Icon.Sun /> : <Icon.Moon />}</StIconBtn>
        <StIconBtn theme={theme}><Icon.Settings /></StIconBtn>
      </div>
    </header>
  );
}

function ChannelSelector({ channel, theme }) {
  const isDark = theme !== 'light';
  return (
    <button style={{
      display: 'inline-flex', alignItems: 'center', gap: 10, height: 32, padding: '0 12px',
      background: isDark ? S.bg2 : S.sand2,
      border: `1px solid ${isDark ? S.bd2 : 'rgba(0,0,0,.1)'}`,
      borderRadius: 8, cursor: 'pointer',
    }}>
      <Icon.Database style={{ color: S.signal }} />
      <span style={{
        fontFamily: S.jbm, fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase',
        color: isDark ? S.fg3 : 'rgba(0,0,0,.5)',
      }}>БАЗА 1С</span>
      <span style={{
        fontFamily: S.mono, fontSize: 12, fontWeight: 600,
        color: isDark ? S.fg1 : S.ink,
      }}>{channel.name}</span>
      <StDot tone={channel.ok ? 'success' : 'error'} size={7} />
      <Icon.ChevDown style={{ color: isDark ? S.fg3 : 'rgba(0,0,0,.5)' }} />
    </button>
  );
}

/* ---------- Sidebar with sessions ---------- */
function Sidebar({ theme = 'dark', sessions, activeId }) {
  const isDark = theme !== 'light';
  const bg = isDark ? S.bg0 : S.sand;
  const bd = isDark ? S.bd1 : 'rgba(0,0,0,.08)';
  return (
    <aside style={{
      background: bg, borderRight: `1px solid ${bd}`,
      display: 'flex', flexDirection: 'column', height: '100%',
    }}>
      <div style={{ padding: 12, borderBottom: `1px solid ${bd}` }}>
        <button style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          height: 36, padding: '0 12px',
          fontFamily: S.mono, fontWeight: 600, fontSize: 12, letterSpacing: '.08em', textTransform: 'uppercase',
          color: isDark ? S.fg1 : S.ink,
          background: isDark ? S.bg2 : S.sand2,
          border: `1px solid ${isDark ? S.bd2 : 'rgba(0,0,0,.08)'}`, borderRadius: 8,
          cursor: 'pointer',
        }}>
          <StMarker size={10} color={S.signal} />
          <span>Новый чат</span>
          <span style={{ marginLeft: 'auto', fontFamily: S.jbm, fontSize: 9, color: isDark ? S.fg4 : 'rgba(0,0,0,.4)', letterSpacing: '.1em' }}>⌘N</span>
        </button>
      </div>

      <div className="sb" style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
        {sessions.map((group, gi) => (
          <div key={gi} style={{ marginTop: gi === 0 ? 8 : 16 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '4px 10px 6px',
              fontFamily: S.jbm, fontSize: 9.5, letterSpacing: '.22em', textTransform: 'uppercase',
              color: isDark ? S.fg4 : 'rgba(0,0,0,.4)',
            }}>
              <span>{group.label}</span>
              <span style={{ flex: 1, height: 1, background: isDark ? S.bd1 : 'rgba(0,0,0,.06)' }} />
              <span>{String(group.items.length).padStart(2,'0')}</span>
            </div>
            {group.items.map(s => (
              <SessionRow key={s.id} session={s} active={s.id === activeId} theme={theme} />
            ))}
          </div>
        ))}
      </div>

      {/* Footer: connection mini status */}
      <div style={{
        padding: '10px 12px', borderTop: `1px solid ${bd}`,
        display: 'flex', alignItems: 'center', gap: 8,
        fontFamily: S.jbm, fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase',
        color: isDark ? S.fg3 : 'rgba(0,0,0,.55)',
      }}>
        <StDot tone="success" size={7} pulse />
        <span>MCP · 6010 · LIVE</span>
        <span style={{ marginLeft: 'auto', color: isDark ? S.fg4 : 'rgba(0,0,0,.4)' }}>42 МС</span>
      </div>
    </aside>
  );
}

function SessionRow({ session, active, theme }) {
  const isDark = theme !== 'light';
  return (
    <div style={{
      position: 'relative', padding: '8px 10px', borderRadius: 7, marginBottom: 2,
      background: active ? (isDark ? S.bg2 : S.sand2) : 'transparent',
      cursor: 'pointer',
    }}>
      {active && <span style={{
        position: 'absolute', left: 0, top: 6, bottom: 6, width: 2, background: S.signal, borderRadius: 1,
      }} />}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3,
        fontFamily: S.jbm, fontSize: 9, letterSpacing: '.16em', textTransform: 'uppercase',
        color: isDark ? S.fg4 : 'rgba(0,0,0,.4)',
      }}>
        <span>{session.id}</span>
        {session.kind && <span style={{ color: isDark ? S.fg3 : 'rgba(0,0,0,.5)' }}>· {session.kind}</span>}
        <span style={{ marginLeft: 'auto' }}>{session.time}</span>
      </div>
      <div style={{
        fontFamily: S.sans, fontSize: 13, fontWeight: 500,
        color: active ? (isDark ? S.fg1 : S.ink) : (isDark ? S.fg2 : 'rgba(0,0,0,.72)'),
        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
      }}>{session.title}</div>
    </div>
  );
}

/* ---------- Composer ---------- */
function Composer({ theme = 'dark', value = '', placeholder = 'Спросите про базу 1С — модель сама подберёт инструменты…', hint = null }) {
  const isDark = theme !== 'light';
  return (
    <div style={{
      padding: '14px 24px 22px',
      borderTop: `1px solid ${isDark ? S.bd1 : 'rgba(0,0,0,.08)'}`,
      background: isDark ? S.bg0 : S.sand,
    }}>
      <div style={{ maxWidth: 860, margin: '0 auto' }}>
        {/* slash-command pill row */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <StChip tone="signal" theme={theme} mono>/ ОТЧЁТ</StChip>
          <StChip tone="muted" theme={theme} mono>/ JOURNAL</StChip>
          <StChip tone="muted" theme={theme} mono>/ EXPLAIN</StChip>
          <StChip tone="muted" theme={theme} mono>@ ОБЪЕКТ</StChip>
          <span style={{ flex: 1 }} />
          <StChip tone="muted" theme={theme} mono>⌘↵ ОТПРАВИТЬ</StChip>
        </div>

        <div style={{
          position: 'relative',
          background: isDark ? S.bg1 : S.sand2,
          border: `1px solid ${isDark ? S.bd2 : 'rgba(0,0,0,.1)'}`,
          borderRadius: 14,
          padding: '14px 16px 12px',
          boxShadow: isDark ? '0 8px 24px rgba(0,0,0,.3)' : '0 2px 8px rgba(0,0,0,.04)',
        }}>
          {/* corner orange tick to echo brand */}
          <span aria-hidden style={{
            position: 'absolute', top: -1, left: 18, width: 22, height: 2, background: S.signal,
          }} />
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 10,
            minHeight: 36,
            fontFamily: S.sans, fontSize: 14,
            color: value ? (isDark ? S.fg1 : S.ink) : (isDark ? S.fg3 : 'rgba(0,0,0,.5)'),
          }}>
            <span style={{ flex: 1, lineHeight: 1.5, paddingTop: 2 }}>
              {value || placeholder}
              {value && <span className="caret" style={{
                display: 'inline-block', width: 7, height: 14, background: S.signal,
                marginLeft: 3, verticalAlign: 'middle',
              }} />}
            </span>
            <div style={{ display: 'flex', gap: 6, paddingTop: 2 }}>
              <StIconBtn theme={theme}><Icon.Paperclip /></StIconBtn>
              <button style={{
                width: 32, height: 32, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: value ? S.signal : (isDark ? S.bg3 : S.sand3),
                border: 'none', borderRadius: 7,
                color: value ? S.ink : (isDark ? S.fg3 : 'rgba(0,0,0,.4)'),
                cursor: 'pointer',
              }}><Icon.Send /></button>
            </div>
          </div>
        </div>

        {/* hint row */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 14, marginTop: 8,
          fontFamily: S.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase',
          color: isDark ? S.fg4 : 'rgba(0,0,0,.45)',
        }}>
          <span>{hint || 'Естественный язык · модель сама выберет MCP-инструменты'}</span>
          <span style={{ marginLeft: 'auto' }}>0 / 4 000 ТОКЕНОВ</span>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Header, Sidebar, SessionRow, ChannelSelector, Composer });
