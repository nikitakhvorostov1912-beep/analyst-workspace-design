/* eslint-disable */
const S = window.STENCIL;

/* ============================================================================
 * Intro artboard — the "design system" cover sheet for the redesign
 * ============================================================================ */

function ScreenIntro() {
  return (
    <div style={{
      width: 1440, height: 1100,
      background: S.bg0, color: S.fg1, fontFamily: S.sans,
      padding: '48px 56px', position: 'relative', overflow: 'hidden',
    }}>
      {/* meta strip */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 36,
        paddingBottom: 28, borderBottom: `1px solid ${S.bd1}`,
      }}>
        <div>
          <div style={{ fontFamily: S.jbm, fontSize: 11, letterSpacing: '.22em', color: S.fg3 }}>
            ↳ REDESIGN · STENCIL APPLIED · 2026-05-19
          </div>
          <h1 style={{
            fontFamily: S.mono, fontWeight: 700, fontSize: 56, lineHeight: 1, letterSpacing: '-.01em',
            margin: '14px 0 16px', textTransform: 'uppercase',
          }}>
            АНАЛИТИК <span style={{ color: S.signal }}>·</span> ПОЛНЫЙ <br />UX/UI ПЕРЕВОД
          </h1>
          <p style={{
            maxWidth: '64ch', fontFamily: S.sans, fontSize: 15, lineHeight: 1.65, color: S.fg2, margin: 0,
          }}>
            Применение фирменного направления <b style={{ color: S.fg1 }}>Stencil / Mono</b> ко всем экранам
            приложения «1С Аналитик». Палитра сжата до 4 цветов, типографика — IBM Plex Mono для
            заголовков и идентификаторов, IBM Plex Sans для тела, JetBrains Mono для меток и кода.
            Сигнальный оранжевый <span style={{ fontFamily: S.jbm, color: S.signal }}>#FF6A3D</span> заменяет тёмно-синий accent,
            оставаясь единственным акцентом интерфейса.
          </p>
        </div>
        <div style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: 8,
          fontFamily: S.jbm, fontSize: 12, color: S.fg3,
        }}>
          {[
            ['проект', 'analyst-workspace-design'],
            ['версия', '1.2.1 → 1.3.0 (design)'],
            ['фронтенд', 'Next.js 15 · React 19 · Tailwind 4'],
            ['accent', '[data-accent="signal"]'],
            ['acrobat', 'IBM Plex Mono 700 · uppercase'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 7, borderBottom: `1px dashed ${S.bd1}` }}>
              <span>{k}</span>
              <span style={{ color: S.fg1 }}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SECTION — Colors */}
      <div style={{ marginTop: 32 }}>
        <StSectionHead num="01" title="Палитра" tag="signal · ink · sand · semantic" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginTop: 16 }}>
          <Swatch big bg={S.signal} fg={S.ink} name="SIGNAL" hex="#FF6A3D" usage="primary CTA · marker · accents" />
          <Swatch big bg={S.ink} fg="#fff" name="INK" hex="#15161A" usage="чёрный текст · iconography" />
          <Swatch big bg={S.sand} fg={S.ink} name="SAND" hex="#F3F1EC" usage="светлая тема · печатные" />
          <Swatch big bg={S.signalTint} fg={S.ink} name="TINT" hex="#FFB38A" usage="signal · subtle states" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8, marginTop: 14 }}>
          <Swatch bg={S.bg0} fg={S.fg1} name="BG-0" hex="#0A0A0A" />
          <Swatch bg={S.bg1} fg={S.fg1} name="BG-1" hex="#141414" />
          <Swatch bg={S.bg2} fg={S.fg1} name="BG-2" hex="#1A1A1A" />
          <Swatch bg={S.bg3} fg={S.fg1} name="BG-3" hex="#202020" />
          <Swatch bg={S.success} fg={S.ink} name="OK"  hex="#7CF0C4" />
          <Swatch bg={S.warning} fg={S.ink} name="WARN" hex="#F7C948" />
          <Swatch bg={S.error} fg={S.ink} name="ERR"  hex="#F87171" />
        </div>
      </div>

      {/* SECTION — Type */}
      <div style={{ marginTop: 36, display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 32 }}>
        <div>
          <StSectionHead num="02" title="Типографика" tag="3 family stack" />
          <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 18 }}>
            <TypeRow size={36} name="LOCKUP · MONO 700"
              sample={<StLockup size={36} version="1.2.1" subtitle={null} />} />
            <TypeRow size={28} name="H1 · MONO 700 · UPPERCASE"
              sample={<span style={{ fontFamily: S.mono, fontWeight: 700, fontSize: 28, letterSpacing: '.01em', textTransform: 'uppercase' }}>Реализации за неделю</span>} />
            <TypeRow size={18} name="H2 · MONO 600"
              sample={<span style={{ fontFamily: S.mono, fontWeight: 600, fontSize: 18, color: S.fg1 }}>Документ.РеализацияТоваровУслуг</span>} />
            <TypeRow size={14} name="BODY · IBM Plex Sans 400"
              sample={<span style={{ fontFamily: S.sans, fontSize: 14, color: S.fg1, lineHeight: 1.55 }}>За период найдено 847 реализаций на 14,2 млн ₽. Один документ не проведён.</span>} />
            <TypeRow size={11} name="LABEL · JetBrains Mono · TRACKED"
              sample={<span style={{ fontFamily: S.jbm, fontSize: 11, letterSpacing: '.18em', color: S.fg3, textTransform: 'uppercase' }}>02 · STREAMING · ACTIVE TOOL CALL</span>} />
            <TypeRow size={12} name="CODE · BSL · JetBrains Mono"
              sample={<span style={{ fontFamily: S.jbm, fontSize: 12.5, color: S.fg1 }}><span style={{ color: S.signal }}>ВЫБРАТЬ</span> Продажи.Контрагент, <span style={{ color: S.signal }}>СУММА</span>(Продажи.Сумма)</span>} />
          </div>
        </div>

        {/* SECTION — Brand motifs */}
        <div>
          <StSectionHead num="03" title="Знаки и мотивы" tag="marker · glyph · chip" />
          <div style={{
            marginTop: 18, display: 'flex', flexDirection: 'column', gap: 14,
            background: S.bg1, border: `1px solid ${S.bd2}`, borderRadius: 12, padding: '18px 18px',
          }}>
            {/* Glyph row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <StGlyph size={56} mode="ink" />
              <StGlyph size={40} mode="signal" />
              <StGlyph size={32} mode="ink" />
              <StGlyph size={24} mode="ink" />
              <span style={{ flex: 1 }} />
              <span style={{ fontFamily: S.jbm, fontSize: 10, letterSpacing: '.14em', color: S.fg3 }}>
                APP ICON · FAVICON · 128/64/32/16
              </span>
            </div>
            <div style={{ height: 1, background: S.bd1 }} />
            {/* Marker bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <StMarker size={18} />
              <StMarker size={14} />
              <StMarker size={10} />
              <StMarker size={8} />
              <span style={{ flex: 1 }} />
              <span style={{ fontFamily: S.jbm, fontSize: 10, letterSpacing: '.14em', color: S.fg3 }}>
                MARKER · ½ X-HEIGHT
              </span>
            </div>
            <div style={{ height: 1, background: S.bd1 }} />
            {/* Chip row */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <StChip tone="signal">01 · ACTIVE</StChip>
              <StChip tone="muted">DEFAULT</StChip>
              <StChip tone="success"><StDot tone="success" size={6}/> LIVE</StChip>
              <StChip tone="warn">ANON · ON</StChip>
              <StChip tone="error">OFFLINE</StChip>
              <StChip tone="solid">CTA</StChip>
            </div>
            <div style={{ height: 1, background: S.bd1 }} />
            {/* Buttons */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <StButton kind="primary" icon={<StMarker size={8} color={S.ink} />}>Новый чат</StButton>
              <StButton kind="outline">Outline</StButton>
              <StButton kind="ghost">Ghost</StButton>
              <StButton kind="secondary">Secondary</StButton>
              <StButton kind="danger">Удалить</StButton>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION — System rules */}
      <div style={{ marginTop: 36 }}>
        <StSectionHead num="04" title="Принципы" tag="bans · rituals" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginTop: 16 }}>
          {[
            { tag: 'TYPE',     ok: 'IBM Plex Mono для заголовков, идентификаторов и BSL', no: 'Inter, Roboto, системный sans' },
            { tag: 'ACCENT',   ok: 'Один сигнальный #FF6A3D на весь интерфейс',           no: 'Градиенты, второй accent, цветной CTA на CTA' },
            { tag: 'BG',      ok: 'Чистые тёмные плоскости bg-0…bg-3',                   no: 'Glassmorphism, blur, кислотные подсветки' },
            { tag: 'MOTIF',    ok: 'Маркер-квадрат как «точка данных» в каждом замке',   no: 'Декоративные иконки, эмодзи в product UI' },
          ].map((r, i) => (
            <div key={i} style={{
              padding: '14px 14px 16px',
              background: S.bg1, border: `1px solid ${S.bd2}`, borderRadius: 12,
            }}>
              <div style={{ fontFamily: S.jbm, fontSize: 10, letterSpacing: '.22em', color: S.signal }}>{r.tag}</div>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 10 }}>
                <span style={{ color: S.success, marginTop: 2 }}><Icon.Check /></span>
                <span style={{ fontFamily: S.sans, fontSize: 12.5, color: S.fg1, lineHeight: 1.5 }}>{r.ok}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 8 }}>
                <span style={{ color: S.error, marginTop: 2 }}><Icon.X /></span>
                <span style={{ fontFamily: S.sans, fontSize: 12.5, color: S.fg2, lineHeight: 1.5 }}>{r.no}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* corner brand decor */}
      <span aria-hidden style={{ position: 'absolute', top: 24, right: 24, width: 14, height: 14, background: S.signal, borderRadius: 2 }} />
      <span aria-hidden style={{ position: 'absolute', bottom: 24, right: 24, fontFamily: S.jbm, fontSize: 10, letterSpacing: '.22em', color: S.fg4 }}>STENCIL · 06 / 09 · LIVE</span>
    </div>
  );
}

function Swatch({ bg, fg, name, hex, usage, big = false }) {
  return (
    <div style={{
      background: bg, color: fg, borderRadius: big ? 10 : 8,
      padding: big ? '16px 16px 14px' : '8px 10px',
      border: `1px solid ${S.bd2}`,
      display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      minHeight: big ? 132 : 64,
    }}>
      <span style={{ fontFamily: S.jbm, fontSize: big ? 11 : 10, letterSpacing: '.16em', textTransform: 'uppercase', opacity: 0.7 }}>{name}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontFamily: S.mono, fontSize: big ? 18 : 12, fontWeight: 700, letterSpacing: '.04em' }}>{hex}</span>
      </div>
      {usage && <div style={{ fontFamily: S.sans, fontSize: 11, opacity: 0.7, lineHeight: 1.4 }}>{usage}</div>}
    </div>
  );
}

function TypeRow({ name, sample }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '200px 1fr', alignItems: 'baseline', gap: 16,
      paddingBottom: 14, borderBottom: `1px dashed ${S.bd1}`,
    }}>
      <span style={{ fontFamily: S.jbm, fontSize: 10, letterSpacing: '.18em', color: S.fg3, textTransform: 'uppercase' }}>{name}</span>
      <span>{sample}</span>
    </div>
  );
}

Object.assign(window, { ScreenIntro });
