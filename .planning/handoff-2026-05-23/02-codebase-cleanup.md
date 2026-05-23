# 02 · Codebase Cleanup — file:line diffs

Все правки, не требующие новых компонентов. Точные file:line + before/after diff. Можно частично автоматизировать (codemods отмечены ниже).

---

## REM-1 — json-tree.tsx: хардкод цветов

**Файл:** `frontend/lib/json-tree.tsx`

**Проблема:** 5 жёстко вшитых Tailwind-цветов вместо токенов. Используется в `ToolTrace` (раскрытый JSON tool_calls). В light-теме `text-green-300` неоновый на песке.

**Точки:**
- L35 — `text-green-300` (string value)
- L44 — `text-orange-300` (number value)
- L53, L62 — `text-purple-300` (boolean, null)
- L80 — `text-red-400` (Circular ref)

**Diff (целиком):**

```diff
   // Primitive: string
   if (typeof value === "string") {
     return (
       <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
-        <span className="text-green-300">&quot;{truncateStr(value)}&quot;</span>
+        <span className="text-[var(--success)]">&quot;{truncateStr(value)}&quot;</span>
       </div>
     );
   }

   // Primitive: number
   if (typeof value === "number") {
     return (
       <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
-        <span className="text-orange-300">{value}</span>
+        <span className="text-[var(--accent)]">{value}</span>
       </div>
     );
   }

   // Primitive: boolean
   if (typeof value === "boolean") {
     return (
       <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
-        <span className="text-purple-300">{String(value)}</span>
+        <span className="text-[var(--warning)]">{String(value)}</span>
       </div>
     );
   }

   // Primitive: null
   if (value === null) {
     return (
       <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
-        <span className="text-purple-300">null</span>
+        <span className="text-[var(--fg-3)] italic">null</span>
       </div>
     );
   }
```

```diff
   // Circular reference detection
   if (isCircular(value)) {
     return (
       <div style={{ paddingLeft: indent }} className="font-mono text-xs tabular-nums">
-        <span className="text-red-400">[Circular]</span>
+        <span className="text-[var(--error)]">[Circular]</span>
       </div>
     );
   }
```

**Маппинг (документируй):**
- строки → `--success` (mint) — «безопасные данные»
- числа → `--accent` (signal orange) — «числовое значение, главный фокус»
- booleans → `--warning` (ochre) — «признак, состояние»
- null/undefined → `--fg-3` (muted) — «отсутствие»
- circular / errors → `--error`

---

## REM-2 — Текст про Docker в Electron

**Файл:** `frontend/app/settings/page.tsx:33`

**Проблема:** Backend недоступен → текст «Запустите docker compose up». В Electron-сборке Docker нет.

**Diff:**

```diff
-        setError("Backend недоступен. Запустите docker compose up");
+        setError("Серверная часть не отвечает. Проверьте, что приложение запущено корректно, и попробуйте перезагрузить страницу.");
```

**Дополнительно:** Если есть `window.electronAPI` (флаг Electron-runtime), показывай кнопку «↻ Перезапустить серверную часть». См. `06-screen-redesigns.md` § Status для полного состояния «backend down».

---

## REM-3 — Версия из одного источника

**Проблема:** В трёх местах разные значения версии.

**Точки:**
- `frontend/components/shell/Header.tsx:48` — `<StencilLockup fontSize={16} />` (использует default из самого Lockup)
- `frontend/components/shell/StencilLockup.tsx:34` — default `version="1.2.2"`
- `frontend/app/about/page.tsx:174` — текст «Версия 1.2.1»
- `frontend/package.json` — true source

**Fix:**

1. Создай `frontend/lib/app-version.ts`:
   ```ts
   // Source-of-truth для отображаемой версии.
   // Берётся из package.json в runtime via env, чтобы не тянуть весь package.json в bundle.
   export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "1.2.4";
   ```

2. В `next.config.mjs` пропиши env (если ещё не):
   ```js
   const pkg = JSON.parse(fs.readFileSync('./package.json', 'utf8'));
   export default {
     env: { NEXT_PUBLIC_APP_VERSION: pkg.version },
     // ... rest
   };
   ```

3. **`StencilLockup.tsx:34`** — убрать default value, сделать обязательным или подставить из APP_VERSION:
   ```diff
   -  version = "1.2.2",
   +  version = APP_VERSION,
   ```
   и `import { APP_VERSION } from "@/lib/app-version";` в шапке.

4. **`app/about/page.tsx:174`** — заменить «Версия 1.2.1» на `{APP_VERSION}`:
   ```diff
   -        Версия 1.2.1
   +        Версия {APP_VERSION}
   ```

5. **Tests:** обновить тесты, которые матчат текст версии.

---

## REM-4 — Терминология (запрещённые термины)

См. `08-copy-glossary.md` для **полной таблицы замен**. Здесь — конкретные файлы и строки.

### REM-4.a — «канал» как лейбл UI

| Файл | Строка | Текущий текст | Заменить на |
|---|---|---|---|
| `frontend/components/shell/ChannelSelector.tsx` | 244 | `aria-label="Выбор канала"` | `aria-label="Выбор базы 1С"` |
| `frontend/components/shell/ChannelSelector.tsx` | 273 | `<DropdownMenuLabel>Канал</DropdownMenuLabel>` | `<DropdownMenuLabel>Базы 1С</DropdownMenuLabel>` |
| `frontend/components/shell/ChannelSelector.tsx` | 296 | `Канал: {conn.channel}` | удалить совсем — это техническая строка, переедет в expert-блок |
| `frontend/components/settings/MCPConnectionList.tsx` | 33 | `канал «{conn.channel}»` | `профиль «{conn.channel}»` (если proxy) или скрыть строку |
| `frontend/components/settings/MCPConnectionList.tsx` | 145 | «proxy — имя канала» | «proxy — имя профиля внешнего шлюза» |
| `frontend/components/settings/MCPConnectionForm.tsx` | 324 | `Канал` (label) | `Профиль (для прокси)` |
| `frontend/components/settings/MCPConnectionForm.tsx` | 338 | «Имя канала, которое введено в обработке MCP_Toolkit» | «Идентификатор, под которым прокси-шлюз отдаёт ваше подключение» |
| `frontend/app/status/page.tsx` | 351 | `{ label: "Канал", value: channel \|\| "—", ...}` | переместить эту строку под `<details>Технические подробности</details>` — см. `06-screen-redesigns.md` § Status |
| `frontend/app/status/page.tsx` | 379 | `канал «${channel}»` | `профиль «${channel}»` |
| `frontend/app/status/page.tsx` | 393 | `канал ${channel}` | `профиль ${channel}` |
| `frontend/app/settings/memory/page.tsx` | 75 | «Не выбран канал. Откройте главный экран и выберите базу 1С.» | «Не выбрана база 1С. Откройте главный экран и выберите подключение.» |
| `frontend/app/settings/skills/page.tsx` | 213 | то же | то же |
| `frontend/lib/form-schemas.ts` | 20 | `"Для прокси-подключения укажите канал"` | `"Для прокси-подключения укажите профиль"` |

> **`conn.channel` как поле модели — НЕ переименовывать**: это backend API контракт. Только UI-strings.

### REM-4.b — «MCP / MCP_Toolkit» в видимом UI

| Файл | Строка | Заменить |
|---|---|---|
| `frontend/app/guide/page.tsx` | 29 | «подключения, инструменты MCP, сценарии, диагностика» → «подключения, обработка 1С, сценарии, диагностика» |
| `frontend/app/guide/page.tsx` | 358 | `MCP_Toolkit_v1.7.0.epf` → оставить в `<Code>` (это технический референс), но обернуть в раздел «Для системного администратора» |
| `frontend/app/guide/page.tsx` | 450, 454 | «Инструменты MCP» → «Инструменты в 1С» |
| `frontend/app/guide/page.tsx` | 458 | «10 инструментов MCP Toolkit» → «10 операций над базой 1С» |
| `frontend/app/guide/page.tsx` | 1137 | «обычно 10 у MCP Toolkit» → «обычно 10 операций» |
| `frontend/app/guide/page.tsx` | 1177 | «обработка MCP Toolkit … MCP_Toolkit_v1.7.0» → оставить точное имя файла (это .epf, который пользователь физически кладёт в 1С), но обернуть фразой «обработка-обработчик (имя файла `MCP_Toolkit_v1.7.0.epf`)» |
| `frontend/components/shell/KindBadge.tsx` | 28 | «обработка MCP_Toolkit работает» → «обработка-обработчик работает» |
| `frontend/components/settings/MCPConnectionForm.tsx` | 254 | «Тот же номер, что введён в MCP_Toolkit на вкладке «Встроенный сервер».» → «Тот же номер, что указан в обработке 1С на вкладке «Встроенный сервер».» |
| `frontend/components/settings/MCPConnectionForm.tsx` | 306 | «Обработка MCP_Toolkit запущена на этом компьютере» → «Обработка-обработчик запущена на этом компьютере» |
| `frontend/components/settings/MCPConnectionList.tsx` | 91 | «встроенный сервер MCP_Toolkit на том же порту» → «встроенный сервер обработки 1С на том же порту» |

> Файл `.epf` называется `MCP_Toolkit_v1.7.0.epf` — это **реальный артефакт**, который пользователь берёт у ИТ-отдела. Имя файла в инструкциях оставлять (это конкретный поисковый запрос для аналитика), но **окружающий текст** — нейтральный.

### REM-4.c — «Tool calls» как метрика

**Файл:** `frontend/app/insights/page.tsx`

Уже есть `Запросов к 1С` на L95 (хорошо). Но рядом есть:

| Строка | Текущий | Заменить |
|---|---|---|
| (проверить) `Среднее время tool вызова` | → «Среднее время обращения к 1С» |
| `Топ инструментов` | → «Что чаще всего спрашивают» |
| Заголовки таблицы `Calls / Errors / Rate` | → `Запросов / Ошибок / % ошибок` |
| `Топ баз 1С (channels)` | → `Топ баз 1С` |
| Колонка `Channel` | → `База` |

---

## REM-5 — StreamingIndicator → StreamingStages

**Проблема:** `frontend/components/chat/StreamingIndicator.tsx` (старый, 31 строка) и `StreamingStages.tsx` (новый, 191 строка) сосуществуют. Аналитик может увидеть либо одно, либо другое.

**Решение:** Полностью удалить `StreamingIndicator`. Везде, где используется — переключить на `StreamingStages`.

**Шаги:**
1. `grep -r "StreamingIndicator" frontend/` — найди все импорты
2. Замени `<StreamingIndicator stage={...} toolName={...} />` → `<StreamingStages stages={mappedStages} activeIndex={...} />`
3. Маппинг от старой одностадийной модели к многостадийной должен брать данные из `useChatStream` — см. существующий `frontend/lib/streaming-stages.ts` (там уже есть функция, проверь).
4. Удали файл `frontend/components/chat/StreamingIndicator.tsx`.
5. Удали тип `StreamingStage` если используется только в этом файле.

**Тест:** прогон `frontend/lib/__tests__/streaming-stages.test.ts` должен проходить.

---

## HIGH-1 — Tailwind config v3 vs v4

**Проблема:** `frontend/tailwind.config.ts` написан в v3-стиле (`theme.extend.colors / fontFamily / transitionDuration`), но `globals.css` импортирует Tailwind v4 (`@import "tailwindcss"`). Без директивы `@theme inline { … }` v4 игнорирует config — поэтому `bg-bg-1`, `duration-normal`, `font-jb-mono` **не работают как utility-классы**. Везде костыли `bg-[var(--bg-1)]` и `style={{ fontFamily: "var(--font-jb-mono)" }}`.

**Решение — выбрать ОДНО из двух:**

### Вариант A — миграция на v4 `@theme inline`

Прописать в `frontend/app/globals.css`:

```css
@import "tailwindcss";

@theme inline {
  --color-bg-0: var(--bg-0);
  --color-bg-1: var(--bg-1);
  --color-bg-2: var(--bg-2);
  --color-bg-3: var(--bg-3);
  --color-bg-4: var(--bg-4);
  --color-bg-hover: var(--bg-hover);
  --color-fg-1: var(--fg-1);
  --color-fg-2: var(--fg-2);
  --color-fg-3: var(--fg-3);
  --color-fg-4: var(--fg-4);
  --color-bd-1: var(--bd-1);
  --color-bd-2: var(--bd-2);
  --color-bd-3: var(--bd-3);
  --color-accent: var(--accent);
  --color-success: var(--success);
  --color-warning: var(--warning);
  --color-error: var(--error);

  --font-sans: "IBM Plex Sans", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
  --font-jb: "JetBrains Mono", ui-monospace, monospace;

  --duration-micro: 150ms;
  --duration-normal: 200ms;
  --duration-large: 300ms;

  --ease-design: cubic-bezier(0.4, 0, 0.2, 1);
}
```

После этого работают: `bg-bg-1`, `text-fg-3`, `border-bd-2`, `bg-accent-12` (если объявить), `font-jb`, `duration-normal`, `ease-design`. Удалить `tailwind.config.ts` или оставить пустым.

**Бенефит:** убираем 30+ inline `style={{ fontFamily }}` костылей в shell.

### Вариант B — оставить arbitrary, удалить config

Если миграция рискована (большой репо, тесты завязаны на классы) — просто **удалить `tailwind.config.ts`**, признать что вся семантика идёт через `bg-[var(--foo)]`. Тогда:
- удалить `style={{ fontFamily: "var(--font-jb-mono)" }}` повсюду
- создать utility-классы в `globals.css`:
  ```css
  .font-jb { font-family: var(--font-jb-mono), ui-monospace, monospace; }
  .font-plex-mono { font-family: var(--font-plex-mono), ui-monospace, monospace; }
  ```
  и использовать `className="font-jb"` вместо inline-style.

**Рекомендуется Вариант A** — он более canonical для v4. Если выбираешь B — задокументируй решение в `.brand/BRAND.md` и обнови `CLAUDE.md`.

---

## HIGH-2 — Focus-ring везде 2px

**Проблема:** В `button.tsx:7` — `focus-visible:ring-1 ring-[var(--accent)]`. 1px ring на signal-orange в light-теме на песочном фоне теряется.

**Затронутые файлы:**
- `frontend/components/ui/button.tsx:7`
- `frontend/components/ui/input.tsx` (искать `focus:ring`)
- `frontend/components/ui/select.tsx` (там же)
- `frontend/components/chat/Input.tsx:393` — `focus:ring-1 focus:ring-[var(--accent)]`
- `frontend/components/shell/ChannelSelector.tsx:243` — `focus:ring-2 focus:ring-[var(--accent-20)]` (этот уже 2px, но без offset)

**Diff (`button.tsx`):**

```diff
   "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors
-   focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent)]
+   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)] focus-visible:ring-[var(--accent)]
    disabled:pointer-events-none disabled:opacity-50",
```

**Diff (`Input.tsx:393`):**

```diff
   className="flex-1 resize-none rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
-   focus:outline-none focus:ring-1 focus:ring-[var(--accent)] transition-colors disabled:opacity-50"
+   focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-[var(--accent)] transition-colors disabled:opacity-50"
```

> Для `input` внутри composer оставляем 2px **без offset**, потому что в этом контексте border заменяется на signal-цвет — внешнее кольцо не нужно. Для button — offset обязателен.

---

## HIGH-3 — Settings — единая система paddings/radius

**Файл:** `frontend/app/settings/page.tsx` + всё, что внутри.

**Проблема:** На одной странице 3 разных padding:
- L92, L108 — sections `p-5 rounded-lg`
- Memory/Insights/Skills link-cards — `p-4 rounded-lg`
- Внутри MCPConnectionForm — внутренний контейнер `p-4 rounded-md`

**Решение — система:**

```
Level 1 (page sections, главные блоки):
  className="p-5 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)]"

Level 2 (nested forms, link-cards внутри секции):
  убрать внутренний border/padding контейнер;
  использовать space-y-4 для разделения полей внутри.

Link-cards (Memory / Insights / Skills) — перенести их в ОТДЕЛЬНУЮ группу
  под H2 «Дополнительные разделы» в той же визуальной системе p-5 rounded-lg,
  но как grid grid-cols-3 gap-3 с компактным внутренним padding p-4.
```

**Структурное изменение:**

```diff
   <div className="space-y-6">
     <section>
       <h2>Базы 1С</h2>
       <p>...</p>
-      <div className="p-5 rounded-lg border bg-elevated">
+      <div className="p-5 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)]">
         <MCPConnectionList />
       </div>
     </section>

     <section>
       <h2>Модель ИИ</h2>
       <p>...</p>
-      <div className="p-5 rounded-lg border bg-elevated">
+      <div className="p-5 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)]">
         <LLMConfigForm />
       </div>
     </section>

     <section>
       <h2>Локальные данные</h2>
-      <div className="p-5 rounded-lg border bg-elevated">
+      <div className="p-5 rounded-lg border border-[var(--bd-2)] bg-[var(--bg-1)]">
         <LocalDataSection />
       </div>
     </section>

+    <section>
+      <h2 className="font-mono uppercase tracking-wide text-base mb-3">
+        Дополнительно
+      </h2>
+      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
+        {/* link-cards: Memory / Insights / Skills */}
+      </div>
+    </section>
   </div>
```

Внутри `MCPConnectionForm.tsx` убрать обёрточный `<div className="p-4 ...">` — форма должна жить прямо в padding родительской секции.

---

## HIGH-6 — Двойной заголовок «Модель ИИ»

**Файлы:**
- `frontend/app/settings/page.tsx:108-114` — заголовок секции «Модель ИИ»
- `frontend/components/settings/LLMConfigForm.tsx:443-445` — внутренний label «Модель ИИ»

**Diff (`LLMConfigForm.tsx:443-445`):**

```diff
-          <label htmlFor="llm-model" className="block text-sm font-medium text-[var(--fg-1)] mb-1.5">
-            Модель ИИ
-          </label>
+          <label htmlFor="llm-model" className="block text-xs uppercase tracking-wider text-[var(--fg-3)] mb-1.5">
+            Языковая модель
+          </label>
```

То есть переименовать internal label на «Языковая модель» (или «Модель»), чтобы не дублировать заголовок секции.

**Дополнительно — SelectItem трюк:**

`LLMConfigForm.tsx:459-466` — `<SelectItem>` использует `<div className="flex flex-col">` (multi-line). Когда radix `<SelectValue />` рендерит выбранный item, trigger становится двухстрочный.

**Diff:**

```diff
-          <SelectItem key={preset.id} value={preset.id}>
-            <div className="flex flex-col">
-              <span>{preset.label}</span>
-              <span className="text-xs text-[var(--fg-3)]">{preset.description}</span>
-            </div>
-          </SelectItem>
+          <SelectItem key={preset.id} value={preset.id} textValue={preset.label}>
+            <span className="flex items-baseline gap-2">
+              <span>{preset.label}</span>
+              <span className="text-xs text-[var(--fg-3)]">— {preset.description}</span>
+            </span>
+          </SelectItem>
```

И — **удалить** дублирующее описание под селектом (LLMConfigForm.tsx:484-489):

```diff
-      <p className="text-xs text-[var(--fg-3)] mt-1">
-        {activePreset.model.description} · {activePreset.provider.label}
-      </p>
```

---

## HIGH-7 — Подсказка «Сначала сохраните, потом тестируйте»

**Файл:** `frontend/components/settings/MCPConnectionForm.tsx:198-201` (`disabled` button «Тест» с toast при клике).

**Проблема:** Подсказка только в toast при клике. Нет tooltip на disabled-кнопке.

**Diff:**

```diff
   <Button
     type="button"
     onClick={handleTest}
     disabled={!initial?.id}
+    title={!initial?.id ? "Сохраните подключение, чтобы можно было его проверить" : undefined}
+    aria-describedby={!initial?.id ? "test-disabled-hint" : undefined}
     ...
   >
     Тест
   </Button>
+  {!initial?.id && (
+    <span id="test-disabled-hint" className="sr-only">
+      Сохраните подключение, чтобы можно было его проверить
+    </span>
+  )}
```

Можно убрать и сам toast про «сначала сохраните» — он избыточен с tooltip.

---

## HIGH-8 — Двойная высота карточек kind в MCPConnectionForm

**Файл:** `frontend/components/settings/MCPConnectionForm.tsx:299-302` (kind pair: Встроенный сервер / Прокси).

**Diff:**

```diff
-  <div className="flex gap-2">
-    <KindCard kind="embedded" ... />
-    <KindCard kind="proxy" ... />
+  <div className="grid grid-cols-2 gap-2">
+    <KindCard kind="embedded" className="min-h-[88px]" ... />
+    <KindCard kind="proxy" className="min-h-[88px]" ... />
   </div>
```

Тогда обе карточки одинаковой высоты, описания не «прыгают».

---

## HIGH-9 — Backend indicator на главной — пересмотр

**Файл:** `frontend/app/page.tsx:18-53` (`BackendIndicator`).

**Проблема:** `fixed bottom-3 right-3` маленький чип. Когда backend недоступен — пользователь не понимает, что делать, кроме как смотреть на красный квадрат.

**Решение:**
1. Когда `status === "ok"` — индикатор скрыть (либо очень бледный — 9px dot без текста; зелёный chip избыточен).
2. Когда `status === "unavailable"` — заменить на верхний баннер по аналогии с `ConnectionStatusBanner`, с кнопкой «↻ Повторить проверку».

См. полный спек в `05-component-additions.md` § BackendDownBanner.

---

## HIGH-10 — Header height pixel glitch

**Файлы:**
- `frontend/components/shell/Header.tsx:30` — `h-[52px]`
- `frontend/components/shell/AppShell.tsx:32` — `gridTemplateRows: "56px 1fr auto"`

**Diff (привести к одному значению):**

```diff
// AppShell.tsx
-  gridTemplateRows: "56px 1fr auto",
+  gridTemplateRows: "52px 1fr auto",
```

Или наоборот — поднять header до 56px и менять `h-[52px]` → `h-14`. Решение: **52px** — компактнее, ближе к Linear/Notion ритму. Меняй AppShell.

---

## LOW-1 — Native confirm() для удаления

**Файл:** `frontend/components/shell/SessionList.tsx:84` — `if (!window.confirm(...))`.

Заменяется на `UndoToast` pattern — полный спек в `05-component-additions.md` § UndoToast. Сюда вынесено для трекинга.

---

## Codemods (полу-автоматизация)

Можно прогнать через `jscodeshift` или просто `sed -i`:

```bash
# REM-4.a — «канал» как UI-label (НЕ затрагивает field name conn.channel)
# Только текстовые литералы:
rg -l 'aria-label="Выбор канала"' frontend/ | xargs sed -i 's/aria-label="Выбор канала"/aria-label="Выбор базы 1С"/g'
rg -l 'DropdownMenuLabel>Канал</' frontend/ | xargs sed -i 's/DropdownMenuLabel>Канал</DropdownMenuLabel>База 1С</g'

# REM-4.b — терминология
rg -l 'инструментов MCP' frontend/ | xargs sed -i 's/инструментов MCP/операций над базой 1С/g'
rg -l 'инструменты MCP' frontend/ | xargs sed -i 's/инструменты MCP/инструменты в 1С/g'
rg -l 'обработка MCP_Toolkit' frontend/ | xargs sed -i 's/обработка MCP_Toolkit/обработка-обработчик/g'
```

> **После любого codemod — обязательный `pnpm test` + ручная проверка изменённых страниц.** Особенно `e2e/` тесты, которые могут матчить старый текст.

---

## Дополнительно: scrollbar

**Файл:** `frontend/app/globals.css:28-34`

Если scrollbar хардкоднут (`#262626` / `#303030`) — заменить на токены:

```diff
 ::-webkit-scrollbar-thumb {
-  background: #262626;
+  background: var(--bd-2);
   border-radius: 6px;
-  border: 2px solid #0a0a0a;
+  border: 2px solid var(--bg-0);
 }
 ::-webkit-scrollbar-thumb:hover {
-  background: #303030;
+  background: var(--bd-3);
 }
```

В light-theme скроллбар станет тонким серым на песке — естественно.
