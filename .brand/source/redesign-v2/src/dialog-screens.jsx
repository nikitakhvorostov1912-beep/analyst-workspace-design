/* eslint-disable */
const S = window.STENCIL;

/* ============================================================================
 * Dialog Surface — reusable shell for modals on backdrop
 * ============================================================================ */
function DialogSurface({ width = 720, height = 720, children, padding = 0, theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div style={{
      width: 1440, height: height + 80,
      background: 'radial-gradient(60% 50% at 50% 30%, rgba(255,106,61,.05) 0%, transparent 60%), ' + p.bg0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: p.sans, color: p.fg1,
      overflow: 'hidden',
    }}>
      <div style={{
        width, maxWidth: 'calc(100% - 80px)',
        background: p.bg1,
        border: `1px solid ${p.bd2}`,
        borderRadius: 16,
        boxShadow: p.isDark ? '0 30px 60px rgba(0,0,0,.5)' : '0 30px 60px rgba(21,22,26,.12)',
        padding,
        position: 'relative', overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

/* ============================================================================
 * Onboarding wizard — step 2 (LLM)
 * ============================================================================ */
function ScreenOnboarding({ theme = 'dark' } = {}) {
  const p = pal(theme);
  const steps = [
    { n: 1, label: 'База 1С' },
    { n: 2, label: 'Модель ИИ' },
    { n: 3, label: 'Обучение' },
    { n: 4, label: 'Готово' },
  ];
  const active = 2;

  return (
    <DialogSurface theme={theme} width={780} height={780}>
      <div style={{
        padding: '22px 28px 18px',
        borderBottom: `1px solid ${p.bd1}`,
        display: 'flex', alignItems: 'center', gap: 14,
        background: p.bg1,
      }}>
        <StGlyph size={36} mode="ink" />
        <div>
          <StLockup theme={theme} size={18} version="1.2.1" subtitle="Setup · 2 of 4" color={p.fg1} />
        </div>
        <span style={{ flex: 1 }} />
        <StChip tone="muted" theme={theme} mono>ESC · ПРОПУСТИТЬ</StChip>
      </div>

      <div style={{
        display: 'flex', gap: 0, padding: '20px 28px 8px',
        background: p.bg1,
      }}>
        {steps.map((s, i) => {
          const done = s.n < active;
          const cur = s.n === active;
          return (
            <div key={s.n} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 0, minWidth: 0 }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                width: 26, height: 26, borderRadius: 7,
                background: done ? p.success + '20' : cur ? p.signal : p.bg2,
                color: done ? p.success : cur ? p.ink : p.fg3,
                border: `1px solid ${done ? p.success + '40' : cur ? p.signal : p.bd2}`,
                fontFamily: p.jbm, fontSize: 11, fontWeight: 700,
              }}>{done ? <Icon.Check /> : s.n}</span>
              <span style={{
                marginLeft: 8, fontFamily: p.mono, fontSize: 11.5, fontWeight: 600,
                letterSpacing: '.06em', textTransform: 'uppercase',
                color: cur ? p.fg1 : done ? p.fg2 : p.fg4,
              }}>{s.label}</span>
              {i < steps.length - 1 && (
                <span style={{ flex: 1, height: 1, background: done ? p.success + '40' : p.bd2, margin: '0 12px' }} />
              )}
            </div>
          );
        })}
      </div>

      <div style={{ padding: '20px 28px 24px', background: p.bg1 }}>
        <div style={{
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.22em', textTransform: 'uppercase', color: p.fg3,
        }}>↳ Шаг 02 · подключите модель</div>
        <h2 style={{
          fontFamily: p.mono, fontWeight: 700, fontSize: 24, letterSpacing: '.01em', textTransform: 'uppercase',
          margin: '8px 0 10px', color: p.fg1,
        }}>Модель ИИ</h2>
        <p style={{
          fontFamily: p.sans, fontSize: 13.5, lineHeight: 1.55, color: p.fg2, maxWidth: 560, margin: 0,
        }}>
          Укажите OpenAI-совместимый endpoint и API-ключ. Ключ хранится только в этом браузере, никуда не уходит.
        </p>

        <div style={{ marginTop: 24, display: 'grid', gap: 16 }}>
          <Field theme={theme} label="Endpoint" hint="HTTP-адрес OpenAI-совместимого API"
            input={
              <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1 }}>https://api.mimo.example/v1</span>
                <span className="caret" style={{ display: 'inline-block', width: 6, height: 14, background: p.signal }} />
              </span>}
          />
          <Field theme={theme} label="Модель" hint="идентификатор модели у провайдера"
            input={<span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1 }}>mimo-32b</span>}
          />
          <Field theme={theme} label="API-ключ" hint="хранится в sessionStorage браузера"
            input={
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1, letterSpacing: '.1em' }}>•••••••••• ••••8a3F</span>
                <Icon.EyeOff style={{ color: p.fg3, marginLeft: 'auto' }} />
              </span>}
          />
        </div>

        <div style={{
          marginTop: 18, padding: '11px 14px',
          background: p.success + '14', border: `1px solid ${p.success}40`, borderRadius: 8,
          display: 'flex', alignItems: 'center', gap: 10,
          fontFamily: p.sans, fontSize: 13, color: p.fg1,
        }}>
          <Icon.Check style={{ color: p.success }} />
          <span style={{ fontFamily: p.mono, fontWeight: 600, color: p.success }}>Тест пройден</span>
          <span style={{ color: p.fg3 }}>· 184 мс · 32 токена ответа · подпись модели соответствует</span>
        </div>
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '16px 28px',
        borderTop: `1px solid ${p.bd1}`,
        background: p.bg0,
      }}>
        <span style={{
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.14em', textTransform: 'uppercase', color: p.fg4,
        }}>~ 90 СЕКУНД ДО ПЕРВОГО ОТВЕТА</span>
        <span style={{ flex: 1 }} />
        <StButton kind="ghost" theme={theme}>← Назад</StButton>
        <StButton kind="outline" theme={theme}>Тест</StButton>
        <StButton kind="primary" theme={theme} icon={<Icon.Arrow />}>Далее</StButton>
      </div>
    </DialogSurface>
  );
}

function Field({ label, hint, input, theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
        <span style={{
          fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.18em', textTransform: 'uppercase',
          color: p.fg2,
        }}>{label}</span>
        <span style={{ fontFamily: p.jbm, fontSize: 10, color: p.fg4, letterSpacing: '.06em' }}>· {hint}</span>
      </div>
      <div style={{
        height: 42, padding: '0 14px',
        display: 'flex', alignItems: 'center',
        background: p.isDark ? p.bg0 : '#fff',
        border: `1px solid ${p.bd2}`, borderRadius: 8,
      }}>{input}</div>
    </div>
  );
}

/* ============================================================================
 * Settings page
 * ============================================================================ */
function ScreenSettings({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <AppShellFrame theme={theme} composer={null} height={1400}>
      <div style={{ maxWidth: 940, margin: '0 auto', padding: '28px 32px 64px' }}>
        <div style={{ marginBottom: 22 }}>
          <div style={{ fontFamily: p.jbm, fontSize: 11, letterSpacing: '.2em', color: p.fg3 }}>↳ SETTINGS</div>
          <h1 style={{
            fontFamily: p.mono, fontWeight: 700, fontSize: 32, letterSpacing: '.01em', textTransform: 'uppercase',
            margin: '6px 0 10px', color: p.fg1,
          }}>Настройки</h1>
          <p style={{ fontFamily: p.sans, fontSize: 13.5, color: p.fg2, margin: 0, maxWidth: 600, lineHeight: 1.55 }}>
            Базы 1С, модель ИИ, локальные данные. Все секреты живут только в этом браузере и не уходят на сервер.
          </p>
        </div>

        <div style={{ marginTop: 28 }}>
          <StSectionHead num="01" title="Базы 1С · MCP" tag="3 подключения" color={p.fg1} dim={p.fg3} />
          <div style={{ marginTop: 16, background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12, overflow: 'hidden' }}>
            {[
              { name: 'УТ · Клиент А · ProdDB',      url: 'http://localhost:6010/mcp', kind: 'УТ',  ok: true,  rtt: '42 мс',  active: true },
              { name: 'КА · Клиент B · TestDB',      url: 'http://localhost:6011/mcp', kind: 'КА',  ok: true,  rtt: '118 мс', active: false },
              { name: 'ERP · Клиент C · Стейджинг',  url: 'http://localhost:6012/mcp', kind: 'ERP', ok: false, rtt: 'timeout', active: false },
            ].map((c, i, arr) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: 'auto 1fr auto auto', alignItems: 'center',
                gap: 16, padding: '14px 16px',
                borderBottom: i < arr.length - 1 ? `1px solid ${p.bd1}` : 'none',
              }}>
                <StGlyph size={32} mode={c.active ? 'signal' : 'ink'} />
                <div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span style={{ fontFamily: p.mono, fontSize: 14, fontWeight: 600, color: p.fg1, letterSpacing: '.02em' }}>{c.name}</span>
                    {c.active && <StChip tone="signal" theme={theme} mono>АКТИВНО</StChip>}
                  </div>
                  <div style={{
                    fontFamily: p.jbm, fontSize: 11, color: p.fg3, marginTop: 3, letterSpacing: '.04em',
                  }}>{c.url}  ·  KIND {c.kind}</div>
                </div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  fontFamily: p.jbm, fontSize: 11, letterSpacing: '.1em',
                  color: c.ok ? p.success : p.error,
                }}>
                  <StDot tone={c.ok ? 'success' : 'error'} size={8} pulse={c.ok} />
                  {c.ok ? 'LIVE' : 'OFFLINE'} · {c.rtt}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <StIconBtn theme={theme}><Icon.Refresh /></StIconBtn>
                  <StIconBtn theme={theme}><Icon.Cog /></StIconBtn>
                  <StIconBtn theme={theme}><Icon.Trash /></StIconBtn>
                </div>
              </div>
            ))}
            <div style={{ padding: 14 }}>
              <StButton kind="outline" theme={theme} icon={<Icon.Plus />}>Добавить подключение</StButton>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 32 }}>
          <StSectionHead num="02" title="Модель ИИ" tag="openai-compatible" color={p.fg1} dim={p.fg3} />
          <div style={{
            marginTop: 16, background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12,
            padding: '20px 22px',
          }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field theme={theme} label="Endpoint" hint="OpenAI-compatible API"
                input={<span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1 }}>https://api.mimo.example/v1</span>} />
              <Field theme={theme} label="Модель" hint="идентификатор у провайдера"
                input={<span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1 }}>mimo-32b</span>} />
              <Field theme={theme} label="API-ключ" hint="sessionStorage only"
                input={<span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1, letterSpacing: '.1em' }}>•••••••••• ••••8a3F</span>} />
              <Field theme={theme} label="Контекст" hint="максимум токенов на ответ"
                input={<span style={{ fontFamily: p.jbm, fontSize: 13, color: p.fg1 }}>32 768</span>} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 18 }}>
              <StButton kind="outline" theme={theme}>Тест соединения</StButton>
              <StButton kind="primary" theme={theme}>Сохранить</StButton>
              <span style={{ flex: 1 }} />
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                fontFamily: p.jbm, fontSize: 11, color: p.success, letterSpacing: '.1em',
              }}>
                <Icon.Check /> ПОСЛЕДНИЙ ТЕСТ · 184 МС · 12:14
              </span>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 32 }}>
          <StSectionHead num="03" title="Локальные данные" tag="privacy" color={p.fg1} dim={p.fg3} />
          <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <PrefRow theme={theme} label="Анонимизация чувствительных данных" desc="Контрагенты, ФИО, ИНН и e-mail заменяются на токены до отправки в LLM." on />
            <PrefRow theme={theme} label="Обучение на сессиях (Learn)" desc="Сохраняет успешные траектории локально для подсказок в будущих диалогах." on={false} />
            <PrefRow theme={theme} label="Confirm на execute_code" desc="Запрос подтверждения для опасных BSL-операций (УДАЛИТЬ, ОЧИСТИТЬ, СОХРАНИТЬ)." on />
            <PrefRow theme={theme} label="Тёмная тема" desc="Sand для светлой, Ink для тёмной — оба используют единую сигнальную палитру." on />
          </div>
          <div style={{
            marginTop: 18, padding: '16px 18px',
            border: `1px solid ${p.error}30`, background: p.error + '12', borderRadius: 12,
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <Icon.Alert style={{ color: p.error }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: p.mono, fontSize: 13, fontWeight: 600, color: p.error }}>Сброс локальных данных</div>
              <div style={{ fontFamily: p.sans, fontSize: 12.5, color: p.fg2, marginTop: 2 }}>
                Удалить все сессии, подключения, API-ключи и кеш Learn. Это действие необратимо.
              </div>
            </div>
            <StButton kind="danger" theme={theme}>Стереть всё</StButton>
          </div>
        </div>
      </div>
    </AppShellFrame>
  );
}

function PrefRow({ label, desc, on, theme = 'dark' }) {
  const p = pal(theme);
  return (
    <div style={{
      padding: '12px 14px',
      background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 10,
      display: 'flex', alignItems: 'flex-start', gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: p.mono, fontSize: 13, fontWeight: 600, color: p.fg1, letterSpacing: '.02em' }}>{label}</div>
        <div style={{ fontFamily: p.sans, fontSize: 12, color: p.fg3, marginTop: 4, lineHeight: 1.5 }}>{desc}</div>
      </div>
      <button style={{
        position: 'relative', flex: 'none',
        width: 38, height: 22, borderRadius: 999,
        background: on ? p.signal : p.bd3, border: 'none', cursor: 'pointer',
      }}>
        <span style={{
          position: 'absolute', top: 2, left: on ? 18 : 2,
          width: 18, height: 18, background: '#fff', borderRadius: '50%',
          transition: 'left .2s ease',
        }} />
      </button>
    </div>
  );
}

/* ============================================================================
 * Status / Diagnostics
 * ============================================================================ */
function ScreenStatus({ theme = 'dark' } = {}) {
  const p = pal(theme);
  const checks = [
    { id: 'backend', title: 'Сервер приложения', status: 'ok',
      sum: 'OK · ответил за 12 мс',
      fields: [
        { k: 'Версия',  v: '1.2.1' },
        { k: 'Endpoint', v: 'http://localhost:8010' },
        { k: 'Uptime',   v: '14 ч 42 мин' },
      ]},
    { id: 'mcp-1', title: 'MCP · УТ · Клиент А', status: 'ok',
      sum: 'LIVE · 42 мс · 87 tools',
      chips: ['list_metadata','execute_query','get_object','get_log','execute_code','get_session','+ 82'],
      fields: [
        { k: 'URL', v: 'http://localhost:6010/mcp' },
        { k: 'EPF version', v: '1.7.0' },
        { k: 'Last ping', v: '12:14:22' },
      ]},
    { id: 'mcp-2', title: 'MCP · КА · Клиент B', status: 'ok',
      sum: 'LIVE · 118 мс · 81 tools',
      fields: [{ k: 'URL', v: 'http://localhost:6011/mcp' }]},
    { id: 'mcp-3', title: 'MCP · ERP · Клиент C', status: 'error',
      sum: 'OFFLINE · нет ответа за 5 с',
      hint: 'Проверьте — запущен ли EPF на localhost:6012?',
      fields: [{ k: 'URL', v: 'http://localhost:6012/mcp' }, { k: 'Last seen', v: '08:42' }]},
    { id: 'llm', title: 'Модель ИИ · mimo-32b', status: 'ok',
      sum: 'Ответил за 184 мс · 32 токена',
      fields: [
        { k: 'Endpoint', v: 'https://api.mimo.example/v1' },
        { k: 'Контекст', v: '32 768 токенов' },
      ]},
    { id: 'storage', title: 'Локальное хранилище', status: 'warn',
      sum: '78 МБ · 14% от лимита',
      hint: 'Кеш Learn разрастается — можно сжать или сбросить.',
      fields: [
        { k: 'Сессий',  v: '128' },
        { k: 'Learn-эпизодов', v: '342' },
        { k: 'API-ключей', v: '2 (sessionStorage)' },
      ]},
  ];

  return (
    <AppShellFrame theme={theme} composer={null} height={1500}>
      <div style={{ maxWidth: 940, margin: '0 auto', padding: '28px 32px 64px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 22 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: p.jbm, fontSize: 11, letterSpacing: '.2em', color: p.fg3 }}>↳ STATUS · DIAGNOSTICS</div>
            <h1 style={{
              fontFamily: p.mono, fontWeight: 700, fontSize: 32, letterSpacing: '.01em', textTransform: 'uppercase',
              margin: '6px 0 6px', color: p.fg1,
            }}>Диагностика</h1>
            <p style={{ fontFamily: p.sans, fontSize: 13.5, color: p.fg2, margin: 0, maxWidth: 600, lineHeight: 1.55 }}>
              Что сейчас работает, а что — нет. Прогон делается локально, ничего не отправляется на сервер.
            </p>
          </div>
          <StButton kind="primary" theme={theme} icon={<Icon.Refresh />}>Прогнать заново</StButton>
        </div>

        <div style={{
          display: 'flex', gap: 0,
          background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12, overflow: 'hidden',
          marginBottom: 18,
        }}>
          {[
            { label: 'OK',    n: 4, tone: 'success' },
            { label: 'WARN',  n: 1, tone: 'warn' },
            { label: 'ERROR', n: 1, tone: 'error' },
            { label: 'TOTAL', n: 6, tone: 'muted' },
          ].map((c, i, arr) => (
            <div key={c.label} style={{
              flex: 1, padding: '14px 18px',
              borderRight: i < arr.length - 1 ? `1px solid ${p.bd1}` : 'none',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.2em', color: p.fg3,
              }}>
                <StDot tone={c.tone === 'muted' ? 'muted' : c.tone} size={8} />
                {c.label}
              </div>
              <div style={{ fontFamily: p.mono, fontWeight: 700, fontSize: 28, marginTop: 4, color: p.fg1 }}>{c.n}</div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {checks.map(c => <CheckCard key={c.id} theme={theme} {...c} />)}
        </div>
      </div>
    </AppShellFrame>
  );
}

function CheckCard({ title, status, sum, hint, fields, chips, theme = 'dark' }) {
  const p = pal(theme);
  const toneColor = status === 'ok' ? p.success : status === 'warn' ? p.warning : p.error;
  return (
    <div style={{
      background: p.bg1, border: `1px solid ${p.bd2}`, borderRadius: 12, overflow: 'hidden',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 32, height: 32, borderRadius: 8,
          background: toneColor + '14', border: `1px solid ${toneColor}30`, color: toneColor,
        }}>{status === 'ok' ? <Icon.Check /> : status === 'warn' ? <Icon.Alert /> : <Icon.X />}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: p.mono, fontWeight: 600, fontSize: 14, color: p.fg1, letterSpacing: '.02em' }}>{title}</div>
          <div style={{ fontFamily: p.jbm, fontSize: 11.5, color: p.fg2, marginTop: 3, letterSpacing: '.04em' }}>{sum}</div>
        </div>
        <StChip theme={theme} tone={status === 'ok' ? 'success' : status === 'warn' ? 'warn' : 'error'} mono>{status.toUpperCase()}</StChip>
      </div>
      {(fields || chips || hint) && (
        <div style={{ padding: '0 16px 14px', borderTop: `1px solid ${p.bd1}`, paddingTop: 12 }}>
          {hint && (
            <div style={{
              fontFamily: p.sans, fontSize: 12.5, color: p.fg2, marginBottom: 10, lineHeight: 1.5,
              paddingLeft: 10, borderLeft: `2px solid ${toneColor}`,
            }}>{hint}</div>
          )}
          {fields && (
            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 18px', maxWidth: 640 }}>
              {fields.map((f, i) => (
                <React.Fragment key={i}>
                  <span style={{ fontFamily: p.jbm, fontSize: 11, color: p.fg3, letterSpacing: '.06em' }}>{f.k}</span>
                  <span style={{ fontFamily: p.jbm, fontSize: 12, color: p.fg1 }}>{f.v}</span>
                </React.Fragment>
              ))}
            </div>
          )}
          {chips && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {chips.map((c, i) => (
                <span key={i} style={{
                  fontFamily: p.jbm, fontSize: 10.5, color: p.fg2, letterSpacing: '.06em',
                  padding: '3px 8px', border: `1px solid ${p.bd2}`, borderRadius: 5,
                }}>{c}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ============================================================================
 * Command palette
 * ============================================================================ */
function ScreenCommandPalette({ theme = 'dark' } = {}) {
  const p = pal(theme);
  const items = [
    { group: 'НАВИГАЦИЯ', rows: [
      { icon: <Icon.Plus />, label: 'Новый чат', hint: 'Создать пустой чат в активной базе', kbd: '⌘N' },
      { icon: <Icon.Search />, label: 'Найти в чатах', hint: 'Поиск по сообщениям и трейсам', kbd: '⌘F' },
      { icon: <Icon.Settings />, label: 'Настройки', hint: 'Базы 1С, модель, локальные данные', kbd: '⌘,' },
      { icon: <Icon.Activity />, label: 'Диагностика', hint: 'Что сейчас живо, а что — упало', kbd: '⌘D' },
    ]},
    { group: 'БАЗЫ 1С', rows: [
      { icon: <Icon.Database />, label: 'УТ · Клиент А', hint: 'localhost:6010 · live', kbd: '⌘1', active: true },
      { icon: <Icon.Database />, label: 'КА · Клиент B', hint: 'localhost:6011 · live', kbd: '⌘2' },
      { icon: <Icon.Database />, label: 'ERP · Клиент C', hint: 'localhost:6012 · offline', kbd: '⌘3', off: true },
    ]},
    { group: 'БЫСТРЫЕ ВОПРОСЫ', rows: [
      { icon: <Icon.Spark />, label: '/ Отчёт по продажам за период', hint: 'Шаблон с параметрами' },
      { icon: <Icon.Spark />, label: '/ Discovery базы — что внутри', hint: 'Сводка по объектам и регистрам' },
      { icon: <Icon.Spark />, label: '/ Explain — объяснить запрос', hint: 'Разбор BSL построчно' },
    ]},
  ];

  return (
    <DialogSurface theme={theme} width={720} height={620}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '14px 18px',
        borderBottom: `1px solid ${p.bd1}`,
        background: p.bg1,
      }}>
        <StMarker size={10} color={p.signal} />
        <span style={{ flex: 1, fontFamily: p.mono, fontSize: 16, fontWeight: 500, letterSpacing: '.02em', color: p.fg1 }}>
          разделить
        </span>
        <span className="caret" style={{ display: 'inline-block', width: 7, height: 16, background: p.signal, marginRight: 4 }} />
        <StChip tone="muted" theme={theme} mono>ESC</StChip>
      </div>

      <div style={{
        padding: '10px 0 14px', background: p.bg1, maxHeight: 540, overflow: 'auto',
      }} className="sb">
        {items.map((g, gi) => (
          <div key={gi}>
            <div style={{
              padding: '12px 18px 6px',
              fontFamily: p.jbm, fontSize: 9.5, letterSpacing: '.22em', color: p.fg4,
            }}>↳ {g.group}</div>
            {g.rows.map((r, ri) => {
              const sel = gi === 0 && ri === 0;
              return (
                <div key={ri} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  margin: '0 8px', padding: '9px 12px', borderRadius: 8,
                  background: sel ? p.signal + '14' : 'transparent',
                  borderLeft: sel ? `2px solid ${p.signal}` : '2px solid transparent',
                  color: r.off ? p.fg4 : p.fg1,
                  cursor: 'pointer',
                }}>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    width: 24, height: 24, borderRadius: 6,
                    background: sel ? p.signal + '20' : p.bg2, color: sel ? p.signal : p.fg3,
                    border: `1px solid ${p.bd2}`,
                  }}>{r.icon}</span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontFamily: p.mono, fontSize: 13, fontWeight: 600, letterSpacing: '.02em' }}>{r.label}</div>
                    <div style={{ fontFamily: p.sans, fontSize: 11.5, color: p.fg3, marginTop: 1 }}>{r.hint}</div>
                  </div>
                  {r.active && <StChip tone="signal" theme={theme} mono>АКТИВНО</StChip>}
                  {r.off && <StChip tone="error" theme={theme} mono>OFFLINE</StChip>}
                  {r.kbd && (
                    <kbd style={{
                      fontFamily: p.jbm, fontSize: 10, letterSpacing: '.1em',
                      padding: '2px 6px', color: p.fg3,
                      border: `1px solid ${p.bd2}`, borderRadius: 4,
                    }}>{r.kbd}</kbd>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      <div style={{
        padding: '10px 18px',
        borderTop: `1px solid ${p.bd1}`,
        background: p.bg0,
        display: 'flex', alignItems: 'center', gap: 16,
        fontFamily: p.jbm, fontSize: 10, letterSpacing: '.14em', textTransform: 'uppercase', color: p.fg4,
      }}>
        <span><kbd style={{ padding: '1px 5px', border: `1px solid ${p.bd2}`, borderRadius: 3 }}>↑↓</kbd> ВЫБОР</span>
        <span><kbd style={{ padding: '1px 5px', border: `1px solid ${p.bd2}`, borderRadius: 3 }}>↵</kbd> ОТКРЫТЬ</span>
        <span><kbd style={{ padding: '1px 5px', border: `1px solid ${p.bd2}`, borderRadius: 3 }}>⌘K</kbd> ЗАКРЫТЬ</span>
        <span style={{ marginLeft: 'auto' }}>12 КОМАНД · 0 РЕЗУЛЬТАТОВ</span>
      </div>
    </DialogSurface>
  );
}

/* ============================================================================
 * Confirm execute_code dialog
 * ============================================================================ */
function ScreenConfirm({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <DialogSurface theme={theme} width={560} height={580}>
      <div style={{
        padding: '22px 24px 18px',
        borderBottom: `1px solid ${p.bd1}`,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 36, height: 36, borderRadius: 9,
          background: p.warning + '20', border: `1px solid ${p.warning}40`, color: p.warning,
        }}><Icon.Alert /></span>
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: p.jbm, fontSize: 10.5, letterSpacing: '.22em', textTransform: 'uppercase', color: p.warning,
          }}>↳ EXECUTE_CODE · CONFIRMATION REQUIRED</div>
          <div style={{
            fontFamily: p.mono, fontWeight: 700, fontSize: 18, letterSpacing: '.02em', color: p.fg1,
            textTransform: 'uppercase', marginTop: 4,
          }}>Подтвердить выполнение?</div>
        </div>
      </div>

      <div style={{ padding: '18px 24px 12px' }}>
        <p style={{ fontFamily: p.sans, fontSize: 13.5, lineHeight: 1.6, color: p.fg2, margin: 0 }}>
          В коде найдены потенциально опасные конструкции — будет выполнено в живой базе{' '}
          <span style={{ fontFamily: p.jbm, color: p.fg1, fontWeight: 600 }}>УТ · Клиент А</span>.
        </p>
        <div style={{
          marginTop: 14,
          background: p.code, border: `1px solid ${p.bd2}`, borderRadius: 8,
          padding: '12px 14px', position: 'relative',
        }}>
          <span style={{
            position: 'absolute', top: 8, right: 12,
            fontFamily: p.jbm, fontSize: 9, letterSpacing: '.18em', color: '#5c5c5c',
          }}>BSL · ФРАГМЕНТ</span>
          <pre style={{
            margin: 0, fontFamily: p.jbm, fontSize: 12.5, lineHeight: 1.7, color: '#e5e5e5',
          }}>
<span style={{ color: p.signal }}>УДАЛИТЬ</span> Документ.РТУ-014826;
<span style={{ color: p.signal }}>ОЧИСТИТЬ</span> Регистр.ВзаиморасчётыКонтрагентов;</pre>
        </div>
        <div style={{
          marginTop: 12, padding: '10px 12px',
          background: p.warning + '14', border: `1px solid ${p.warning}30`, borderRadius: 8,
          display: 'flex', alignItems: 'flex-start', gap: 10,
        }}>
          <Icon.Alert style={{ color: p.warning, flex: 'none', marginTop: 2 }} />
          <div style={{ fontFamily: p.sans, fontSize: 12.5, color: p.fg2, lineHeight: 1.5 }}>
            <b style={{ color: p.warning, fontFamily: p.mono, letterSpacing: '.02em' }}>2 опасные конструкции:</b> УДАЛИТЬ, ОЧИСТИТЬ.
            Операция необратима и затронет регистры взаиморасчётов.
          </div>
        </div>

        <label style={{
          display: 'flex', alignItems: 'center', gap: 10,
          marginTop: 14, padding: '8px 0',
          fontFamily: p.sans, fontSize: 12.5, color: p.fg2,
        }}>
          <span style={{
            width: 16, height: 16, border: `1.5px solid ${p.bd3}`, borderRadius: 4,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          }} />
          Запоминать выбор для этой сессии (10 минут)
        </label>
      </div>

      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '14px 24px',
        borderTop: `1px solid ${p.bd1}`,
        background: p.bg0,
      }}>
        <StButton kind="ghost" theme={theme}>Отмена</StButton>
        <span style={{ flex: 1 }} />
        <StButton kind="outline" theme={theme} icon={<Icon.Eye />}>Сухой прогон</StButton>
        <StButton kind="primary" theme={theme} style={{ background: p.warning, borderColor: p.warning, color: p.ink }}>Выполнить</StButton>
      </div>
    </DialogSurface>
  );
}

/* ============================================================================
 * Splash screen
 * ============================================================================ */
function ScreenSplash({ theme = 'dark' } = {}) {
  const p = pal(theme);
  return (
    <div style={{
      width: 1280, height: 800,
      background: p.bg0, color: p.fg1,
      fontFamily: p.sans, position: 'relative', overflow: 'hidden',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: `linear-gradient(${p.isDark ? 'rgba(255,255,255,.04)' : 'rgba(21,22,26,.06)'} 1px, transparent 1px),
                          linear-gradient(90deg, ${p.isDark ? 'rgba(255,255,255,.04)' : 'rgba(21,22,26,.06)'} 1px, transparent 1px)`,
        backgroundSize: '32px 32px',
        WebkitMaskImage: 'radial-gradient(circle at center, rgba(0,0,0,.7), transparent 70%)',
        maskImage: 'radial-gradient(circle at center, rgba(0,0,0,.7), transparent 70%)',
      }} />
      <span aria-hidden style={{ position: 'absolute', top: 28, left: 28, width: 14, height: 14, background: p.signal, borderRadius: 2 }} />
      <span aria-hidden style={{ position: 'absolute', bottom: 28, right: 28, width: 14, height: 14, background: p.signal, borderRadius: 2 }} />

      <div style={{
        position: 'absolute', top: 28, right: 28,
        fontFamily: p.jbm, fontSize: 11, letterSpacing: '.22em', color: p.fg3,
      }}>SPLASH · 07 · ON LAUNCH</div>

      <div style={{
        position: 'absolute', bottom: 28, left: 28,
        fontFamily: p.jbm, fontSize: 11, letterSpacing: '.22em', color: p.fg3,
      }}>FF6A3D / 15161A / F3F1EC</div>

      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 32, zIndex: 1,
      }}>
        <StLockup theme={theme} size={64} version="1.2.1" subtitle="Production build · Stable" color={p.fg1} />

        <div style={{ width: 320, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
          <div style={{ width: '100%', height: 4, borderRadius: 2, background: p.isDark ? 'rgba(255,255,255,.06)' : 'rgba(21,22,26,.08)', overflow: 'hidden' }}>
            <div style={{ width: '64%', height: '100%', background: p.signal }} />
          </div>
          <div style={{
            fontFamily: p.jbm, fontSize: 11, letterSpacing: '.22em', textTransform: 'uppercase', color: p.fg3,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <StDot tone="signal" size={6} pulse />
            <span>Готовлю рабочее место · 64%</span>
            <span style={{ color: p.fg4 }}>· 3 БАЗЫ · MIMO-32B</span>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  DialogSurface, Field, PrefRow, CheckCard,
  ScreenOnboarding, ScreenSettings, ScreenStatus,
  ScreenCommandPalette, ScreenConfirm, ScreenSplash,
});
