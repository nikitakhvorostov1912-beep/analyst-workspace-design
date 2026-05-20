/* eslint-disable */
const S = window.STENCIL;

/* ============================================================================
 * Chat building blocks — all theme-aware via pal(theme).
 * ============================================================================ */

function UserMessage({ text, time = '14:32', user = 'Никита', theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
      <div style={{ maxWidth: '78%', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontFamily: p.jbm, fontSize: 10, letterSpacing: '.18em', textTransform: 'uppercase',
          color: p.fg4,
        }}>
          <span>{user}</span><span>· {time}</span>
        </div>
        <div style={{
          padding: '10px 14px',
          background: 'transparent',
          border: `1px solid ${p.bd2}`,
          borderRadius: '10px 10px 2px 10px',
          fontFamily: p.sans, fontSize: 14, lineHeight: 1.55, color: p.fg1,
        }}>{text}</div>
      </div>
    </div>
  );
}

function AssistantHeader({ tools = [], duration = '12,4 с', model = 'MIMO-32B', theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8,
      fontFamily: p.jbm, fontSize: 10, letterSpacing: '.18em', textTransform: 'uppercase',
      color: p.fg3,
    }}>
      <StGlyph size={22} mode="ink" />
      <span style={{ color: p.fg2 }}>АНАЛИТИК</span>
      <span style={{ width: 1, height: 11, background: p.bd2 }} />
      <span style={{ color: p.signal }}>{model}</span>
      <span>·</span>
      <span>{duration}</span>
      <span>·</span>
      <span>{tools.length} TOOL CALL{tools.length !== 1 ? 'S' : ''}</span>
    </div>
  );
}

function StreamingStages({ active = 2, theme = 'dark' }) {
  const p = pal(theme);
  const stages = [
    { kind: 'analyzing', label: 'Анализирую', icon: <Icon.Search /> },
    { kind: 'learn',     label: 'Ищу прошлые ответы', icon: <Icon.Book /> },
    { kind: 'tool',      label: 'Вызываю', icon: <Icon.Cog />, tool: 'execute_query' },
    { kind: 'tool_done', label: 'Получил данные', icon: <Icon.Check />, extra: '(184 мс)' },
    { kind: 'finalizing',label: 'Формирую ответ', icon: <Icon.Pen /> },
  ];

  return (
    <div style={{
      display: 'inline-flex', flexWrap: 'wrap', alignItems: 'center', gap: 4,
      padding: '8px 12px', background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 10,
      fontFamily: p.sans, fontSize: 12,
    }}>
      {stages.map((s, i) => {
        const done = i < active;
        const cur = i === active;
        const future = i > active;
        const color = done ? p.success : cur ? p.signal : p.fg4;
        const bg = done ? p.success + '20' : cur ? p.signal + '20' : 'transparent';
        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <span style={{ color: i <= active ? p.bd3 : p.bd2, fontSize: 11 }}>→</span>
            )}
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: '3px 8px', borderRadius: 5,
              background: bg, color,
              opacity: future ? 0.6 : 1,
            }}>
              <span className={cur && s.kind === 'tool' ? 'spin' : ''} style={{ display: 'inline-flex' }}>
                {done ? <Icon.Check /> : s.icon}
              </span>
              <span style={{ fontFamily: p.jbm, fontSize: 11, letterSpacing: '.06em' }}>{s.label}{cur && !s.tool ? '…' : ''}</span>
              {s.tool && <span style={{ fontFamily: p.jbm, fontSize: 11, color: p.fg1, fontWeight: 600 }}>{s.tool}</span>}
              {cur && s.kind === 'tool' && <span className="blink" style={{ display: 'inline-block', width: 5, height: 5, background: p.signal, borderRadius: '50%' }} />}
              {s.extra && <span style={{ color: p.fg3, fontFamily: p.jbm, fontSize: 11 }}>{s.extra}</span>}
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );
}

function ToolTrace({ expanded = true, theme = 'dark' }) {
  const p = pal(theme);
  const calls = [
    { name: 'list_metadata', dur: '32 мс', ok: true,
      input:  '{ "kind": "Документ" }',
      output: '46 объектов' },
    { name: 'execute_query', dur: '184 мс', ok: true,
      input:  '{ "query": "ВЫБРАТЬ Продажи… (24 строки)" }',
      output: '847 rows · 1,2 МБ' },
    { name: 'get_object',    dur: '21 мс', ok: true,
      input:  '{ "ref": "a1c9-…-014825" }',
      output: 'Документ.РТУ-014825 · 8 полей' },
  ];
  return (
    <div style={{
      marginTop: 14, background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12, overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '11px 14px', borderBottom: `1px solid ${p.bd1}`,
      }}>
        <Icon.ChevDown style={{ color: p.fg3 }} />
        <span style={{
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.18em', textTransform: 'uppercase', color: p.fg2,
        }}>TOOL TRACE · 3 ВЫЗОВА · 237 МС ОБЩИЙ</span>
        <span style={{ flex: 1 }} />
        <button style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, height: 24, padding: '0 9px',
          fontFamily: p.jbm, fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase',
          color: p.fg2, background: 'transparent',
          border: `1px solid ${p.bd2}`, borderRadius: 6, cursor: 'pointer',
        }}><Icon.Copy /> CURL</button>
      </div>
      {expanded && calls.map((c, i) => (
        <div key={i} style={{
          padding: '12px 14px',
          borderBottom: i < calls.length - 1 ? `1px solid ${p.bd1}` : 'none',
          fontFamily: p.jbm, fontSize: 11.5, lineHeight: 1.6,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Icon.Check style={{ color: p.success }} />
            <span style={{ fontWeight: 700, color: p.fg1 }}>{c.name}</span>
            <span style={{ color: p.fg3 }}>· #{i+1}</span>
            <span style={{ marginLeft: 'auto', color: p.fg3 }}>{c.dur}</span>
          </div>
          <div style={{ marginTop: 6, paddingLeft: 22 }}>
            <div style={{ color: p.fg3, letterSpacing: '.06em' }}>↳ in&nbsp;&nbsp;<span style={{ color: p.fg2 }}>{c.input}</span></div>
            <div style={{ color: p.fg3, letterSpacing: '.06em' }}>↳ out <span style={{ color: p.fg2 }}>{c.output}</span></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function AssistantMessage({ children, tools = ['list_metadata','execute_query','get_object'], duration = '12,4 с', theme = 'dark' }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <AssistantHeader tools={tools} duration={duration} theme={theme} />
      <div style={{ paddingLeft: 30 }}>
        {children}
      </div>
    </div>
  );
}

function ErrorBanner({ theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 14,
      padding: '12px 16px', margin: '14px 0',
      background: p.error + '14', border: `1px solid ${p.error}40`, borderRadius: 10,
    }}>
      <Icon.Alert style={{ color: p.error, flex: 'none' }} />
      <div style={{ flex: 1 }}>
        <div style={{
          fontFamily: p.mono, fontSize: 13, fontWeight: 600, color: p.error, letterSpacing: '.02em',
        }}>База 1С не отвечает</div>
        <div style={{ fontFamily: p.sans, fontSize: 12.5, color: p.fg2, marginTop: 2 }}>
          MCP Toolkit на <span style={{ fontFamily: p.jbm }}>http://localhost:6010/mcp</span> не ответил за 5 секунд. Проверьте, запущен ли EPF в вашей базе 1С.
        </div>
      </div>
      <StButton kind="outline" theme={theme} size="sm" icon={<Icon.Refresh />}>Повторить</StButton>
      <StButton kind="ghost" theme={theme} size="sm">Настройки →</StButton>
    </div>
  );
}

/* ============================================================================ */
function WelcomeScreen({ theme = 'dark' }) {
  const p = pal(theme);
  const examples = [
    { tag: 'METADATA', q: 'Расскажи про эту базу — какие основные документы и регистры?' },
    { tag: 'REPORT',   q: 'Покажи реализации за неделю по контрагентам, сумма и количество' },
    { tag: 'JOURNAL',  q: 'Что было сделано в базе сегодня — выведи журнал по типам событий' },
    { tag: 'OBJECT',   q: 'Найди контрагента «Северный Ветер» и покажи карточку с обороткой' },
  ];

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100%', padding: '40px 48px',
    }}>
      <div style={{ maxWidth: 720, width: '100%' }}>
        <div style={{
          position: 'relative', padding: '40px 36px 36px',
          background: p.bg1,
          border: `1px solid ${p.bd2}`,
          borderRadius: 16, overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', inset: 14,
            border: `1px dashed ${p.isDark ? p.bd2 : 'rgba(0,0,0,.18)'}`,
            pointerEvents: 'none', borderRadius: 8,
          }} />
          <span aria-hidden style={{ position: 'absolute', top: 8, left: 8, width: 14, height: 14, background: p.signal, borderRadius: 2 }} />
          <span aria-hidden style={{ position: 'absolute', bottom: 8, right: 8, width: 14, height: 14, background: p.signal, borderRadius: 2 }} />
          <div style={{
            fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.22em', textTransform: 'uppercase',
            color: p.fg3,
          }}>01 · WELCOME · WORKSPACE READY</div>

          <div style={{ marginTop: 18 }}>
            <StLockup size={42} version="1.2.1" subtitle="Production build · Stable" theme={theme} color={p.fg1} />
          </div>

          <p style={{
            marginTop: 22, maxWidth: 60 + 'ch',
            fontFamily: p.sans, fontSize: 15, lineHeight: 1.6,
            color: p.fg2,
          }}>
            Готов отвечать на вопросы по 1С. Пишите на русском —
            модель сама подберёт нужные MCP-инструменты, выполнит запросы
            и покажет ответ с таблицей, карточкой объекта или журналом событий.
          </p>

          <div style={{ display: 'flex', gap: 10, marginTop: 22 }}>
            <StButton kind="primary" theme={theme} icon={<StMarker size={10} color={p.ink} />}>Новый чат</StButton>
            <StButton kind="outline" theme={theme} icon={<Icon.Activity />}>Диагностика</StButton>
            <StButton kind="ghost" theme={theme} icon={<Icon.Book />}>О приложении</StButton>
          </div>
        </div>

        <div style={{ marginTop: 24 }}>
          <StSectionHead num="02" title="Примеры вопросов" tag="quick start" color={p.fg1} dim={p.fg3} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 14 }}>
            {examples.map((ex, i) => (
              <div key={i} style={{
                padding: '12px 14px',
                background: p.bg1,
                border: `1px solid ${p.bd2}`,
                borderRadius: 10, cursor: 'pointer',
              }}>
                <div style={{
                  fontFamily: p.jbm, fontSize: 9.5, letterSpacing: '.2em', textTransform: 'uppercase',
                  color: p.signal, marginBottom: 5,
                }}>↳ /{ex.tag}</div>
                <div style={{
                  fontFamily: p.sans, fontSize: 13.5, lineHeight: 1.5,
                  color: p.fg1,
                }}>{ex.q}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 14,
          marginTop: 22, padding: '10px 14px',
          background: 'transparent',
          border: `1px solid ${p.bd1}`,
          borderRadius: 10,
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.12em', textTransform: 'uppercase',
          color: p.fg3,
        }}>
          <StDot tone="success" size={7} pulse />
          <span>MCP 6010</span>
          <span>·</span>
          <span style={{ color: p.fg1 }}>УТ · КЛИЕНТ А</span>
          <span style={{ marginLeft: 'auto' }}>LLM · MIMO-32B</span>
          <span>·</span>
          <span style={{ color: p.success }}>STABLE</span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================================ */
const SAMPLE_SESSIONS = [
  {
    label: 'Сегодня', items: [
      { id: 'S-2147', kind: 'УТ', time: '14:32', title: 'Реализации за неделю — выгрузить контрагентов' },
      { id: 'S-2146', kind: 'УТ', time: '12:18', title: 'Почему пользователь не видит документ?' },
      { id: 'S-2145', kind: 'КА', time: '10:04', title: 'Аудит регламентных заданий' },
    ],
  },
  {
    label: 'Вчера', items: [
      { id: 'S-2142', kind: 'УТ',  time: '18:50', title: 'Долгий запрос — где узкое место' },
      { id: 'S-2141', kind: 'ERP', time: '16:11', title: 'Сравни две версии конфигурации' },
    ],
  },
  {
    label: 'На неделе', items: [
      { id: 'S-2138', kind: 'УТ',  time: 'ПН', title: 'Регистры взаиморасчётов — структура' },
      { id: 'S-2135', kind: 'УСО', time: 'ПН', title: 'Журнал · что упало в воскресенье ночью' },
      { id: 'S-2130', kind: 'КА',  time: 'ВС', title: 'Discovery новой базы — обзор объектов' },
    ],
  },
];

/* ============================================================================ */
function AppShellFrame({ children, theme = 'dark', composer = null, activeId = null, channel, height = 900 }) {
  const p = pal(theme);
  return (
    <div style={{
      width: 1440, height,
      display: 'grid',
      gridTemplateColumns: '260px 1fr',
      gridTemplateRows: '52px 1fr auto',
      background: p.bg0,
      color: p.fg1,
      fontFamily: p.sans,
      overflow: 'hidden',
    }}>
      <Header theme={theme} channel={channel || { name: 'УТ · Клиент А · ProdDB', ok: true }} />
      <Sidebar theme={theme} sessions={SAMPLE_SESSIONS} activeId={activeId} />
      <main style={{ overflow: 'auto', background: p.bg0 }} className="sb">{children}</main>
      {composer && (
        <>
          <div style={{ background: p.bg0, borderTop: `1px solid ${p.bd1}` }} />
          <div>{composer}</div>
        </>
      )}
    </div>
  );
}

/* ============================================================================
 * Screens
 * ============================================================================ */

function ScreenWelcome({ theme = 'dark' } = {}) {
  return (
    <AppShellFrame theme={theme} composer={<Composer theme={theme} />}>
      <WelcomeScreen theme={theme} />
    </AppShellFrame>
  );
}

function ScreenActiveChat({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <AppShellFrame theme={theme} activeId="S-2147" composer={<Composer theme={theme} value="Покажи топ-10 контрагентов по сумме реализации за май" />}>
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '24px 32px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18,
          padding: '10px 12px',
          border: `1px solid ${p.bd1}`, borderRadius: 10,
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.16em', textTransform: 'uppercase', color: p.fg3,
        }}>
          <StMarker size={8} color={p.signal} />
          <span style={{ color: p.fg2 }}>S-2147</span>
          <span>· УТ · Клиент А</span>
          <span style={{ width: 1, height: 11, background: p.bd2 }} />
          <span>3 сообщения · 1 трейс</span>
          <span style={{ marginLeft: 'auto', color: p.fg2 }}>Экспорт ↓ · Копировать ⌘C</span>
        </div>

        <UserMessage theme={theme} text="Какие документы реализации были на этой неделе? Покажи таблицей с суммой и проведённостью." time="14:31" />

        <AssistantMessage theme={theme} tools={['list_metadata','execute_query']} duration="9,2 с">
          <p style={{ fontFamily: p.sans, fontSize: 14.5, lineHeight: 1.7, color: p.fg1, margin: 0 }}>
            За период с <span style={{ fontFamily: p.jbm, color: p.signal }}>13.05 — 19.05.2026</span> найдено
            {' '}<span style={{ fontFamily: p.jbm, color: p.fg1, fontWeight: 600 }}>847 реализаций</span> на общую сумму
            {' '}<span style={{ fontFamily: p.jbm, color: p.fg1, fontWeight: 600 }}>14 248 920 ₽</span>. Один документ не проведён —
            показал в таблице ниже, проверьте РТУ-014826.
          </p>

          <div style={{ marginTop: 14 }}><TableCard theme={theme} /></div>
          <div style={{ marginTop: 12 }}><ToolTrace theme={theme} /></div>
        </AssistantMessage>

        <UserMessage theme={theme} text="Открой РТУ-014825 — посмотри, что там внутри" time="14:36" />

        <AssistantMessage theme={theme} tools={['get_object']} duration="1,8 с">
          <p style={{ fontFamily: p.sans, fontSize: 14.5, lineHeight: 1.65, color: p.fg1, margin: '0 0 14px 0' }}>
            Открыл документ. Контрагент скрыт под токеном (анонимизация ВКЛ) — нажмите «Раскрыть» в карточке, чтобы получить реальное значение.
          </p>
          <ObjectCard theme={theme} />
        </AssistantMessage>

        <AssistantMessage theme={theme} tools={['execute_query']} duration="…">
          <StreamingStages theme={theme} active={2} />
          <div style={{ marginTop: 12, color: p.fg3, fontFamily: p.sans, fontSize: 14 }}>
            <span className="shimmer-text">Получаю срез регистра «ПродажиОбороты» за период…</span>
          </div>
        </AssistantMessage>
      </div>
    </AppShellFrame>
  );
}

function ScreenCardsShowcase({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <AppShellFrame theme={theme} activeId="S-2147" composer={<Composer theme={theme} />} height={2300}>
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '28px 32px' }}>
        <div style={{ marginBottom: 20 }}>
          <StSectionHead num="01" title="Inline-карточки" tag="6 типов + chart" color={p.fg1} dim={p.fg3} />
        </div>

        <AssistantMessage theme={theme} tools={['execute_query x3']} duration="4,1 с">
          <p style={{ fontFamily: p.sans, fontSize: 14, lineHeight: 1.65, color: p.fg1, margin: '0 0 14px 0' }}>
            Сводка по продажам за неделю — ключевые показатели:
          </p>
          <MetricRow theme={theme} />
          <div style={{ height: 18 }} />
          <ChartCard theme={theme} />
          <div style={{ height: 18 }} />
          <ReferencesCard theme={theme} />
          <div style={{ height: 18 }} />
          <LogCard theme={theme} />
          <div style={{ height: 18 }} />
          <CodeCard theme={theme} />
        </AssistantMessage>
      </div>
    </AppShellFrame>
  );
}

function ScreenErrorState({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <AppShellFrame theme={theme} channel={{ name: 'УТ · Клиент А · ProdDB', ok: false }} composer={<Composer theme={theme} placeholder="MCP отключён — отправка недоступна" />}>
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '24px 32px' }}>
        <ErrorBanner theme={theme} />

        <UserMessage theme={theme} text="Покажи журнал событий за сегодня" time="14:32" />

        <AssistantMessage theme={theme} tools={[]} duration="—">
          <div style={{
            padding: '14px 16px',
            border: `1px dashed ${p.error}55`, borderRadius: 10,
            fontFamily: p.sans, fontSize: 13.5, color: p.fg2, lineHeight: 1.6,
          }}>
            <div style={{
              fontFamily: p.jbm, fontSize: 10, letterSpacing: '.2em', textTransform: 'uppercase',
              color: p.error, marginBottom: 6,
            }}>↳ MCP UNAVAILABLE · TOOL CALL ABORTED</div>
            Я не могу обратиться к базе — MCP-сервер не отвечает. Восстановите подключение,
            и я повторю последний запрос автоматически.
          </div>
        </AssistantMessage>
      </div>
    </AppShellFrame>
  );
}

// Back-compat: old code references ScreenLightWelcome — keep as a thin alias.
function ScreenLightWelcome() {
  return <ScreenWelcome theme="light" />;
}

Object.assign(window, {
  UserMessage, AssistantMessage, AssistantHeader,
  StreamingStages, ToolTrace, ErrorBanner, WelcomeScreen,
  AppShellFrame, SAMPLE_SESSIONS,
  ScreenWelcome, ScreenActiveChat, ScreenCardsShowcase, ScreenErrorState, ScreenLightWelcome,
});
