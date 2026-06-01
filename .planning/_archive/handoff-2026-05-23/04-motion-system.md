# 04 · Motion System

Восемь точек motion-применения. Все через CSS — без библиотек. Все respect `prefers-reduced-motion: reduce`. Длительности/easing — из токенов `03-design-tokens.md`.

---

## Принципы

1. **Никогда не блокировать UI анимацией.** Любая анимация — это «дорисовка», UI должен быть кликабелен в момент проигрывания.
2. **Длительность ≤ 500ms** для интерфейсных переходов. Исключение — loop-анимации (skeleton, pulse).
3. **Один тип движения за один момент времени.** Не комбинируем translate + scale + opacity на одном элементе — выбираем 1–2 свойства.
4. **Каждое CSS-keyframe определяется в `globals.css`** (там уже есть `fade-up`, `scale-in`, `dialog-in`, `blink`, `skeleton-pulse`, `streaming-shimmer`). **Не дублируй** их в компонентах.
5. **Reduced motion:** глобальный `@media (prefers-reduced-motion: reduce)` блок в `globals.css` (см. `03-design-tokens.md` § 8) выключает всё.

---

## M01 · Skeleton shimmer (loading)

**Цель:** заменить голый текст «Загрузка...» во всех местах.

**Места применения:**
- `frontend/app/page.tsx:174-180` (welcome loading)
- `frontend/app/sessions/[id]/page.tsx:188` (chat loading)
- `frontend/app/settings/page.tsx:78` (settings loading)
- `frontend/app/insights/page.tsx:84` (insights loading)

**CSS (в `globals.css`):**

```css
.skeleton {
  background: linear-gradient(
    90deg,
    var(--skeleton-bg-from) 0%,
    var(--skeleton-bg-to) 50%,
    var(--skeleton-bg-from) 100%
  );
  background-size: 200% 100%;
  border-radius: 4px;
  animation: skeleton-shimmer 1.6s linear infinite;
}

@keyframes skeleton-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

**Компонент:** `frontend/components/ui/Skeleton.tsx` (создать).

```tsx
"use client";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("skeleton", className)} {...props} />;
}
```

**Использование (вместо «Загрузка...»):**

```tsx
// chat loading state
<div className="flex flex-col gap-3 p-6 max-w-3xl mx-auto" data-testid="chat-loading">
  <Skeleton className="h-4 w-2/3" />
  <Skeleton className="h-4 w-full" />
  <Skeleton className="h-4 w-5/6" />
  <Skeleton className="h-32 w-full mt-6" />
</div>
```

**Acceptance:** ни в одном из четырёх loading-мест больше нет голого текста «Загрузка...».

---

## M02 · Streaming stages (улучшение существующего)

Компонент `StreamingStages` уже есть. Добавляем недостающее:

1. **Сценический entry** — каждая стадия появляется с `fade-up` (уже есть keyframe `@keyframes fade-up`).
2. **Pulse на активной стадии** для `tool` kind — уже есть `animate-blink` (см. `StreamingStages.tsx:151`).
3. **Smooth transition между стадиями** — `transition-all duration-normal ease-design-ease` (уже есть на L117).

**Что добавить:** stagger между стадиями (`animationDelay`).

**Diff (`StreamingStages.tsx:107-119`):**

```diff
   return (
     <div
       data-testid="streaming-stages"
       data-active-index={activeIndex}
       className={cn(
         "inline-flex flex-wrap items-center gap-1 px-3 py-2 rounded-lg bg-[var(--bg-1)] border border-[var(--bd-2)] text-xs animate-fade-up",
         className,
       )}
       role="status"
       aria-live="polite"
     >
       {stages.map((s, i) => {
         /* ... */
         return (
-          <span key={`stage-${i}`} className="inline-flex items-center gap-1">
+          <span
+            key={`stage-${i}`}
+            className="inline-flex items-center gap-1"
+            style={{ animation: `fade-up 280ms ${i * 80}ms var(--ease-out) both` }}
+          >
```

Stagger 80ms между стадиями — каждая следующая «вылетает» чуть позже.

---

## M03 · Sparkline draw-in

**Где:** `frontend/components/cards/Sparkline.tsx` (используется в MetricCard).

**Идея:** SVG `<path>` рисуется через `stroke-dasharray` + `stroke-dashoffset` анимацию. Линия «прорастает», а не вспыхивает.

**CSS (в `globals.css`):**

```css
@keyframes spark-draw {
  to { stroke-dashoffset: 0; }
}

@keyframes spark-fill-fade {
  to { opacity: 1; }
}

.spark-line {
  stroke-dasharray: var(--spark-len, 1000);
  stroke-dashoffset: var(--spark-len, 1000);
  animation: spark-draw 1.6s var(--ease-out) forwards;
}

.spark-fill {
  opacity: 0;
  animation: spark-fill-fade 1s 0.4s var(--ease-out) forwards;
}
```

**В `Sparkline.tsx`:**

```tsx
// Считаем длину линии через ref + getTotalLength() после mount:
const pathRef = useRef<SVGPathElement>(null);
useEffect(() => {
  if (pathRef.current) {
    const len = pathRef.current.getTotalLength();
    pathRef.current.style.setProperty('--spark-len', String(len));
  }
}, []);

return (
  <svg viewBox="...">
    <path ref={pathRef} className="spark-line" d={d} fill="none" stroke="var(--accent)" />
    <path className="spark-fill" d={areaD} fill="url(#sparkfill)" />
  </svg>
);
```

**Acceptance:** в MetricCard линия sparkline проигрывается один раз при mount, заливка появляется через 0.4 сек после старта линии.

---

## M04 · Send-flight (отправка сообщения)

**Где:** `frontend/components/chat/Input.tsx:432-447` (send button).

**Идея:** при клике — кнопка кратковременно сжимается, иконка стрелки «улетает» вверх, message появляется в thread с `fade-up`.

**CSS:**

```css
.send-flight {
  animation: send-press 240ms var(--ease-spring);
}

@keyframes send-press {
  0%   { transform: scale(1); }
  25%  { transform: scale(0.94); }
  60%  { transform: scale(1.04); }
  100% { transform: scale(1); }
}
```

**React (handler в Input.tsx):**

```tsx
function handleSubmit() {
  const btn = sendBtnRef.current;
  if (btn) {
    btn.classList.add('send-flight');
    btn.addEventListener('animationend', () => btn.classList.remove('send-flight'), { once: true });
  }
  // ... actual submit
}
```

**Bonus:** message при появлении в thread получает `animate-fade-up`. Уже работает в существующем коде — проверь, что у `<Message>` есть `animate-fade-up` класс.

---

## M05 · Connection pulse (статусы баз 1С)

**Где:** `StatusDot.tsx` — компонент уже есть. Анимация — уже есть в `design-tokens.css:226 @keyframes status-pulse`.

**Проверка:** у `StatusDot` с `status="online"` должна быть применена `animation: status-pulse 2s ease infinite`. Если нет — добавь.

**CSS (если не работает):**

```css
.status-online {
  background: var(--success);
  box-shadow: 0 0 0 0 var(--success-20);
  animation: status-pulse 2s ease infinite;
}

@keyframes status-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--success-20); }
  50%      { box-shadow: 0 0 0 4px var(--success-12); }
}

.status-connecting {
  background: var(--warning);
  animation: status-blink 1s linear infinite;
}

@keyframes status-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.3; }
}

.status-offline {
  background: var(--error);
  box-shadow: 0 0 0 4px var(--error-12);
  /* без анимации — статичный */
}
```

**Acceptance:** в Channel Selector у активной базы 1С с online-status зелёная точка пульсирует. У connecting (во время ping) — мигает. У offline — статика с error-12 ореолом.

---

## M06 · Drag-over composer

**Где:** `frontend/components/chat/Input.tsx:278-280` (drag-over state).

**Уже работает** через `ring-2 ring-[var(--accent)] ring-inset bg-[var(--accent-08)]`. Не хватает **плавности** — сейчас граница появляется мгновенно.

**Diff:**

```diff
   <div
     className={`relative flex flex-col gap-1.5 p-3
-      ${isDragOver ? "ring-2 ring-[var(--accent)] ring-inset rounded-md bg-[var(--accent-08)]" : ""}
+      transition-all duration-200 ease-out
+      ${isDragOver
+        ? "ring-2 ring-[var(--accent)] ring-inset rounded-md bg-[var(--accent-08)] scale-[1.005]"
+        : ""}
     `}
   ...>
```

Лёгкое `scale(1.005)` + transition даёт ощущение «упругого приёма».

---

## M07 · Sidebar collapse

**Где:** `frontend/components/shell/AppShell.tsx`.

**Идея:** sidebar сворачивается/разворачивается через grid-template-columns transition. Не дёргает контент в main.

**CSS:**

```css
.app-shell {
  display: grid;
  grid-template-columns: var(--sidebar-w, 260px) 1fr;
  transition: grid-template-columns 320ms var(--ease);
}

.app-shell[data-sidebar="collapsed"] {
  --sidebar-w: 56px;
}
```

**Sidebar contents fade:**

```tsx
<aside className="overflow-hidden">
  <div className="transition-opacity duration-200 ease-out"
       style={{ opacity: collapsed ? 0 : 1, pointerEvents: collapsed ? 'none' : 'auto' }}>
    {/* содержимое сайдбара */}
  </div>
</aside>
```

**State persistence:** сохрани collapsed в localStorage ключ `analyst.sidebar-collapsed`.

---

## M08 · Page enter (route transitions)

**Где:** между маршрутами `/`, `/sessions/[id]`, `/settings`, `/insights`, `/status`, `/about`, `/guide`.

**Идея:** при навигации main-контент проигрывает короткий `fade-up` (8px translate + opacity).

**Подход в Next.js App Router:** добавить `animate-fade-up` на главный wrapper в каждой странице. Уже частично сделано — `OnboardingDialog.tsx` использует `animate-fade-up`.

**Универсальное решение** — обёртка в AppShell:

```tsx
// AppShell.tsx
"use client";
import { usePathname } from "next/navigation";

export function AppShell({ children, ... }) {
  const pathname = usePathname();
  return (
    <div className="app-shell ...">
      <Header ... />
      <Sidebar ... />
      <main key={pathname} className="animate-fade-up ...">
        {children}
      </main>
    </div>
  );
}
```

`key={pathname}` заставит main-контент перемонтироваться при смене маршрута → анимация проиграется снова.

> **Caveat:** если в main есть тяжёлый state (chat history) — перемонтаж нежелателен. Тогда **не** делать key={pathname} на AppShell, а в каждой странице руками добавлять `<div className="animate-fade-up">`.

---

## M09 · Toast slide-in (UndoToast)

**Где:** новый компонент `UndoToast` (см. `05-component-additions.md`).

**CSS (в `globals.css`):**

```css
@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(40px) scale(0.96); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
}

@keyframes toast-out {
  to   { opacity: 0; transform: translateX(-50%) translateY(40px) scale(0.96); }
}

@keyframes toast-progress-shrink {
  from { width: 100%; }
  to   { width: 0; }
}

.toast-undo {
  animation: toast-in 280ms var(--ease-spring) both;
}
.toast-undo[data-state="closing"] {
  animation: toast-out 240ms var(--ease) both;
}
.toast-progress {
  animation: toast-progress-shrink var(--toast-duration, 5000ms) linear forwards;
}
```

---

## Integration map

| Motion | Применяется в | Status |
|---|---|---|
| M01 Skeleton | 4 loading-страницы | НОВЫЙ компонент |
| M02 Streaming stages | `chat/StreamingStages.tsx` | улучшение существующего |
| M03 Sparkline draw-in | `cards/Sparkline.tsx` | улучшение существующего |
| M04 Send-flight | `chat/Input.tsx` send button | улучшение существующего |
| M05 Connection pulse | `ui/StatusDot.tsx` | проверить и поправить |
| M06 Drag-over | `chat/Input.tsx` drop zone | улучшение существующего |
| M07 Sidebar collapse | `shell/AppShell.tsx` | НОВАЯ функция (есть кнопка, нет анимации) |
| M08 Page enter | каждая страница в `app/` | НОВАЯ |
| M09 Toast slide-in | `components/ui/UndoToast.tsx` | НОВЫЙ компонент |

---

## Acceptance

После всего этого:

- [ ] Loading-состояния — skeleton с shimmer (не «Загрузка...»)
- [ ] При streaming видны стадии с stagger animation
- [ ] Sparkline в MetricCard рисуется один раз при появлении
- [ ] Send button короткий spring press при клике
- [ ] Online-точка в Channel pulse, connecting — blink, offline — статика
- [ ] Composer при drag-over упруго подсвечивается signal-ring
- [ ] Sidebar collapse — плавная анимация ширины 320ms
- [ ] Между страницами короткий fade-up
- [ ] UndoToast — slide-up с progress bar
- [ ] При `prefers-reduced-motion: reduce` всё работает мгновенно (без транзишн-задержек)
