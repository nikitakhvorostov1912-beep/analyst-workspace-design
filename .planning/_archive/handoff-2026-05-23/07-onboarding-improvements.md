# 07 · Onboarding — улучшения

`OnboardingDialog.tsx` уже **на 4 шагах с back/skip**. Базовый stepper работает. Что нужно — мелкие точечные улучшения.

---

## O-1 · Persist прогресса между перезагрузками

**Проблема:** если пользователь закрыл окно браузера во время onboarding — при следующем запуске начинает с шага 1.

**Решение:** сохранять `step`, `createdConnection.id`, `llmTestPassed`, `learnOn` в `localStorage`.

**Diff (`OnboardingDialog.tsx`):**

```diff
+ const LS_KEY = "analyst.onboarding-progress";
+
+ interface PersistedProgress {
+   step: Step;
+   createdConnectionId: string | null;
+   llmTestPassed: boolean;
+   learnOn: boolean;
+ }
+
+ function loadProgress(): PersistedProgress | null {
+   try {
+     const raw = window.localStorage.getItem(LS_KEY);
+     return raw ? JSON.parse(raw) : null;
+   } catch {
+     return null;
+   }
+ }
+
+ function saveProgress(p: PersistedProgress) {
+   try {
+     window.localStorage.setItem(LS_KEY, JSON.stringify(p));
+   } catch {}
+ }
+
+ function clearProgress() {
+   try {
+     window.localStorage.removeItem(LS_KEY);
+   } catch {}
+ }

 export function OnboardingDialog({ open, onComplete, onSkip }: OnboardingDialogProps) {
   const [step, setStep] = useState<Step>(1);
   /* ... */

-  useEffect(() => {
-    if (open) {
-      setStep(1);
-      setCreatedConnection(null);
-      /* ... reset все ... */
-    }
-  }, [open]);
+  useEffect(() => {
+    if (open) {
+      const saved = loadProgress();
+      if (saved) {
+        setStep(saved.step);
+        setLlmTestPassed(saved.llmTestPassed);
+        setLearnOn(saved.learnOn);
+        if (saved.createdConnectionId) {
+          // Reload connection details from backend
+          fetchConnection(saved.createdConnectionId).then((c) => {
+            setCreatedConnection(c);
+            setPingPassed(true);    // если в backend сохранён → значит test был пройден ранее
+          }).catch(() => {});
+        }
+      } else {
+        setStep(1);
+        setCreatedConnection(null);
+        /* ... reset все ... */
+      }
+    }
+  }, [open]);
+
+  // Persist при каждом изменении ключевого state
+  useEffect(() => {
+    if (!open) return;
+    saveProgress({
+      step,
+      createdConnectionId: createdConnection?.id ?? null,
+      llmTestPassed,
+      learnOn,
+    });
+  }, [step, createdConnection?.id, llmTestPassed, learnOn, open]);

   function handleComplete() {
     /* ... existing ... */
+    clearProgress();
     setOnboardingCompleted(true);
     onComplete(createdConnection?.id ?? null);
   }
 ```

И в `handleSkip`:

```diff
   function handleSkip() {
+    clearProgress();
     setOnboardingCompleted(true);
     onSkip();
   }
```

---

## O-2 · ResumeBanner на главной (если onboarding прерван)

**Проблема:** даже с автосейвом, если пользователь закрыл диалог через onPointerDownOutside? Нет — он preventDefault'нут. Но если просто закрыл вкладку — флаг `onboarding-completed` не выставлен. При следующем заходе onboarding откроется на сохранённом шаге. **Хорошо**.

Дополнительно: если у пользователя есть `loadProgress() !== null`, но `getOnboardingCompleted() === true` (он залип на «Готово!» и закрыл) — показать `MemoryHint`-стиль баннер на главной:

```tsx
// frontend/components/onboarding/OnboardingResumeBanner.tsx
"use client";
import Link from "next/link";

export function OnboardingResumeBanner({ progress, onDismiss }: ...) {
  if (!progress) return null;
  return (
    <div className="rounded-lg border border-[var(--accent-32)] bg-[var(--accent-08)] p-4 flex items-center gap-3">
      <div className="flex-1">
        <div className="text-sm font-medium">Завершите настройку</div>
        <div className="text-xs text-[var(--fg-3)] mt-0.5">
          Вы остановились на шаге {progress.step} из 4. Продолжите, чтобы получить максимум от приложения.
        </div>
      </div>
      <Button size="sm" onClick={onResume}>Продолжить →</Button>
      <button onClick={onDismiss} aria-label="Скрыть" className="text-[var(--fg-3)] hover:text-[var(--fg-1)]">✕</button>
    </div>
  );
}
```

Логика отображения — в `app/page.tsx`:
- `loadProgress()` существует И `getOnboardingCompleted()` true → показывать banner
- При dismiss — `clearProgress()` и не показывать больше

---

## O-3 · Welcome screen — индикатор «настройка не завершена»

Если из onboarding пользователь нажал «Пропустить» на любом шаге → на welcome показать:

```tsx
{!hasFullConfig && (
  <div className="rounded-md border border-dashed border-[var(--warning-40)] bg-[var(--warning-12)] p-3 text-sm flex items-center gap-2">
    <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />
    <span>Часть настроек пропущена — приложение может работать ограниченно.</span>
    <Link href="/settings" className="ml-auto text-[var(--accent)] hover:underline">Открыть настройки →</Link>
  </div>
)}
```

---

## O-4 · Шаг 3 (Обучение) — более конкретная копия

Текущий текст: «Когда функция будет готова, ваши прошлые чаты будут использованы автоматически» (`OnboardingDialog.tsx:237-241`) — звучит как «когда-нибудь».

**Diff:**

```diff
-      <div className="text-[13px] font-medium text-[var(--fg-1)]">
-        Готовим функцию обучения
-      </div>
-      <div className="text-xs text-[var(--fg-3)] mt-0.5 leading-relaxed">
-        Когда функция будет готова, ваши прошлые чаты будут использованы
-        автоматически. Сейчас включение запомнит ваш выбор — настройка
-        появится в Настройках → Обучение.
-      </div>
+      <div className="text-[13px] font-medium text-[var(--fg-1)]">
+        Опция сохранена
+      </div>
+      <div className="text-xs text-[var(--fg-3)] mt-0.5 leading-relaxed">
+        Когда обучение запустится, оно подхватит ваши прошлые ответы по
+        этой базе. Управлять можно в&nbsp;Настройки → Память &amp; Обучение.
+      </div>
```

Конкретнее и без «когда-нибудь».

---

## O-5 · Готово!-шаг — добавить «Что дальше»

`step === 4` сейчас показывает «Готово!» + одну кнопку «Начать работу».

Добавь 2–3 quick-start примера:

```tsx
{step === 4 && (
  <div className="space-y-5 animate-fade-up">
    <div>
      <CheckCircle2 icon ... />
      <DialogTitle>Готово!</DialogTitle>
      <p>{existing wording}</p>
    </div>

    {/* НОВОЕ — quick starts */}
    <div className="space-y-2">
      <div className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)]"
           style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}>
        Попробуйте начать с одного из вопросов:
      </div>
      {[
        "Расскажи про базу — какая конфигурация и сколько объектов",
        "Покажи последние документы за неделю",
        "Какие пользователи самые активные сегодня",
      ].map((q) => (
        <button
          key={q}
          onClick={() => handleStartWithQuestion(q)}
          className="w-full text-left px-3 py-2 rounded-md border border-[var(--bd-2)] bg-[var(--bg-2)]
                     hover:border-[var(--bd-3)] hover:bg-[var(--bg-3)] transition-colors text-[13px]"
        >
          {q}
        </button>
      ))}
    </div>

    <div className="flex items-center justify-between gap-2">
      <Button variant="ghost" size="sm" onClick={handleBack}>← Назад</Button>
      <Button className="flex-1" onClick={handleComplete}>Начать с пустого чата</Button>
    </div>
  </div>
)}
```

`handleStartWithQuestion(q)` — completes onboarding и сразу создаёт session с этим вопросом.

---

## O-6 · Step 3 (Обучение) — переименовать

Сейчас label `"Обучение"`. Лучше: `"Память"` — это более понятный термин для аналитика и согласуется с разделом `Settings → Memory`.

**Diff (`OnboardingDialog.tsx:26`):**

```diff
- const STEP_LABELS = ["База 1С", "Модель ИИ", "Обучение", "Готово"];
+ const STEP_LABELS = ["База 1С", "Модель ИИ", "Память", "Готово"];
```

И на самом шаге переименовать заголовок «Обучение на ваших чатах» → «Память по этой базе».

---

## Acceptance Onboarding

- [ ] Closing browser mid-onboarding и открытие заново → продолжает с того же шага.
- [ ] Если onboarding закрыт через skip — на welcome виден resume-banner.
- [ ] Шаг 4 показывает 3 quick-start examples.
- [ ] Шаг 3 называется «Память».
- [ ] При completion / skip — localStorage очищается.
