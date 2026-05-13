---
phase: 01-foundation
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/package.json
  - frontend/pnpm-workspace.yaml
  - frontend/tsconfig.json
  - frontend/next.config.ts
  - frontend/postcss.config.mjs
  - frontend/tailwind.config.ts
  - frontend/.env.local.example
  - frontend/.eslintrc.json
  - frontend/components.json
  - frontend/app/layout.tsx
  - frontend/app/page.tsx
  - frontend/app/globals.css
  - frontend/app/settings/page.tsx
  - frontend/components/shell/AppShell.tsx
  - frontend/components/shell/Header.tsx
  - frontend/components/shell/Sidebar.tsx
  - frontend/components/shell/ChannelSelector.tsx
  - frontend/components/shell/ModelBadge.tsx
  - frontend/components/chat/Thread.tsx
  - frontend/components/chat/Message.tsx
  - frontend/components/chat/Input.tsx
  - frontend/components/ui/button.tsx
  - frontend/components/ui/input.tsx
  - frontend/components/ui/scroll-area.tsx
  - frontend/components/ui/select.tsx
  - frontend/lib/api.ts
  - frontend/lib/sse.ts
  - frontend/lib/storage.ts
  - frontend/lib/types.ts
  - frontend/lib/utils.ts
autonomous: true
requirements:
  - FR-1
  - FR-2
  - FR-7
  - FR-9
  - FR-10
  - NFR-15
  - NFR-16
  - NFR-19
  - IR-6
must_haves:
  truths:
    - "pnpm dev поднимает Next.js 15 на http://localhost:3010 и главная страница рендерится"
    - "Глаза видят AppShell: header сверху (с channel selector + model badge), sidebar слева (заглушка списка сессий), main по центру (dummy chat thread), input снизу"
    - "Тёмная тема активна по умолчанию (class=\"dark\" на <html>), Tailwind dark: классы рендерятся; нет переключателя light"
    - "Шрифт основного текста — IBM Plex Sans, моноширинного — IBM Plex Mono (импортируются через next/font/google или локально)"
    - "Весь UI-текст на русском (заголовки header, plaeholder в input, тексты sidebar, settings page)"
    - "lib/api.ts экспортирует типизированные функции postChat (SSE), pingMCP, getHealth — без any в сигнатурах"
    - "lib/sse.ts парсит event-stream и эмиттит типизированные события {event: 'status'|'delta'|'tool_call'|...|'done', data: ...}"
    - "lib/storage.ts читает/пишет в localStorage LLM API key + endpoint + model + список MCP connections; key в backend НЕ отправляется через body, только через header X-LLM-API-Key"
    - "Empty state на главной: hero + кнопка «Настроить подключение» → /settings"
    - "TypeScript strict mode, tsc проходит без ошибок, eslint clean"
  artifacts:
    - path: "frontend/package.json"
      provides: "Зависимости: next@15, react@19, tailwindcss@4, shadcn/ui деривативы, IBM Plex шрифты; scripts: dev, build, lint, type-check"
      contains: "\"next\":"
    - path: "frontend/tailwind.config.ts"
      provides: "Tailwind 4 конфиг с darkMode='class', содержит токены IBM Plex, цветовая палитра (dark by default)"
      exports: ["default config"]
    - path: "frontend/app/layout.tsx"
      provides: "Root layout: html lang='ru' className='dark', font variables, <AppShell>{children}</AppShell>"
      exports: ["default metadata", "default RootLayout"]
    - path: "frontend/app/page.tsx"
      provides: "Главная страница чата: dummy ChatThread + ChatInput. Empty state когда нет сессий"
      exports: ["default HomePage"]
    - path: "frontend/components/shell/AppShell.tsx"
      provides: "Сетка layout: header (sticky), sidebar (260px), main (flex-1), bottom input area"
      exports: ["AppShell"]
    - path: "frontend/components/shell/Header.tsx"
      provides: "Шапка: лого '1С Аналитик' слева, ChannelSelector в центре, ModelBadge + ссылка Settings справа"
      exports: ["Header"]
    - path: "frontend/components/shell/Sidebar.tsx"
      provides: "Список сессий (placeholder группы Today/Yesterday/Earlier — данные dummy в Phase 1)"
      exports: ["Sidebar"]
    - path: "frontend/components/shell/ChannelSelector.tsx"
      provides: "Dropdown из shadcn Select — заглушка списка из localStorage MCP connections (в Phase 1 — пусто)"
      exports: ["ChannelSelector"]
    - path: "frontend/components/chat/Thread.tsx"
      provides: "Список сообщений с авто-скроллом; в Phase 1 — рендер dummy messages из props"
      exports: ["Thread"]
    - path: "frontend/components/chat/Input.tsx"
      provides: "Textarea + кнопка Send; ⌘+Enter отправка; placeholder 'Спросите про базу 1С...'"
      exports: ["Input"]
    - path: "frontend/app/settings/page.tsx"
      provides: "Скелет страницы настроек: две секции — LLM и Connections; в Phase 1 формы только показывают текущие значения из localStorage, CRUD — в Phase 2.4"
      exports: ["default SettingsPage"]
    - path: "frontend/lib/api.ts"
      provides: "fetchChat (POST /chat → ReadableStream), fetchHealth, fetchMCPPing; типизированные через lib/types.ts"
      exports: ["fetchChat", "fetchHealth", "fetchMCPPing"]
    - path: "frontend/lib/sse.ts"
      provides: "parseSSEStream: ReadableStream<Uint8Array> → AsyncIterable<SSEEvent>"
      exports: ["parseSSEStream", "SSEEvent"]
    - path: "frontend/lib/storage.ts"
      provides: "getLLMConfig, setLLMConfig, getMCPConnections, setMCPConnections — обёртки над localStorage с типами"
      exports: ["getLLMConfig", "setLLMConfig", "getMCPConnections", "setMCPConnections"]
    - path: "frontend/lib/types.ts"
      provides: "Типы зеркалируют Pydantic модели backend: ChatRequest, SSEEvent, MCPConnection, LLMConfig, HealthResponse"
      exports: ["ChatRequest", "SSEEvent", "MCPConnection", "LLMConfig", "HealthResponse"]
  key_links:
    - from: "frontend/app/layout.tsx"
      to: "frontend/components/shell/AppShell.tsx"
      via: "import + рендер обёртка"
      pattern: "import.*AppShell"
    - from: "frontend/app/page.tsx"
      to: "frontend/components/chat/Thread.tsx"
      via: "import Thread"
      pattern: "import.*Thread"
    - from: "frontend/lib/api.ts"
      to: "frontend/lib/sse.ts"
      via: "fetchChat использует parseSSEStream для распарсивания response.body"
      pattern: "parseSSEStream"
    - from: "frontend/lib/api.ts"
      to: "frontend/lib/storage.ts"
      via: "fetchChat читает LLM api key из getLLMConfig() и кладёт в header X-LLM-API-Key"
      pattern: "X-LLM-API-Key"
    - from: "frontend/components/shell/Header.tsx"
      to: "frontend/components/shell/ChannelSelector.tsx"
      via: "import + render внутри header"
      pattern: "import.*ChannelSelector"
---

<objective>
Заложить весь frontend-стек проекта «1С Аналитик»: Next.js 15 (App Router) + React 19, Tailwind 4 с тёмной темой by default, шрифты IBM Plex, shadcn/ui примитивы, AppShell (header + sidebar + main + bottom input), типизированный API-клиент к backend, парсер SSE и обёртки над localStorage для LLM ключей. Без бизнес-логики чата — только skeleton, dummy данные, empty states.

Purpose: пользователь запускает `pnpm dev` (или `docker compose up frontend` в Phase 2+), открывает http://localhost:3010 и видит готовую оболочку приложения с правильными шрифтами/темой/русским UI/AppShell. Это фундамент для Phase 2 MVP chat, и для FR-1/FR-2 (Settings page будет наполнена в Phase 2.4), и для FR-7 (SSE парсер уже работает).

Output: ~30 файлов в frontend/, рабочий pnpm dev, чистый tsc + eslint.
</objective>

<execution_context>
@C:/CLOUDE_PR/.claude/get-shit-done/workflows/execute-plan.md
@C:/CLOUDE_PR/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@PROJECT.md
@REQUIREMENTS.md
@ARCHITECTURE.md
@CLAUDE.md
@.planning/intel/STACK.md

<interfaces>
<!-- Контракты между frontend и backend Plan 01 -->

# Зеркало Pydantic моделей backend в TypeScript (lib/types.ts)
export type ChatRequest = {
  message: string;
  session_id?: string | null;
  channel_id?: string | null;
};

export type HealthResponse = {
  status: "ok" | "degraded";
  version: string;
  db: "ok" | "error";
};

export type MCPPingResponse = {
  mcp_version: string;
  tool_count: number;
  session_id: string;
  duration_ms: number;
};

# SSE event types (IR-6) — должны совпадать с backend Plan 01
export type SSEEvent =
  | { event: "status"; data: { stage: "thinking" | "calling_tool" | "responding" } }
  | { event: "delta"; data: { content: string } }
  | { event: "tool_call"; data: { name: string; args: Record<string, unknown>; call_id: string } }
  | { event: "tool_result"; data: { call_id: string; result: unknown; duration_ms: number } }
  | { event: "card"; data: { type: "table" | "object" | "log"; payload: unknown } }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { message: string; code: string } };

# LLM config (только в localStorage, NEVER на backend)
export type LLMConfig = {
  endpoint: string;          // "https://api.openai.com/v1"
  api_key: string;           // sk-...
  model: string;             // "mimo-32b"
  temperature: number;       // 0.3
};

# MCP connection (зеркало backend mcp_connections row)
export type MCPConnection = {
  id: string;
  name: string;
  endpoint: string;          // "http://localhost:6010/mcp"
  channel: string | null;
  anon_enabled: boolean;
};

# Контракт fetchChat
// fetchChat читает api_key из getLLMConfig() и шлёт его ТОЛЬКО в header X-LLM-API-Key
async function fetchChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<SSEEvent>;
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Next.js 15 + Tailwind 4 + shadcn/ui init с тёмной темой и IBM Plex</name>
  <files>frontend/package.json, frontend/tsconfig.json, frontend/next.config.ts, frontend/postcss.config.mjs, frontend/tailwind.config.ts, frontend/.env.local.example, frontend/.eslintrc.json, frontend/components.json, frontend/app/layout.tsx, frontend/app/page.tsx, frontend/app/globals.css, frontend/components/ui/button.tsx, frontend/components/ui/input.tsx, frontend/components/ui/scroll-area.tsx, frontend/components/ui/select.tsx, frontend/lib/utils.ts</files>
  <action>
Инициализировать Next.js 15 проект в frontend/ строго по стеку из PROJECT.md. Никаких лишних пакетов сверх списка (запрещены: Inter font, framer-motion для glass morphism, эмодзи в UI — это явный анти-список из CLAUDE.md).

1. frontend/package.json:
   - name: "1c-analyst-frontend", private: true, type: "module"
   - dependencies: next@^15.0.0, react@^19.0.0, react-dom@^19.0.0, @radix-ui/react-select, @radix-ui/react-scroll-area, @radix-ui/react-slot, class-variance-authority, clsx, tailwind-merge, lucide-react
   - devDependencies: typescript@^5.6, @types/node, @types/react@^19, @types/react-dom@^19, tailwindcss@^4.0.0, @tailwindcss/postcss@^4.0.0, postcss, eslint@^9, eslint-config-next@^15, prettier
   - scripts: dev=`next dev -p 3010`, build=`next build`, start=`next start -p 3010`, lint=`next lint`, type-check=`tsc --noEmit`
   - НЕ добавлять: openai SDK (это backend), framer-motion, эмодзи-библиотеки, mantine/chakra/MUI (только shadcn/ui над Radix).

2. frontend/tsconfig.json — strict: true, target: ES2022, module: ESNext, moduleResolution: bundler, jsx: preserve, paths: { "@/*": ["./*"] }. Без скрытых any (noImplicitAny, strictNullChecks — оба включены через strict).

3. frontend/next.config.ts — `experimental: { reactCompiler: false }` (стабильность), eslint.ignoreDuringBuilds=false, typescript.ignoreBuildErrors=false. Никаких rewrites/redirects пока.

4. frontend/postcss.config.mjs — `export default { plugins: { '@tailwindcss/postcss': {} } }` (Tailwind 4 синтаксис, НЕ Tailwind 3).

5. frontend/tailwind.config.ts:
   - darkMode: 'class'
   - content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}']
   - theme.extend.fontFamily: { sans: ['var(--font-plex-sans)', 'system-ui'], mono: ['var(--font-plex-mono)', 'monospace'] }
   - theme.extend.colors: токены через CSS variables (--bg, --bg-elevated, --fg, --fg-muted, --border, --accent) — определяются в globals.css

6. frontend/app/globals.css:
   - `@import "tailwindcss";`
   - CSS variables в :root (dark по умолчанию): --bg #0a0a0a, --bg-elevated #141414, --fg #ededed, --fg-muted #8a8a8a, --border #262626, --accent #f97316 (warm orange — не purple-cyan градиент из бана v0).
   - `* { border-color: rgb(var(--border)) }`
   - body { background: var(--bg); color: var(--fg); font-family: var(--font-plex-sans) }
   - Никаких глобальных переопределений scroll-bar / glass morphism.

7. frontend/app/layout.tsx:
   - import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google"
   - const plexSans = IBM_Plex_Sans({ subsets: ['latin','cyrillic'], weight: ['400','500','600'], variable: '--font-plex-sans' })
   - const plexMono = IBM_Plex_Mono({ subsets: ['latin','cyrillic'], weight: ['400','500'], variable: '--font-plex-mono' })
   - metadata: { title: '1С Аналитик', description: 'Чат-консоль для бизнес-аналитиков 1С' }
   - return `<html lang="ru" className={\`dark \${plexSans.variable} \${plexMono.variable}\`}><body>{children}</body></html>`

8. frontend/app/page.tsx — пока минимальный экран с h1 "1С Аналитик" и текстом "Загрузка skeleton..." (наполнение AppShell — в Task 2).

9. frontend/components/ui/button.tsx, input.tsx, scroll-area.tsx, select.tsx — стандартные shadcn компоненты (можно сгенерировать через `npx shadcn@latest add button input scroll-area select` ПОСЛЕ инициализации, либо вручную скопировать из shadcn registry). frontend/components.json — стандартный shadcn config (style: default, baseColor: neutral, cssVariables: true).

10. frontend/lib/utils.ts — стандартный `cn` helper (clsx + tailwind-merge).

11. frontend/.eslintrc.json — extends: ["next/core-web-vitals", "next/typescript"], rules: { "@typescript-eslint/no-explicit-any": "error" } (для NFR-19).

12. frontend/.env.local.example — NEXT_PUBLIC_BACKEND_URL=http://localhost:8010.

Антипаттерны (явный бан из CLAUDE.md, проверить grep'ом после генерации): нигде не должно быть Inter font, "glass", "from-purple", "to-cyan", эмодзи 🔥💡✨ в JSX, светлой темы как опции в коде.
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; pnpm install &amp;&amp; pnpm type-check &amp;&amp; pnpm lint &amp;&amp; pnpm build &amp;&amp; ! grep -rE "(font-inter|from-purple|to-cyan|glass-morphism)" app components lib --include="*.tsx" --include="*.ts" --include="*.css"</automated>
  </verify>
  <done>
    - pnpm install проходит без ошибок
    - pnpm type-check (tsc --noEmit) — ноль ошибок (NFR-19)
    - pnpm lint — clean
    - pnpm build — успешная сборка
    - В коде нет запрещённых из CLAUDE.md паттернов (grep подтверждает)
    - В layout.tsx html lang="ru" className содержит "dark" (NFR-15, NFR-16)
    - IBM Plex шрифты загружаются через next/font (видно в build output)
  </done>
</task>

<task type="auto">
  <name>Task 2: AppShell (header + sidebar + main + input), главная страница, Settings stub</name>
  <files>frontend/app/page.tsx, frontend/app/settings/page.tsx, frontend/components/shell/AppShell.tsx, frontend/components/shell/Header.tsx, frontend/components/shell/Sidebar.tsx, frontend/components/shell/ChannelSelector.tsx, frontend/components/shell/ModelBadge.tsx, frontend/components/chat/Thread.tsx, frontend/components/chat/Message.tsx, frontend/components/chat/Input.tsx</files>
  <action>
Собрать видимую оболочку приложения по ARCHITECTURE.md "High-level topology" и REQUIREMENTS NFR-15/16. Без реальной бизнес-логики — dummy данные, заглушки кнопок, empty states. Десктоп-only вёрстка (минимум 1280px, см. CLAUDE.md «mobile-first запрещён»).

1. frontend/components/shell/AppShell.tsx:
   - Layout: CSS grid `grid-cols-[260px_1fr] grid-rows-[56px_1fr_auto] h-screen`
   - Header в row 1, span обе колонки (col-span-2)
   - Sidebar в row 2 col 1
   - Main в row 2 col 2 (overflow-y-auto)
   - Принимает children: ReactNode для main, и опционально prop bottom: ReactNode для input area внизу main колонки
   - Использует CSS variables из globals.css для всех цветов

2. frontend/components/shell/Header.tsx:
   - sticky top, h-14, border-bottom
   - Слева: лого-текст "1С Аналитик" (font-semibold)
   - В центре: <ChannelSelector />
   - Справа: <ModelBadge /> + ссылка на /settings (icon SettingsIcon из lucide-react, без подписи)
   - Никаких эмодзи, никаких decorative dots/градиентов

3. frontend/components/shell/ChannelSelector.tsx:
   - Использует shadcn Select. Опции читаются из getMCPConnections() из lib/storage (в Phase 1 список будет пуст)
   - Если пусто: показывает placeholder "Подключения не настроены" + disabled state
   - Возвращает onChange через useState — пока кладёт в localStorage active_channel_id

4. frontend/components/shell/ModelBadge.tsx:
   - Маленький pill с monospace шрифтом IBM Plex Mono: "MiMo · 0.3" (model + temperature)
   - Читает из getLLMConfig(); если не настроено — пустой бейдж "—"

5. frontend/components/shell/Sidebar.tsx:
   - Заголовок группы "Сегодня", "Вчера", "Ранее" (русский, см. FR-8)
   - В Phase 1 — все группы пустые с подписью "Истории пока нет"
   - Кнопка "+ Новый чат" сверху

6. frontend/components/chat/Thread.tsx:
   - Принимает messages: Message[] (тип из lib/types.ts добавить)
   - Рендерит ScrollArea с <Message> на каждое сообщение
   - В Phase 1 — рендерит dummy: одно сообщение role=assistant content="Готов отвечать на вопросы про вашу базу 1С. Выберите подключение или настройте новое."

7. frontend/components/chat/Message.tsx:
   - Принимает {role, content}. Для role=user — выравнивание вправо, фон bg-elevated. Для assistant — выравнивание влево, фон transparent.
   - Использует font-sans, ширина max-w-3xl, padding p-4, rounded-lg

8. frontend/components/chat/Input.tsx:
   - <textarea> resizable: none, min-h 56px max-h 240px, placeholder "Спросите про базу 1С..."
   - Кнопка "Отправить" справа (shadcn Button)
   - ⌘+Enter / Ctrl+Enter — submit (NFR-17 готовится, реальная отправка — Phase 2)
   - В Phase 1 onSubmit — console.log + alert "Подключите MCP и LLM в настройках" (если getLLMConfig() пустой)

9. frontend/app/page.tsx:
   - Empty state когда нет ни MCP connections, ни LLM config:
     - Большой заголовок "Начните работу"
     - Подзаголовок "Подключите вашу базу 1С через MCP и укажите LLM-провайдер"
     - Кнопка "Настроить" → Link на /settings
   - Иначе — <AppShell bottom={<Input />}><Thread messages={dummyMessages} /></AppShell>
   - Проверка empty state — client component с useEffect (читать localStorage), пока не загрузилось — простой skeleton

10. frontend/app/settings/page.tsx:
   - В Phase 1 — только два section'а в карточках: "LLM" и "MCP подключения"
   - В каждом section — read-only вывод текущих значений из localStorage (если есть) + сообщение "Редактирование появится в следующей итерации (Phase 2)"
   - Это полностью удовлетворяет FR-1/FR-2 на уровне «есть страница и каркас», CRUD — Phase 2.4

Запрещено в этом таске: добавлять реальный fetch к /chat, реализовывать SSE парсинг (это Task 3 этого же plan'а), писать business logic, использовать класс `text-purple`/`text-cyan`, эмодзи в JSX, иконки кроме lucide-react.

После таска — `pnpm dev` и открыть http://localhost:3010, убедиться глазами что AppShell виден (см. Phase 4 общих правил «Верификация — обязательно посмотреть»).
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; pnpm type-check &amp;&amp; pnpm lint &amp;&amp; pnpm build &amp;&amp; ! grep -rE "(🔥|💡|✨|emoji|from-purple|to-cyan)" app components --include="*.tsx"</automated>
  </verify>
  <done>
    - `pnpm dev` → http://localhost:3010 рендерится с тёмной темой
    - Видны: header (с лого, channel selector placeholder, model badge "—", settings icon), sidebar (3 пустые группы), main (либо empty state с CTA «Настроить», либо dummy thread)
    - /settings рендерится с двумя секциями (LLM, Connections) в read-only виде
    - Весь текст на русском, шрифт IBM Plex Sans виден через DevTools (computed font-family содержит Plex)
    - ⌘+Enter в textarea триггерит submit (alert или console.log в Phase 1)
    - tsc + lint + build — clean
    - Нет запрещённых паттернов
  </done>
</task>

<task type="auto">
  <name>Task 3: API-клиент (lib/api.ts + lib/sse.ts + lib/storage.ts + lib/types.ts), smoke вызов /health</name>
  <files>frontend/lib/api.ts, frontend/lib/sse.ts, frontend/lib/storage.ts, frontend/lib/types.ts</files>
  <action>
Реализовать типизированную инфраструктуру для общения с backend. Все типы — зеркало Pydantic моделей из Plan 01 (см. <interfaces> в context). Никаких `any`.

1. frontend/lib/types.ts — ровно типы из <interfaces>: ChatRequest, SSEEvent (discriminated union по event), HealthResponse, MCPPingResponse, LLMConfig, MCPConnection. Дополнительно: ChatMessage = { id: string; role: 'user'|'assistant'|'tool'; content: string; created_at: string }.

2. frontend/lib/storage.ts:
   - Константы ключей: const KEY_LLM = 'analyst.llm', KEY_MCP = 'analyst.mcp_connections', KEY_ACTIVE_CHANNEL = 'analyst.active_channel'
   - getLLMConfig(): LLMConfig | null — JSON.parse из localStorage (try/catch, на ошибку — null)
   - setLLMConfig(cfg: LLMConfig): void
   - getMCPConnections(): MCPConnection[] — пустой массив если ничего нет
   - setMCPConnections(conns: MCPConnection[]): void
   - getActiveChannelId(): string | null
   - setActiveChannelId(id: string | null): void
   - Все функции защищены от SSR (typeof window === 'undefined' → возвращают safe defaults). Это критично для Next.js App Router.

3. frontend/lib/sse.ts:
   - export async function* parseSSEStream(stream: ReadableStream<Uint8Array>): AsyncIterable<SSEEvent>
   - Использует TextDecoderStream, читает через ReaderDefault, аккумулирует buffer, выделяет блоки разделённые \n\n
   - Каждый блок разбирает построчно: строка "event: name" → currentEvent, "data: payload" → накопить data (может быть multi-line), пустая строка — yield {event: currentEvent, data: JSON.parse(dataBuffer)}
   - Тип возврата — SSEEvent (с runtime-валидацией: если event не из enum — yield {event:'error', data:{message:'unknown event', code:'sse_parse'}})
   - При cancel() reader — корректно завершиться

4. frontend/lib/api.ts:
   - const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8010'
   - export async function fetchHealth(): Promise<HealthResponse>
       — fetch BACKEND+'/health', response.json() с as HealthResponse
   - export async function* fetchChat(req: ChatRequest, signal?: AbortSignal): AsyncIterable<SSEEvent>
       — Читает getLLMConfig() (на client side). Если нет api_key → yield {event:'error', data:{message:'API ключ не задан', code:'no_api_key'}} и return.
       — fetch BACKEND+'/chat', method POST, headers {Content-Type: application/json, X-LLM-API-Key: cfg.api_key, X-LLM-Endpoint: cfg.endpoint, X-LLM-Model: cfg.model, Accept: 'text/event-stream'}, body JSON.stringify(req), signal
       — Если !response.ok → yield error event с response.status и return
       — yield* parseSSEStream(response.body!)
   - export async function fetchMCPPing(endpoint: string, signal?: AbortSignal): Promise<MCPPingResponse>
       — fetch POST BACKEND+'/mcp/_/ping?endpoint='+encodeURIComponent(endpoint) (Phase 1: conn_id игнорируется backend'ом, передаём '_')

5. Подключить smoke-вызов /health на главной странице (app/page.tsx) — useEffect → fetchHealth() → показать в нижнем углу мелким текстом "Backend: ok / version" или "Backend: недоступен" (это и есть проверка integration).

Запрещено: использовать axios (только fetch), использовать `any` в любых сигнатурах, читать api_key из URL/cookies/sessionStorage. localStorage only — это критическое решение архитектуры (NFR-6, ARCHITECTURE Key Decision #1).
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; pnpm type-check &amp;&amp; pnpm lint &amp;&amp; ! grep -rE "(: any\b|as any\b|@ts-ignore)" lib app components --include="*.ts" --include="*.tsx" &amp;&amp; ! grep -rE "axios" package.json lib --include="*.ts"</automated>
  </verify>
  <done>
    - lib/types.ts — все типы экспортированы, zero any
    - lib/storage.ts — функции работают на server (SSR safe) и client
    - lib/sse.ts — parseSSEStream корректно парсит multi-event поток (минимум визуально подтверждается через test SSE из backend Plan 01)
    - lib/api.ts — fetchChat читает api_key из localStorage и шлёт в header X-LLM-API-Key, НЕ в body (NFR-6 / ARCHITECTURE #1)
    - app/page.tsx показывает статус backend в нижнем углу (smoke integration)
    - tsc + lint clean, grep подтверждает отсутствие any/@ts-ignore/axios
    - Если оба плана уже исполнены: `pnpm dev` + `docker compose up backend`, открыть http://localhost:3010 — UI рендерится, в углу "Backend: ok 0.1.0"
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Пользователь → Browser localStorage | LLM API ключ хранится только тут, никогда не в backend |
| Browser → Backend | Все запросы — fetch с явными headers; CORS контролирует доступ |
| 3rd-party скрипты → DOM | Next.js по умолчанию изолирует, но любая внешняя dependency может теоретически читать localStorage |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-09 | Information Disclosure | LLM API ключ в localStorage — доступен любому JS на этом origin | mitigate | (a) минимизировать сторонние зависимости (нет analytics, нет sentry в Phase 1); (b) в Phase 3 рассмотреть crypto.subtle для encryption-at-rest (ARCHITECTURE Tradeoff раздел 1); (c) Phase 3 добавит CSP headers |
| T-01-10 | Spoofing | Пользователь может ввести произвольный LLM endpoint, в т.ч. вредоносный | accept | By design: аналитик сам контролирует свой endpoint. Phase 3 — добавить allowlist в Settings |
| T-01-11 | Tampering | XSS в content сообщений ассистента может выполниться | mitigate | В Phase 1 Thread/Message рендерят content как plain text (не dangerouslySetInnerHTML). В Phase 2 при подключении markdown — использовать react-markdown с sanitize плагином, НЕ raw html |
| T-01-12 | Information Disclosure | API ключ случайно попасть в body запроса /chat | mitigate | fetchChat явно НЕ кладёт api_key в body; ChatRequest TypeScript type не имеет поля api_key (compile-time guard); тест-grep подтверждает что в lib/api.ts ключ только в header X-LLM-API-Key |
| T-01-13 | Denial of Service | Большие SSE стримы зависают reader | mitigate | fetchChat принимает signal: AbortSignal; UI должен передавать AbortController при unmount (это уже Phase 2 интеграция, но контракт сейчас) |
</threat_model>

<verification>
1. `cd frontend && pnpm install && pnpm type-check && pnpm lint && pnpm build` — всё зелёное
2. `pnpm dev` → открыть http://localhost:3010 в Chrome:
   - DevTools → Elements → <html> имеет class содержащий "dark", lang="ru"
   - Computed style на body содержит "IBM Plex Sans" в font-family
   - Виден AppShell: header (лого "1С Аналитик" слева, ChannelSelector placeholder, ModelBadge "—", иконка settings), sidebar (пустые группы Сегодня/Вчера/Ранее с подписью «Истории пока нет»), main с empty state ИЛИ dummy thread, textarea с placeholder "Спросите про базу 1С..."
3. Открыть http://localhost:3010/settings — две секции (LLM, Connections), русский текст
4. Запустить backend (Plan 01) + frontend параллельно — в углу главной видно "Backend: ok 0.1.0" (smoke integration)
5. ⌘+Enter / Ctrl+Enter в textarea — срабатывает submit handler (alert или console.log)
6. grep -rE "(font-inter|from-purple|to-cyan|glass|🔥|: any\b|as any)" frontend/app frontend/components frontend/lib — ничего не находит
7. Lighthouse > 90 в категории Best Practices (Performance/A11y/SEO — не критично для Phase 1)
</verification>

<success_criteria>
- Next.js 15 + React 19 + Tailwind 4 + shadcn/ui установлены и работают (стек строго по PROJECT.md)
- Тёмная тема by default — class="dark" на <html>, нет переключателя light (NFR-15)
- IBM Plex Sans + Mono подключены через next/font (NFR-16 — кириллица subset)
- Русский UI: lang="ru", все видимые тексты на русском (NFR-16)
- AppShell собран: header + sidebar + main + bottom input (ARCHITECTURE topology)
- Empty state на главной с CTA «Настроить» → /settings (FR-10)
- Скелет /settings со списком LLM + Connections (FR-1, FR-2 — основа)
- ChannelSelector в header — placeholder под мульти-tenant (FR-9)
- lib/sse.ts парсит EventStream → AsyncIterable<SSEEvent> (FR-7, IR-6)
- lib/api.ts шлёт LLM api_key только в header X-LLM-API-Key, НЕ в body (NFR-6)
- lib/storage.ts — SSR-safe localStorage обёртка
- tsc strict + eslint clean, zero `any` (NFR-19)
- pnpm build проходит
- Запрещённые паттерны (Inter font, purple-cyan, glass, эмодзи) отсутствуют (CLAUDE.md баны)
</success_criteria>

<output>
После завершения создать `.planning/phases/01-foundation/01-02-SUMMARY.md` со списком созданных файлов, реальными командами для проверки (`pnpm dev`, скриншот главной + /settings), статусом tsc/lint/build, подтверждением что Backend integration (fetchHealth) работает совместно с Plan 01.
</output>
