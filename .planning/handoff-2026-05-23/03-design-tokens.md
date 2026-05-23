# 03 · Design Tokens — additions & fixes

Этот документ покрывает **только то, что добавляется или меняется**. Существующий `frontend/styles/design-tokens.css` сохраняется как есть (там уже всё необходимое для tokens, theming, semantic colors, light/dark, brand stencil). Ниже — конкретные `diff` для добавления motion-токенов, info-цвета, focus-ring токена и code-syntax map.

---

## 1. Motion tokens (новые — расширяют существующие)

Сейчас в `design-tokens.css:69-74` есть:
```css
--t-micro: 150ms;
--t-normal: 200ms;
--t-large: 300ms;
--ease: cubic-bezier(0.4, 0, 0.2, 1);
```

**Добавить (в тот же `:root` блок, сразу после `--ease`):**

```css
/* === Motion — extended (handoff 2026-05-23) =============================== */
--t-micro: 100ms;              /* был 150ms — для micro-hover нужно быстрее */
--t-fast: 160ms;               /* НОВЫЙ — color/opacity transitions */
--t-normal: 240ms;             /* был 200ms — panels, popovers */
--t-slow: 420ms;               /* НОВЫЙ — page enter, layout */

/* Easings */
--ease: cubic-bezier(0.32, 0.72, 0, 1);            /* НОВЫЙ default — было tailwind default */
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);          /* НОВЫЙ — enter animations */
--ease-spring: cubic-bezier(0.5, 1.4, 0.45, 1);     /* НОВЫЙ — chip pop, send button */

/* Backwards-compat — старый --ease как алиас, чтобы код не сломался */
--ease-design-ease: var(--ease);
--duration-micro: var(--t-micro);
--duration-normal: var(--t-normal);
--duration-large: var(--t-slow);
```

> **Внимание:** `--ease-design-ease` упоминается в `StreamingStages.tsx:117,144` и `OnboardingDialog.tsx:51,61`. Сохраняем как алиас на новый default `--ease`. Не удаляем.

---

## 2. Info color (НОВЫЙ — для нейтральных info-состояний)

Сейчас в дизайне нет голубого "info" tone — приходится использовать accent для подсказок, что путает с CTA. Добавляем info как 5-й semantic.

**В `:root`:**
```css
/* Info — neutral hint colour, не путать с accent (CTA) */
--info: #5fb8ff;
--info-12: rgba(95, 184, 255, 0.12);
--info-20: rgba(95, 184, 255, 0.20);
--info-40: rgba(95, 184, 255, 0.40);
```

**В `[data-theme="light"]`:**
```css
--info: #1a73c4;
--info-12: rgba(26, 115, 196, 0.12);
--info-20: rgba(26, 115, 196, 0.20);
--info-40: rgba(26, 115, 196, 0.40);
```

**Применение:** подсказки в hint-блоках («Готовим функцию обучения» в Onboarding), inline-info в формах. **НЕ для CTA** (это всегда signal).

---

## 3. Focus-ring token (НОВЫЙ — для единообразия)

```css
:root {
  /* Focus ring — единый паттерн */
  --focus-ring: var(--accent);
  --focus-ring-offset: var(--bg-0);
  --focus-ring-width: 2px;
}
```

**Применение в Tailwind v4 `@theme inline`:**
```css
@theme inline {
  --color-focus-ring: var(--focus-ring);
}
```

Использовать в utility-классе:
```css
.focus-ring {
  @apply focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2;
  --tw-ring-color: var(--focus-ring);
  --tw-ring-offset-color: var(--focus-ring-offset);
}
```

И затем — `className="focus-ring"` на всех интерактивных элементах.

---

## 4. Code syntax tokens (НОВЫЕ — для json-tree)

Сейчас json-tree использует хардкод-цвета. После REM-1 — через токены ниже:

```css
/* Code syntax — используется в JsonTree, Markdown code blocks, TraceCard */
--syntax-string: var(--success);    /* mint  — стабильные данные */
--syntax-number: var(--accent);     /* signal — главный фокус (числа = метрики) */
--syntax-bool: var(--warning);      /* ochre  — состояние, признак */
--syntax-null: var(--fg-4);         /* dim    — отсутствие */
--syntax-key: var(--fg-3);          /* muted  — ключи объектов */
--syntax-error: var(--error);
--syntax-bracket: var(--fg-4);
```

**Применение в `json-tree.tsx` после REM-1:** заменить `text-[var(--success)]` на `text-[var(--syntax-string)]` для семантической ясности. (Это **необязательно**, если REM-1 уже сделан — можно оставить прямые semantic toкены.)

---

## 5. Skeleton shimmer токен (расширение существующего)

В `globals.css` уже есть `@keyframes streaming-shimmer` и класс `.shimmer-text`. Добавь дополнительно:

```css
/* В design-tokens.css :root */
--skeleton-bg-from: var(--bg-1);
--skeleton-bg-to: var(--bg-3);
```

Класс `.skeleton` (см. `04-motion-system.md` § Skeleton).

---

## 6. Lockup tokens — ничего не меняется

Уже есть `--lockup-slash`, `--lockup-version`, `--lockup-subtitle` для обеих тем. Оставить как есть.

---

## 7. Полный diff к `design-tokens.css`

Вот целевой diff для блока `:root` (только добавки):

```diff
 :root {
   /* ... существующие токены ... */

-  /* Animation timing */
-  --t-micro: 150ms;
-  --t-normal: 200ms;
-  --t-large: 300ms;
-  --ease: cubic-bezier(0.4, 0, 0.2, 1);
+  /* === Motion — extended ================================================== */
+  --t-micro: 100ms;                                       /* hover */
+  --t-fast: 160ms;                                        /* color/opacity */
+  --t-normal: 240ms;                                      /* panels, popovers */
+  --t-slow: 420ms;                                        /* page enter, layout */
+  --ease: cubic-bezier(0.32, 0.72, 0, 1);                 /* default */
+  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);              /* enter */
+  --ease-spring: cubic-bezier(0.5, 1.4, 0.45, 1);         /* chip pop, send */
+
+  /* Backwards-compat aliases */
+  --ease-design-ease: var(--ease);
+  --duration-micro: var(--t-micro);
+  --duration-normal: var(--t-normal);
+  --duration-large: var(--t-slow);
+
+  /* === Info color (5th semantic) ========================================== */
+  --info: #5fb8ff;
+  --info-12: rgba(95, 184, 255, 0.12);
+  --info-20: rgba(95, 184, 255, 0.20);
+  --info-40: rgba(95, 184, 255, 0.40);
+
+  /* === Focus ring ========================================================= */
+  --focus-ring: var(--accent);
+  --focus-ring-offset: var(--bg-0);
+
+  /* === Code syntax (json-tree, markdown code blocks) ====================== */
+  --syntax-string: var(--success);
+  --syntax-number: var(--accent);
+  --syntax-bool: var(--warning);
+  --syntax-null: var(--fg-4);
+  --syntax-key: var(--fg-3);
+  --syntax-error: var(--error);
+  --syntax-bracket: var(--fg-4);
+
+  /* === Skeleton ========================================================== */
+  --skeleton-bg-from: var(--bg-1);
+  --skeleton-bg-to: var(--bg-3);

   /* Density */
   --row-h: 36px;
   /* ... */
 }
```

Аналогично в `[data-theme="light"]` — добавить `--info` (#1a73c4) и `--focus-ring-offset: var(--bg-0)`. Skeleton наследуется.

---

## 8. Reduced motion

Добавь в самый конец `design-tokens.css` (или `globals.css`):

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

> Не использовать `@media (prefers-reduced-motion: reduce)` с `display: none` на анимациях — лучше «мгновенный финальный кадр».

---

## 9. Acceptance

После применения этого файла:

- [ ] В DevTools Computed Style на `:root` видны `--t-micro: 100ms`, `--ease-out`, `--ease-spring`, `--info: #5fb8ff`, `--focus-ring`, `--syntax-string`, `--skeleton-bg-from`.
- [ ] В `[data-theme="light"]` есть `--info: #1a73c4`.
- [ ] Существующие компоненты (`StreamingStages`, `OnboardingDialog`) **не сломались** — `--ease-design-ease` и `--duration-normal` остались как aliases.
- [ ] `prefers-reduced-motion: reduce` отключает все анимации (проверить через DevTools rendering panel).

См. `04-motion-system.md` для применения этих токенов в keyframes.
