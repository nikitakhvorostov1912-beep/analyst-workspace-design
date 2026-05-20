/* eslint-disable */
const S = window.STENCIL;

/* ============================================================================
 * Inline data cards — TableCard · ObjectCard · LogCard · MetricCard ·
 *                    ReferencesCard · CodeCard · ChartCard
 *
 * All cards accept `theme = 'dark' | 'light'` and render via pal(theme).
 * Frame:
 *   ┌── KIND chip ────────── meta ┐
 *   │ Card body                   │
 *   └── ACTIONS · footer ─────────┘
 * ============================================================================ */

function CardFrame({ kind, title, meta, footer, badge, children, accent, theme = 'dark' }) {
  const p = pal(theme);
  const ac = accent || p.signal;
  return (
    <div style={{
      background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12, overflow: 'hidden',
      fontFamily: p.sans, position: 'relative',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '11px 14px',
        borderBottom: `1px solid ${p.bd1}`,
        background: p.bg1,
      }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontFamily: p.jbm, fontSize: 10, letterSpacing: '.18em', textTransform: 'uppercase',
          color: ac,
        }}>
          <span style={{ display: 'inline-block', width: 7, height: 7, background: ac, borderRadius: 2 }} />
          <span>{kind}</span>
        </div>
        <span style={{ width: 1, height: 12, background: p.bd2 }} />
        <span style={{
          fontFamily: p.mono, fontSize: 12, fontWeight: 600, color: p.fg1, letterSpacing: '.02em',
        }}>{title}</span>
        {meta && <span style={{
          fontFamily: p.jbm, fontSize: 10.5, color: p.fg3, letterSpacing: '.06em',
        }}>· {meta}</span>}
        {badge && <span style={{ marginLeft: 'auto' }}>{badge}</span>}
      </div>
      <div>{children}</div>
      {footer && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 14px',
          borderTop: `1px solid ${p.bd1}`,
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.08em', color: p.fg3,
        }}>{footer}</div>
      )}
    </div>
  );
}

/* ============================================================================ */
function TableCard({ theme = 'dark' }) {
  const p = pal(theme);
  const cols = [
    { name: '№', type: 'Number', w: 50 },
    { name: 'Дата', type: 'Date', w: 110 },
    { name: 'Номер', type: 'String', w: 130 },
    { name: 'Контрагент', type: 'String', w: 240 },
    { name: 'Сумма', type: 'Number', w: 120 },
    { name: 'Проведён', type: 'Boolean', w: 90 },
  ];
  const rows = [
    [148, '19.05.2026', 'РТУ-014823', 'ООО «Северный Ветер»',         '128 450,00', true],
    [149, '19.05.2026', 'РТУ-014824', 'ИП Кузнецов А. А.',            '   8 920,00', true],
    [150, '18.05.2026', 'РТУ-014825', '⟨ANON#k4f2⟩',                  '  64 100,00', true],
    [151, '18.05.2026', 'РТУ-014826', 'ООО «Технополис»',             '  12 040,00', false],
    [152, '17.05.2026', 'РТУ-014827', 'ООО «Резерв-Логистик»',        ' 412 880,00', true],
    [153, '17.05.2026', 'РТУ-014828', '⟨ANON#a1c9⟩',                  '   1 950,00', true],
    [154, '17.05.2026', 'РТУ-014829', 'ООО «Терра-Снаб»',             '  88 000,00', true],
  ];

  return (
    <CardFrame theme={theme} kind="TABLE" title="Реализации товаров за неделю"
      meta="847 строк · 124 мс"
      badge={
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, height: 26, padding: '0 10px',
          fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase',
          color: p.fg2, background: 'transparent',
          border: `1px solid ${p.bd2}`, borderRadius: 6, cursor: 'pointer',
        }}><Icon.Download /> CSV</button>
      }
      footer={
        <>
          <Icon.Eye style={{ color: p.warning }} />
          <span style={{ color: p.warning }}>Раскрыть реальные значения · 2 токена</span>
          <span style={{ marginLeft: 'auto' }}>СТР. 1 / 17</span>
          <button style={{ width: 22, height: 22, border: `1px solid ${p.bd2}`, borderRadius: 4, background: 'transparent', color: p.fg3, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}><Icon.ChevLeft /></button>
          <button style={{ width: 22, height: 22, border: `1px solid ${p.bd2}`, borderRadius: 4, background: 'transparent', color: p.fg2, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}><Icon.ChevRight /></button>
        </>
      }
    >
      <div style={{ overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {cols.map(c => (
                <th key={c.name} style={{
                  textAlign: c.type === 'Number' ? 'right' : 'left',
                  fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase',
                  fontWeight: 500, color: p.fg3,
                  padding: '8px 12px', borderBottom: `1px solid ${p.bd2}`,
                  whiteSpace: 'nowrap', background: p.bg1,
                }}>{c.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} style={{ borderBottom: `1px solid ${p.bd1}` }}>
                {r.map((cell, ci) => {
                  const numeric = cols[ci].type === 'Number';
                  const anon = typeof cell === 'string' && cell.startsWith('⟨ANON');
                  return (
                    <td key={ci} style={{
                      padding: '8px 12px',
                      fontFamily: numeric || anon ? p.jbm : p.sans,
                      fontSize: 12.5,
                      color: p.fg1,
                      textAlign: numeric ? 'right' : 'left',
                      whiteSpace: 'nowrap',
                    }}>
                      {typeof cell === 'boolean'
                        ? (cell ? <span style={{ color: p.success }}>✓</span> : <span style={{ color: p.fg3 }}>✗</span>)
                        : anon
                          ? <span style={{
                              background: p.warning + '20', color: p.warning,
                              border: `1px solid ${p.warning}40`, borderRadius: 3,
                              padding: '0 5px', fontSize: 11.5,
                            }}>{cell}</span>
                          : cell}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CardFrame>
  );
}

/* ============================================================================ */
function ObjectCard({ theme = 'dark' }) {
  const p = pal(theme);
  const fields = [
    { k: 'Номер',         v: 'РТУ-014825' },
    { k: 'Дата',          v: '18.05.2026 14:32:17' },
    { k: 'Контрагент',    v: '⟨ANON#k4f2⟩', anon: true },
    { k: 'Организация',   v: 'ООО «Аналитик Демо»' },
    { k: 'Склад',         v: 'Основной склад' },
    { k: 'Сумма',         v: '64 100,00 ₽', mono: true },
    { k: 'Проведён',      v: 'Да', tone: 'success' },
    { k: 'Ответственный', v: 'Хворостов Н. С.' },
  ];
  return (
    <CardFrame theme={theme} kind="OBJECT" title="Документ.РеализацияТоваровУслуг" meta="ref: a1c9-…-014825">
      <div style={{ padding: '14px 16px 6px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 18, rowGap: 8 }}>
          {fields.map((f, i) => (
            <React.Fragment key={i}>
              <span style={{
                fontFamily: p.jbm, fontSize: 11, letterSpacing: '.06em', color: p.fg3,
                whiteSpace: 'nowrap',
              }}>{f.k}</span>
              <span style={{
                fontFamily: f.mono ? p.jbm : p.sans, fontSize: 13,
                color: f.tone === 'success' ? p.success : p.fg1,
                fontWeight: 500,
              }}>
                {f.anon ? (
                  <span style={{ background: p.warning + '20', color: p.warning, border: `1px solid ${p.warning}40`, borderRadius: 3, padding: '0 5px', fontFamily: p.jbm, fontSize: 12 }}>{f.v}</span>
                ) : f.v}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      <details open style={{ borderTop: `1px solid ${p.bd1}` }}>
        <summary style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 16px', cursor: 'pointer', listStyle: 'none',
        }}>
          <span style={{
            fontFamily: p.jbm, fontSize: 11, letterSpacing: '.14em', textTransform: 'uppercase', color: p.fg2,
          }}>↳ ТАБЛИЧНАЯ ЧАСТЬ · ТОВАРЫ</span>
          <span style={{ fontFamily: p.jbm, fontSize: 11, color: p.fg3 }}>3 СТРОКИ</span>
        </summary>
        <div style={{ padding: '0 16px 14px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                {['Номенклатура','Кол.','Цена','Сумма'].map(h => (
                  <th key={h} style={{
                    textAlign: h === 'Кол.' || h === 'Цена' || h === 'Сумма' ? 'right' : 'left',
                    fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase',
                    color: p.fg3, padding: '6px 8px', borderBottom: `1px solid ${p.bd2}`,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['Услуга по адаптации',  '1',  '32 050,00', '32 050,00'],
                ['Услуга консультации',  '1',  '24 050,00', '24 050,00'],
                ['Услуга поддержки',     '1',  '  8 000,00', '  8 000,00'],
              ].map((row, ri) => (
                <tr key={ri} style={{ borderBottom: `1px solid ${p.bd1}` }}>
                  {row.map((c, ci) => (
                    <td key={ci} style={{
                      padding: '6px 8px',
                      fontFamily: ci > 0 ? p.jbm : p.sans,
                      textAlign: ci > 0 ? 'right' : 'left', color: p.fg1,
                    }}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </CardFrame>
  );
}

/* ============================================================================ */
function LogCard({ theme = 'dark' }) {
  const p = pal(theme);
  const events = [
    { lvl: 'INFO',  t: '14:32:17.184', msg: 'Документ РТУ-014825 проведён',         meta: 'event=Документ.Проведение · user=admin' },
    { lvl: 'WARN',  t: '14:31:42.910', msg: 'Долгое выполнение запроса (812 мс)',  meta: 'event=Запрос · object=Регистр.Продажи' },
    { lvl: 'INFO',  t: '14:30:15.022', msg: 'Регламент «Списание затрат» завершён',meta: 'event=Регламент · duration=4.2с' },
    { lvl: 'ERROR',t: '14:28:01.553', msg: 'Тайм-аут при обращении к веб-сервису', meta: 'event=Внешний.HTTP · code=504' },
    { lvl: 'INFO', t: '14:27:33.018',  msg: 'Пользователь admin · вход',           meta: 'event=Безопасность.Авторизация' },
    { lvl: 'INFO', t: '14:26:50.001',  msg: 'Запуск регламента «Свёртка реестра»', meta: 'event=Регламент · start' },
  ];
  const lvlColor = { INFO: p.fg2, WARN: p.warning, ERROR: p.error };
  const lvlBg    = { INFO: p.bd1, WARN: p.warning + '20', ERROR: p.error + '20' };

  return (
    <CardFrame theme={theme} kind="LOG" title="Журнал регистрации"
      meta="2 026-05-19 · 6 событий · stream"
      footer={<>
        <StDot tone="success" size={6} pulse />
        <span>LIVE · последнее событие 12 С НАЗАД</span>
        <span style={{ marginLeft: 'auto' }}>ЗАГРУЗИТЬ ЕЩЁ 50 →</span>
      </>}
    >
      <div style={{ fontFamily: p.jbm, fontSize: 11.5, lineHeight: 1.65 }}>
        {events.map((e, i) => (
          <div key={i} style={{
            display: 'grid',
            gridTemplateColumns: '60px 110px 1fr',
            gap: 12, padding: '8px 14px',
            borderBottom: `1px solid ${p.bd1}`,
            background: i === 3 ? p.error + '10' : 'transparent',
          }}>
            <span style={{
              alignSelf: 'start', justifySelf: 'start',
              padding: '1px 6px', borderRadius: 3,
              background: lvlBg[e.lvl], color: lvlColor[e.lvl],
              fontSize: 10, letterSpacing: '.14em', fontWeight: 600,
            }}>{e.lvl}</span>
            <span style={{ color: p.fg3 }}>{e.t}</span>
            <div style={{ minWidth: 0 }}>
              <div style={{ color: p.fg1, fontFamily: p.sans, fontSize: 12.5 }}>{e.msg}</div>
              <div style={{ color: p.fg4, fontSize: 10.5, marginTop: 2, letterSpacing: '.04em' }}>{e.meta}</div>
            </div>
          </div>
        ))}
      </div>
    </CardFrame>
  );
}

/* ============================================================================ */
function MetricCard({ value, label, unit, delta, sparkline, theme = 'dark' }) {
  const p = pal(theme);
  const up = delta && delta.dir === 'up';
  const down = delta && delta.dir === 'down';
  const dCol = up ? p.success : down ? p.error : p.fg3;

  return (
    <div style={{
      background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12,
      padding: '16px 18px', minWidth: 220, flex: 1, position: 'relative', overflow: 'hidden',
    }}>
      <span aria-hidden style={{
        position: 'absolute', top: 0, left: 18, width: 22, height: 2, background: p.signal,
      }} />
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
        fontFamily: p.jbm, fontSize: 10, letterSpacing: '.16em', textTransform: 'uppercase', color: p.fg3,
      }}>
        <StMarker size={6} color={p.signal} />
        <span>METRIC</span>
        <span>· {label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{
          fontFamily: p.mono, fontWeight: 700, fontSize: 36, letterSpacing: '-.02em', color: p.fg1,
        }}>{value}</span>
        {unit && <span style={{ fontFamily: p.sans, fontSize: 16, color: p.fg3 }}>{unit}</span>}
      </div>
      {delta && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5, marginTop: 4,
          fontFamily: p.jbm, fontSize: 11, color: dCol,
        }}>
          {up && <Icon.ArrowUp />}
          {down && <Icon.ArrowUp style={{ transform: 'rotate(180deg)' }} />}
          <span>{delta.text}</span>
          <span style={{ color: p.fg4 }}>· {delta.window}</span>
        </div>
      )}
      {sparkline && (
        <svg viewBox="0 0 200 36" width="100%" height={36} style={{ marginTop: 12, display: 'block' }}>
          <polyline
            fill="none" stroke={p.signal} strokeWidth="1.5"
            points={sparkline.map((y, x) => `${(x / (sparkline.length - 1)) * 200},${36 - y * 36}`).join(' ')}
          />
          <polyline
            fill={p.signal + '20'} stroke="none"
            points={`0,36 ${sparkline.map((y, x) => `${(x / (sparkline.length - 1)) * 200},${36 - y * 36}`).join(' ')} 200,36`}
          />
        </svg>
      )}
    </div>
  );
}

/* ============================================================================ */
function ReferencesCard({ theme = 'dark' }) {
  const p = pal(theme);
  const refs = [
    { kind: 'Объект', path: 'Документ.РеализацияТоваровУслуг.РТУ-014825', hint: 'ссылка на проведённый документ' },
    { kind: 'Регистр', path: 'РегистрНакопления.ПродажиОбороты', hint: 'источник суммы за период' },
    { kind: 'Запрос', path: 'Запрос: "ВЫБРАТЬ ИЗ ПродажиОбороты…"', hint: 'BSL · 24 строки' },
    { kind: 'Документ', path: 'docs/RTU-014825.pdf', hint: 'печатная форма документа · 64 КБ' },
  ];
  return (
    <CardFrame theme={theme} kind="REFERENCES" title="Связанные объекты и материалы" meta="4 ссылки">
      <div style={{ padding: '6px 0' }}>
        {refs.map((r, i) => (
          <a key={i} style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '10px 16px',
            borderBottom: i < refs.length - 1 ? `1px solid ${p.bd1}` : 'none',
            cursor: 'pointer', textDecoration: 'none',
          }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 28, height: 28, border: `1px solid ${p.bd2}`, borderRadius: 6,
              color: p.signal,
            }}><Icon.Link /></span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{
                  fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: p.signal,
                }}>{r.kind}</span>
                <span style={{ fontFamily: p.mono, fontSize: 12.5, color: p.fg1, fontWeight: 500 }}>{r.path}</span>
              </div>
              <div style={{ fontFamily: p.sans, fontSize: 12, color: p.fg3, marginTop: 2 }}>{r.hint}</div>
            </div>
            <Icon.ChevRight style={{ color: p.fg4 }} />
          </a>
        ))}
      </div>
    </CardFrame>
  );
}

/* ============================================================================ */
function CodeCard({ theme = 'dark' }) {
  const p = pal(theme);
  // Code surface stays dark in both themes — keeps Stencil-Mono identity.
  const tok = (t, c) => <span style={{ color: c }}>{t}</span>;
  const KW = p.signal, NUM = '#c2c2a0', CMT = '#7a7a7a', ID = '#e5e5e5';
  return (
    <CardFrame theme={theme} kind="CODE" title="Запрос · Продажи за период"
      meta="BSL · 18 строк"
      badge={
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, height: 26, padding: '0 10px',
          fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase',
          color: p.fg2, background: 'transparent',
          border: `1px solid ${p.bd2}`, borderRadius: 6, cursor: 'pointer',
        }}><Icon.Copy /> COPY</button>
      }
      footer={<>
        <Icon.Alert style={{ color: p.warning }} />
        <span style={{ color: p.warning }}>execute_code требует подтверждения</span>
        <span style={{ marginLeft: 'auto' }}>
          <StButton kind="primary" size="sm">Выполнить</StButton>
        </span>
      </>}
    >
      <div style={{
        background: p.code, padding: '14px 16px',
        fontFamily: p.jbm, fontSize: 12.5, lineHeight: 1.7,
        color: ID, whiteSpace: 'pre',
        position: 'relative',
      }}>
        <span style={{
          position: 'absolute', top: 8, right: 12,
          fontFamily: p.jbm, fontSize: 9, letterSpacing: '.18em', color: '#5c5c5c',
        }}>BSL · ЗАПРОС</span>
{tok('// Сумма реализаций по контрагентам за май 2026', CMT)}{`\n`}
{tok('ВЫБРАТЬ', KW)}{`\n  `}
{tok('Продажи.Контрагент', ID)}{tok(' КАК ', KW)}{tok('Клиент,', ID)}{`\n  `}
{tok('СУММА(Продажи.Сумма)', ID)}{tok(' КАК ', KW)}{tok('Итог', ID)}{`\n`}
{tok('ИЗ', KW)}{`\n  `}
{tok('РегистрНакопления.ПродажиОбороты', ID)}{tok('(', ID)}{`\n    `}
{tok('&НачалоПериода,', ID)}{`\n    `}
{tok('&КонецПериода,', ID)}{`\n    `}
{tok('Авто,', NUM)}{`\n    `}
{tok('Организация = &Организация', ID)}{tok(')', ID)}{tok(' КАК ', KW)}{tok('Продажи', ID)}{`\n`}
{tok('СГРУППИРОВАТЬ ПО', KW)}{`\n  `}
{tok('Продажи.Контрагент', ID)}{`\n`}
{tok('УПОРЯДОЧИТЬ ПО', KW)}{`\n  `}
{tok('Итог УБЫВ', ID)}
      </div>
    </CardFrame>
  );
}

/* ============================================================================ */
function ChartCard({ theme = 'dark' }) {
  const p = pal(theme);
  const bars = [62, 88, 74, 95, 110, 82, 138, 124, 156, 132, 168, 148, 192, 174];
  const max = Math.max(...bars);
  return (
    <CardFrame theme={theme} kind="CHART" title="Динамика продаж · по дням"
      meta="2 026-05-06 → 2 026-05-19">
      <div style={{ padding: '18px 18px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 140 }}>
          {bars.map((v, i) => {
            const h = (v / max) * 130;
            const last = i === bars.length - 1;
            return (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: '100%',
                  height: h,
                  background: last ? p.signal : p.signal + '70',
                  borderRadius: '3px 3px 0 0',
                }} />
                <span style={{ fontFamily: p.jbm, fontSize: 9, color: p.fg4 }}>{String(6+i).padStart(2,'0')}</span>
              </div>
            );
          })}
        </div>
        <div style={{
          display: 'flex', gap: 16, marginTop: 10,
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.06em', color: p.fg3,
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <StMarker size={8} color={p.signal} /> Реализации (₽)
          </span>
          <span>· пик 19.05 · 192 480 ₽</span>
          <span style={{ marginLeft: 'auto', color: p.success }}>↗ +24,8% к предыдущей неделе</span>
        </div>
      </div>
    </CardFrame>
  );
}

/* ============================================================================ */
function MetricRow({ theme = 'dark' }) {
  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <MetricCard theme={theme}
        label="Реализаций за неделю"
        value="847"
        delta={{ dir: 'up', text: '+24,8%', window: 'к прошлой неделе' }}
        sparkline={[.3,.45,.4,.55,.6,.5,.7,.65,.78,.72,.84,.8,.95,.9]}
      />
      <MetricCard theme={theme}
        label="Сумма к получению"
        value="14,2"
        unit="млн ₽"
        delta={{ dir: 'up', text: '+1,8 млн', window: 'за 7 дней' }}
        sparkline={[.5,.55,.5,.6,.62,.66,.7,.72,.78,.8,.84,.86,.92,.94]}
      />
      <MetricCard theme={theme}
        label="Незакрытых ошибок"
        value="12"
        delta={{ dir: 'down', text: '−3', window: 'за 7 дней' }}
        sparkline={[.9,.85,.8,.82,.78,.7,.65,.66,.6,.58,.5,.45,.4,.38]}
      />
    </div>
  );
}

Object.assign(window, { CardFrame, TableCard, ObjectCard, LogCard, MetricCard, MetricRow, ReferencesCard, CodeCard, ChartCard });
