/* eslint-disable */
const S = window.STENCIL;

function App() {
  return (
    <DesignCanvas>
      {/* ── Cover sheet ────────────────────────────────────────────────── */}
      <DCSection id="cover" title="Аналитик · Stencil Redesign"
        subtitle="Полный UX/UI перевод приложения «1С Аналитик» под фирменное направление Stencil — для импорта в Claude Code.">
        <DCArtboard id="intro" label="00 · Design system" width={1440} height={1100}>
          <ScreenIntro />
        </DCArtboard>
      </DCSection>

      {/* ── Diff section ───────────────────────────────────────────────── */}
      <DCSection id="diff" title="00.5 · Diff · v0 ↦ Stencil"
        subtitle="Старый mockup объект-IDE рядом с новым Stencil-эквивалентом. Сводка снизу — чек-лист для handoff в Claude Code.">
        <DCArtboard id="before-after" label="00.5 · Before / After · ключевые компоненты" width={1440} height={1830}>
          <ScreenDiff />
        </DCArtboard>
      </DCSection>

      {/* ── App shell · dark ───────────────────────────────────────────── */}
      <DCSection id="shell-dark" title="01 · App Shell · тёмная тема"
        subtitle="Хедер 52px (брэнд-замок + channel + toolbar) · sidebar 260px · main · composer 14px.">
        <DCArtboard id="welcome-d" label="01.A · Welcome · готов отвечать" width={1440} height={900}>
          <ScreenWelcome theme="dark" />
        </DCArtboard>
        <DCArtboard id="active-d" label="01.B · Активный чат · трейс + карточки" width={1440} height={900}>
          <ScreenActiveChat theme="dark" />
        </DCArtboard>
        <DCArtboard id="error-d" label="01.C · MCP отвалился" width={1440} height={900}>
          <ScreenErrorState theme="dark" />
        </DCArtboard>
      </DCSection>

      {/* ── App shell · light ──────────────────────────────────────────── */}
      <DCSection id="shell-light" title="01·L · App Shell · светлая тема (Sand)"
        subtitle="Те же экраны, но с темой Sand — для пользователей, которые работают в светлой среде.">
        <DCArtboard id="welcome-l" label="01.A·L · Welcome · sand" width={1440} height={900}>
          <ScreenWelcome theme="light" />
        </DCArtboard>
        <DCArtboard id="active-l" label="01.B·L · Активный чат · sand" width={1440} height={900}>
          <ScreenActiveChat theme="light" />
        </DCArtboard>
        <DCArtboard id="error-l" label="01.C·L · MCP отвалился · sand" width={1440} height={900}>
          <ScreenErrorState theme="light" />
        </DCArtboard>
      </DCSection>

      {/* ── Inline cards ───────────────────────────────────────────────── */}
      <DCSection id="cards" title="02 · Inline-карточки в ответах"
        subtitle="Шесть базовых типов + Chart. KIND-чип, заголовок, мета, тело, опц. футер. Обе темы.">
        <DCArtboard id="all-cards-d" label="02.A · Полный набор · тёмная" width={1440} height={2300}>
          <ScreenCardsShowcase theme="dark" />
        </DCArtboard>
        <DCArtboard id="all-cards-l" label="02.B · Полный набор · светлая" width={1440} height={2300}>
          <ScreenCardsShowcase theme="light" />
        </DCArtboard>
      </DCSection>

      {/* ── Onboarding ─────────────────────────────────────────────────── */}
      <DCSection id="onboarding" title="03 · Onboarding wizard"
        subtitle="Четыре шага: База → Модель → Обучение → Готово. Показан шаг 02 (тест LLM пройден).">
        <DCArtboard id="onb-step2-d" label="03.A · Шаг 02 · тёмная" width={1440} height={860}>
          <ScreenOnboarding theme="dark" />
        </DCArtboard>
        <DCArtboard id="onb-step2-l" label="03.B · Шаг 02 · светлая" width={1440} height={860}>
          <ScreenOnboarding theme="light" />
        </DCArtboard>
      </DCSection>

      {/* ── Settings + Status ──────────────────────────────────────────── */}
      <DCSection id="ops" title="04 · Settings · Status"
        subtitle="Настройки (MCP / LLM / Privacy) и диагностика со сводкой и подробностями. Обе темы.">
        <DCArtboard id="settings-d" label="04.A · Settings · тёмная" width={1440} height={1400}>
          <ScreenSettings theme="dark" />
        </DCArtboard>
        <DCArtboard id="settings-l" label="04.A·L · Settings · светлая" width={1440} height={1400}>
          <ScreenSettings theme="light" />
        </DCArtboard>
        <DCArtboard id="status-d" label="04.B · Status · тёмная" width={1440} height={1500}>
          <ScreenStatus theme="dark" />
        </DCArtboard>
        <DCArtboard id="status-l" label="04.B·L · Status · светлая" width={1440} height={1500}>
          <ScreenStatus theme="light" />
        </DCArtboard>
      </DCSection>

      {/* ── Modals / overlays ──────────────────────────────────────────── */}
      <DCSection id="modals" title="05 · Модальные · оверлеи"
        subtitle="Палитра ⌘K, подтверждение execute_code, сплэш-экран. Все — в обеих темах.">
        <DCArtboard id="palette-d" label="05.A · ⌘K · тёмная" width={1440} height={700}>
          <ScreenCommandPalette theme="dark" />
        </DCArtboard>
        <DCArtboard id="palette-l" label="05.A·L · ⌘K · светлая" width={1440} height={700}>
          <ScreenCommandPalette theme="light" />
        </DCArtboard>
        <DCArtboard id="confirm-d" label="05.B · execute_code · тёмная" width={1440} height={660}>
          <ScreenConfirm theme="dark" />
        </DCArtboard>
        <DCArtboard id="confirm-l" label="05.B·L · execute_code · светлая" width={1440} height={660}>
          <ScreenConfirm theme="light" />
        </DCArtboard>
        <DCArtboard id="splash-d" label="05.C · Splash · тёмная" width={1280} height={800}>
          <ScreenSplash theme="dark" />
        </DCArtboard>
        <DCArtboard id="splash-l" label="05.C·L · Splash · светлая" width={1280} height={800}>
          <ScreenSplash theme="light" />
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
