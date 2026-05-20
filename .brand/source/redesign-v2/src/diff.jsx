/* eslint-disable */
/* ============================================================================
 * Diff · Before / After
 *
 * Recreates the key visuals from the legacy v0-object-ide mockup
 * (Tailwind, Inter, cyan/emerald/amber palette, glow shadows) so they can be
 * laid out next to their Stencil replacements.
 *
 * v0 palette (LEGACY — DO NOT REUSE elsewhere):
 *   bg     #0b0e14   surface #151a23   border #1f2533
 *   ink-0  #f1f5f9   ink-2   #94a3b8   cyan #22d3ee   emerald #10b981
 *   amber  #f59e0b   rose    #f43f5e
 * ============================================================================ */
const S = window.STENCIL;

const V0 = {
  bg:      '#0b0e14',
  bgSoft:  '#11151c',
  surf:    '#151a23',
  surfHov: '#1c2230',
  bd:      '#1f2533',
  bdStr:   '#2a3142',
  ink0:    '#f1f5f9',
  ink1:    '#cbd5e1',
  ink2:    '#94a3b8',
  ink3:    '#64748b',
  ink4:    '#475569',
  cyan:    '#22d3ee',
  emer:    '#10b981',
  amber:   '#f59e0b',
  rose:    '#f43f5e',
  viol:    '#a78bfa',
  sans:    "'Inter','system-ui',sans-serif",
  mono:    "'JetBrains Mono', monospace",
};

/* ---------- Layout helpers ---------- */
function DiffPair({ label, before, after, height = 220, beforeBg = V0.bg }) {
  return (
    <div style={{ marginBottom: 26 }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 10,
      }}>
        <span style={{
          fontFamily: S.mono, fontWeight: 600, fontSize: 13.5, letterSpacing: '.06em',
          textTransform: 'uppercase', color: S.fg1,
        }}>{label}</span>
        <span style={{ flex: 1, height: 1, background: S.bd1 }} />
        <span style={{ fontFamily: S.jbm, fontSize: 10, letterSpacing: '.18em', color: S.fg4 }}>
          BEFORE  ↦  AFTER
        </span>
      </div>
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 24px 1fr', alignItems: 'stretch', gap: 0,
      }}>
        <DiffPane tone="before" height={height} bg={beforeBg}>{before}</DiffPane>
        <ArrowCol />
        <DiffPane tone="after" height={height} bg={S.bg0}>{after}</DiffPane>
      </div>
    </div>
  );
}

function DiffPane({ children, tone, height, bg }) {
  const isBefore = tone === 'before';
  return (
    <div style={{
      position: 'relative',
      border: `1px solid ${isBefore ? '#26303f' : S.bd2}`,
      borderRadius: 10, overflow: 'hidden',
      background: bg, minHeight: height,
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, padding: '4px 9px',
        fontFamily: S.jbm, fontSize: 9, letterSpacing: '.22em',
        background: isBefore ? '#1f2533' : S.signal,
        color: isBefore ? V0.ink2 : S.ink,
        zIndex: 2,
      }}>{isBefore ? 'V0 · OBJECT-IDE' : 'STENCIL · V2'}</div>
      <div style={{ height: '100%' }}>{children}</div>
    </div>
  );
}

function ArrowCol() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: S.signal, fontFamily: S.jbm, fontSize: 14, letterSpacing: '.18em',
    }}>→</div>
  );
}

/* ============================================================================
 * V0 · re-implementations (just enough to convey the old look)
 * ============================================================================ */

function V0Header() {
  return (
    <div style={{
      height: 56, display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px',
      background: V0.bgSoft, borderBottom: `1px solid ${V0.bd}`,
      fontFamily: V0.sans, color: V0.ink0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{
          width: 30, height: 30, borderRadius: 7,
          background: 'linear-gradient(135deg, #22d3ee 0%, #06b6d4 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#0b0e14', fontFamily: V0.sans, fontWeight: 800, fontSize: 15,
          boxShadow: '0 0 0 1px rgba(34,211,238,.4), 0 0 18px -2px rgba(34,211,238,.5)',
        }}>1С</div>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Аналитик</span>
          <span style={{ fontFamily: V0.mono, fontSize: 9.5, color: V0.ink3, letterSpacing: '.04em' }}>v0.9.4 · object-ide</span>
        </div>
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginLeft: 18, padding: '6px 12px',
        background: V0.surf, borderRadius: 8, border: `1px solid ${V0.bd}`,
      }}>
        <span style={{ width: 8, height: 8, borderRadius: 4, background: V0.emer }} />
        <span style={{ fontFamily: V0.mono, fontSize: 12, color: V0.ink1 }}>УТ · Клиент А · ProdDB</span>
        <span style={{ color: V0.ink3, fontSize: 10 }}>▾</span>
      </div>
      <span style={{ flex: 1 }} />
      <div style={{
        height: 30, padding: '0 12px',
        display: 'flex', alignItems: 'center', gap: 8,
        background: V0.surf, border: `1px solid ${V0.bd}`, borderRadius: 7,
        fontFamily: V0.sans, fontSize: 12, color: V0.ink2,
      }}>
        <span style={{ width: 12, height: 12, borderRadius: 2, border: `1.5px solid ${V0.ink2}` }} />
        <span>Найти…</span>
        <span style={{ fontFamily: V0.mono, fontSize: 10, padding: '1px 5px', border: `1px solid ${V0.bd}`, borderRadius: 3, color: V0.ink3 }}>⌘K</span>
      </div>
    </div>
  );
}

function V0Welcome() {
  return (
    <div style={{
      padding: '38px 36px',
      fontFamily: V0.sans, color: V0.ink0,
      background: V0.bg,
    }}>
      <div style={{
        display: 'inline-block',
        padding: '4px 12px', borderRadius: 999, background: 'rgba(34,211,238,.1)',
        border: `1px solid rgba(34,211,238,.3)`,
        fontFamily: V0.mono, fontSize: 11, color: V0.cyan, letterSpacing: '.05em',
      }}>● workspace ready</div>
      <h1 style={{
        fontFamily: V0.sans, fontWeight: 700, fontSize: 34, lineHeight: 1.15,
        margin: '14px 0 10px', color: V0.ink0,
        background: 'linear-gradient(90deg, #22d3ee, #a78bfa)',
        WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
      }}>Готов отвечать на ваши вопросы по 1С 👋</h1>
      <p style={{ fontFamily: V0.sans, fontSize: 14, color: V0.ink2, margin: 0, maxWidth: '60ch', lineHeight: 1.6 }}>
        Спросите про объекты, журнал событий или регистры — я подключу нужные инструменты и
        вернусь с ответом. ✨
      </p>
      <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
        <button style={{
          height: 38, padding: '0 16px', borderRadius: 8,
          background: 'linear-gradient(135deg, #22d3ee 0%, #06b6d4 100%)',
          color: '#0b0e14', fontWeight: 600, fontSize: 13, border: 'none',
          boxShadow: '0 0 0 1px rgba(34,211,238,.4), 0 6px 18px -2px rgba(34,211,238,.4)',
        }}>+ Новый чат</button>
        <button style={{
          height: 38, padding: '0 16px', borderRadius: 8,
          background: V0.surf, color: V0.ink1, fontSize: 13, border: `1px solid ${V0.bd}`,
        }}>Диагностика</button>
      </div>
    </div>
  );
}

function V0Composer() {
  return (
    <div style={{ padding: '14px 20px 20px', background: V0.bg }}>
      <div style={{
        background: V0.surf, border: `1px solid ${V0.bd}`, borderRadius: 12,
        padding: 12, display: 'flex', alignItems: 'center', gap: 10,
        boxShadow: '0 0 0 1px rgba(34,211,238,.18), 0 0 24px -4px rgba(34,211,238,.15)',
      }}>
        <span style={{ flex: 1, color: V0.ink3, fontFamily: V0.sans, fontSize: 14 }}>
          Спросите про объекты, метаданные, регистры…
        </span>
        <button style={{
          width: 36, height: 36, borderRadius: 8,
          background: 'linear-gradient(135deg, #22d3ee 0%, #06b6d4 100%)',
          color: '#0b0e14', border: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        }}>➤</button>
      </div>
      <div style={{
        display: 'flex', gap: 14, marginTop: 8, fontFamily: V0.sans, fontSize: 11, color: V0.ink3,
      }}>
        <span><span style={{ color: V0.cyan }}>✨</span> модель сама подберёт MCP-инструменты</span>
        <span style={{ marginLeft: 'auto' }}>tokens 0 / 4000</span>
      </div>
    </div>
  );
}

function V0Table() {
  const rows = [
    ['РТУ-014823', 'ООО «Северный Ветер»',   '128 450 ₽', '✓'],
    ['РТУ-014824', 'ИП Кузнецов А. А.',       '  8 920 ₽', '✓'],
    ['РТУ-014826', 'ООО «Технополис»',        ' 12 040 ₽', '✗'],
    ['РТУ-014827', 'ООО «Резерв-Логистик»',  '412 880 ₽', '✓'],
  ];
  return (
    <div style={{ padding: 14, background: V0.bg, color: V0.ink0, fontFamily: V0.sans }}>
      <div style={{
        background: V0.surf, border: `1px solid ${V0.bd}`, borderRadius: 10, overflow: 'hidden',
        boxShadow: '0 0 0 1px rgba(34,211,238,.1), 0 12px 32px -16px rgba(0,0,0,.6)',
      }}>
        <div style={{
          padding: '10px 12px', borderBottom: `1px solid ${V0.bd}`,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '3px 8px', borderRadius: 5,
            background: 'rgba(34,211,238,.12)', color: V0.cyan,
            fontFamily: V0.mono, fontSize: 10, letterSpacing: '.06em',
          }}>📊 Таблица</span>
          <span style={{ fontWeight: 600, fontSize: 13 }}>Реализации товаров</span>
          <span style={{ marginLeft: 'auto', fontFamily: V0.mono, fontSize: 10.5, color: V0.ink3 }}>847 строк</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: V0.bgSoft }}>
              {['№','Контрагент','Сумма','✓'].map((h, i) => (
                <th key={i} style={{
                  textAlign: i >= 2 ? 'right' : 'left',
                  padding: '7px 12px', borderBottom: `1px solid ${V0.bd}`,
                  fontFamily: V0.sans, fontSize: 11, fontWeight: 600, color: V0.ink2,
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} style={{ borderBottom: `1px solid ${V0.bd}` }}>
                {r.map((c, ci) => (
                  <td key={ci} style={{
                    padding: '7px 12px',
                    textAlign: ci >= 2 ? 'right' : 'left',
                    fontFamily: ci === 0 || ci === 2 ? V0.mono : V0.sans,
                    color: ci === 3
                      ? (c === '✓' ? V0.emer : V0.rose)
                      : V0.ink0,
                  }}>{c}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function V0Error() {
  return (
    <div style={{ padding: 14, background: V0.bg, fontFamily: V0.sans, color: V0.ink0 }}>
      <div style={{
        padding: '14px 16px', borderRadius: 10,
        background: 'rgba(244,63,94,.08)', border: `1px solid rgba(244,63,94,.3)`,
        boxShadow: '0 0 0 1px rgba(244,63,94,.3), 0 0 16px -2px rgba(244,63,94,.15)',
        display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <span style={{
          width: 28, height: 28, borderRadius: 999,
          background: 'rgba(244,63,94,.18)', color: V0.rose,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 700,
        }}>!</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: V0.rose }}>
            Connection lost
          </div>
          <div style={{ fontSize: 12.5, color: V0.ink2, marginTop: 4, lineHeight: 1.5 }}>
            Не удалось связаться с MCP toolkit на localhost:6010. Проверьте,
            что EPF запущен и доступен. Повторить попытку?
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button style={{
              padding: '6px 12px', borderRadius: 6,
              background: V0.rose, color: '#0b0e14', border: 'none',
              fontSize: 12, fontWeight: 600,
            }}>↻ Retry</button>
            <button style={{
              padding: '6px 12px', borderRadius: 6,
              background: 'transparent', color: V0.ink1, border: `1px solid ${V0.bd}`,
              fontSize: 12,
            }}>Settings</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function V0Lockup() {
  return (
    <div style={{
      padding: '38px 28px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10,
      fontFamily: V0.sans, color: V0.ink0, background: V0.bg,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 48, height: 48, borderRadius: 12,
          background: 'linear-gradient(135deg, #22d3ee 0%, #06b6d4 50%, #a78bfa 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#0b0e14', fontWeight: 800, fontSize: 22, letterSpacing: '-.02em',
          boxShadow: '0 0 0 1px rgba(34,211,238,.4), 0 0 24px -2px rgba(34,211,238,.5)',
        }}>1С</div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{
            fontFamily: V0.sans, fontSize: 24, fontWeight: 700,
            background: 'linear-gradient(90deg, #22d3ee, #a78bfa)',
            WebkitBackgroundClip: 'text', backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>Аналитик</span>
          <span style={{ fontFamily: V0.mono, fontSize: 11, color: V0.ink3, letterSpacing: '.04em' }}>
            v0.9.4 · object-ide
          </span>
        </div>
      </div>
      <span style={{
        fontFamily: V0.mono, fontSize: 9.5, color: V0.ink4, letterSpacing: '.1em',
      }}>tailwind · inter · cyan-emerald accent stack</span>
    </div>
  );
}

/* ============================================================================
 * Stencil · ready-made "after" inserts that pair with the v0 visuals
 * ============================================================================ */

function StHeaderInsert() {
  return (
    <div style={{ background: S.bg0 }}>
      <Header theme="dark" />
    </div>
  );
}

function StWelcomeInsert() {
  return (
    <div style={{
      padding: '38px 36px', background: S.bg0,
      fontFamily: S.sans, color: S.fg1,
    }}>
      <div style={{
        fontFamily: S.jbm, fontSize: 10.5, letterSpacing: '.22em', textTransform: 'uppercase', color: S.fg3,
      }}>01 · WELCOME · WORKSPACE READY</div>
      <div style={{ marginTop: 14 }}>
        <StLockup size={32} version="1.2.1" subtitle="Production · Stable" />
      </div>
      <p style={{
        marginTop: 18, maxWidth: '60ch',
        fontFamily: S.sans, fontSize: 14, lineHeight: 1.6, color: S.fg2,
      }}>
        Готов отвечать на вопросы по 1С. Пишите на русском — модель сама подберёт
        нужные MCP-инструменты, выполнит запросы и покажет ответ с таблицей или
        карточкой объекта.
      </p>
      <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
        <StButton kind="primary" icon={<StMarker size={9} color={S.ink} />}>Новый чат</StButton>
        <StButton kind="outline">Диагностика</StButton>
      </div>
    </div>
  );
}

function StComposerInsert() {
  return (
    <div style={{ background: S.bg0 }}>
      <Composer />
    </div>
  );
}

function StTableInsert() {
  return (
    <div style={{ padding: 14, background: S.bg0 }}>
      <TableCard />
    </div>
  );
}

function StErrorInsert() {
  return (
    <div style={{ padding: 14, background: S.bg0 }}>
      <ErrorBanner />
    </div>
  );
}

function StLockupInsert() {
  return (
    <div style={{
      padding: '38px 28px', display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10,
      background: S.bg0,
    }}>
      <StLockup size={26} version="1.2.1" subtitle="PRODUCTION · STABLE" />
      <span style={{
        fontFamily: S.jbm, fontSize: 10, color: S.fg4, letterSpacing: '.16em', textTransform: 'uppercase',
      }}>IBM Plex Mono 700 · единый сигнал · ½-em маркер</span>
    </div>
  );
}

/* ============================================================================
 * Diff cheat-sheet — what changed, in words
 * ============================================================================ */
function DiffNotes() {
  const rows = [
    { dim: 'Шрифт', from: 'Inter · system-ui', to: 'IBM Plex Sans + Plex Mono + JetBrains Mono' },
    { dim: 'Заголовки', from: 'Inter 700 · gradient-text cyan→violet', to: 'Plex Mono 700 · uppercase · signal' },
    { dim: 'Accent', from: 'cyan #22d3ee · linear gradient', to: 'signal #FF6A3D · solid' },
    { dim: 'Successful tone', from: 'emerald #10b981', to: 'mint #7CF0C4' },
    { dim: 'Surface stack', from: 'navy-zinc #11151c / #151a23 / #1c2230', to: 'ink-grey #0a0a0a / #141414 / #1a1a1a' },
    { dim: 'Border', from: '#1f2533 · cyan glow rings', to: '#1f1f1f → #3a3a3a · без glow' },
    { dim: 'Lockup', from: 'логомарка-плашка «1С» + gradient-text', to: '[■ маркер] АНАЛИТИК / 1.2.1 + subtitle' },
    { dim: 'CTA', from: 'gradient cyan→teal · drop-glow shadow', to: 'signal solid · 0 shadow · tick-bar' },
    { dim: 'Эмодзи', from: '👋 ✨ 📊 ➤ в копирайтинге и чипах', to: 'убраны — только маркер + JetBrains-знаки' },
    { dim: 'Тип/мета', from: 'JetBrains Mono only · нет letter-spacing', to: 'JetBrains Mono 0.18em · uppercase · ↳ префиксы' },
    { dim: 'Светлая тема', from: 'не было', to: 'Sand #F3F1EC + Ink — toggle в header' },
  ];
  return (
    <div style={{
      marginTop: 24,
      background: S.bg1, border: `1px solid ${S.bd2}`, borderRadius: 12, overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 16px', borderBottom: `1px solid ${S.bd1}`,
        fontFamily: S.jbm, fontSize: 11, letterSpacing: '.22em', textTransform: 'uppercase', color: S.fg2,
      }}>↳ DIFF · SUMMARY · 11 ИЗМЕНЕНИЙ</div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Аспект','Было (v0 · object-ide)','Стало (Stencil v2)'].map(h => (
              <th key={h} style={{
                textAlign: 'left', padding: '10px 16px',
                fontFamily: S.jbm, fontSize: 10, letterSpacing: '.18em', textTransform: 'uppercase',
                color: S.fg3, fontWeight: 500,
                borderBottom: `1px solid ${S.bd2}`,
                background: S.bg1,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${S.bd1}` }}>
              <td style={{
                padding: '10px 16px', fontFamily: S.mono, fontSize: 12, fontWeight: 600,
                color: S.fg1, letterSpacing: '.02em', width: 180,
              }}>{r.dim}</td>
              <td style={{
                padding: '10px 16px', fontFamily: S.sans, fontSize: 12.5, color: S.fg2,
                textDecoration: 'line-through', textDecorationColor: S.bd3,
              }}>{r.from}</td>
              <td style={{
                padding: '10px 16px', fontFamily: S.sans, fontSize: 12.5, color: S.fg1,
              }}>
                <span style={{ color: S.signal, fontFamily: S.jbm, marginRight: 6 }}>↳</span>
                {r.to}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ============================================================================
 * The Diff screen — full artboard
 * ============================================================================ */
function ScreenDiff() {
  return (
    <div style={{
      width: 1440, padding: '36px 40px 48px',
      background: S.bg0, color: S.fg1, fontFamily: S.sans,
    }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{
          fontFamily: S.jbm, fontSize: 11, letterSpacing: '.22em', color: S.fg3,
        }}>↳ BEFORE / AFTER · ДЛЯ HANDOFF В CLAUDE CODE</div>
        <h1 style={{
          fontFamily: S.mono, fontWeight: 700, fontSize: 36, letterSpacing: '.01em',
          textTransform: 'uppercase', margin: '6px 0 8px',
        }}>Diff · v0 ↦ Stencil</h1>
        <p style={{ fontFamily: S.sans, fontSize: 14, color: S.fg2, margin: 0, maxWidth: '64ch', lineHeight: 1.6 }}>
          Каждая пара: слева — как было в <code style={{ fontFamily: S.jbm, color: S.fg1 }}>mockups/_legacy/v0-object-ide</code> (Inter + Tailwind + cyan/emerald),
          справа — Stencil-эквивалент. Сводка изменений в конце листа — её можно скармливать модели как чек-лист.
        </p>
      </div>

      <DiffPair label="01 · Header / app bar" height={70}
        before={<V0Header />}
        after={<StHeaderInsert />} />

      <DiffPair label="02 · Lockup / wordmark" height={170}
        before={<V0Lockup />}
        after={<StLockupInsert />} />

      <DiffPair label="03 · Welcome / hero copy" height={260}
        before={<V0Welcome />}
        after={<StWelcomeInsert />} />

      <DiffPair label="04 · Composer / prompt field" height={140}
        before={<V0Composer />}
        after={<StComposerInsert />} />

      <DiffPair label="05 · Inline · Table card" height={280}
        before={<V0Table />}
        after={<StTableInsert />} />

      <DiffPair label="06 · Error · MCP offline" height={180}
        before={<V0Error />}
        after={<StErrorInsert />} />

      <DiffNotes />
    </div>
  );
}

Object.assign(window, {
  ScreenDiff, V0, V0Header, V0Welcome, V0Composer, V0Table, V0Error, V0Lockup,
  DiffPair, DiffNotes,
});
