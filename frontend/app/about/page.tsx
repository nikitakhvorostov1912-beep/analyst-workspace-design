"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, BookOpen } from "lucide-react";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { APP_VERSION } from "@/lib/version";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] px-6 py-8 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Link
          href="/"
          className="text-[var(--fg-muted)] hover:text-[var(--fg)] transition-colors flex items-center gap-1 text-sm"
        >
          <ArrowLeft size={16} />
          На главную
        </Link>
        <h1 className="text-lg font-semibold text-[var(--fg)]">О приложении</h1>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>

      <article className="space-y-8 text-[var(--fg)]">
        {/* CTA: переход в полноценный гайд */}
        <Link
          href="/guide"
          className="block rounded-md border border-[var(--accent-20)] bg-[var(--accent-08)] px-5 py-4 hover:bg-[var(--accent-12)] transition-colors group"
        >
          <div className="flex items-center gap-4">
            <BookOpen className="h-6 w-6 text-[var(--accent)] flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[15px] font-semibold text-[var(--fg-1)]">
                Полный гайд аналитика
              </div>
              <div className="text-[13px] text-[var(--fg-2)] mt-0.5">
                9 разделов: подключение к 1С · операции в базе · карточки · сценарии · диагностика · безопасность
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-[var(--fg-3)] group-hover:text-[var(--accent)] group-hover:translate-x-0.5 transition-all flex-shrink-0" />
          </div>
        </Link>

        <section className="space-y-3">
          <h2 className="text-2xl font-semibold">Что это?</h2>
          <p className="text-[var(--fg-muted)] leading-relaxed">
            <strong className="text-[var(--fg)]">1С Аналитик</strong> — чат с базой 1С на русском
            языке. Аналог ChatGPT, но вместо общих вопросов он отвечает по вашей базе:
            показывает документы, считает остатки, находит ошибки в журнале регистрации.
            Вы пишете вопрос — приложение само формирует запрос к 1С и показывает ответ
            таблицей или карточкой.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Как это работает</h2>
          <ol className="space-y-3 text-[var(--fg-muted)] leading-relaxed pl-5 list-decimal">
            <li>Вы пишете на русском: «Покажи документы ОПП за вчера»</li>
            <li>
              Приложение передаёт вопрос модели ИИ — она понимает, какие данные из 1С нужны.
            </li>
            <li>
              Модель формирует запрос к 1С автоматически (вам не нужно знать SQL или язык
              запросов 1С).
            </li>
            <li>
              1С возвращает данные, модель оформляет их таблицей, карточкой документа,
              графиком или списком ссылок «где используется».
            </li>
            <li>
              Вы получаете ответ обычно за 5–30 секунд. Можно развернуть «трассировку»,
              чтобы увидеть, какие именно операции выполнила модель.
            </li>
          </ol>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Что вы получите</h2>
          <ul className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-disc">
            <li>
              <strong className="text-[var(--fg)]">Не нужно знать SQL или BSL</strong> —
              пишете на русском, модель сама формирует запросы.
            </li>
            <li>
              <strong className="text-[var(--fg)]">6 типов ответов</strong> — таблицы (с
              сортировкой и выгрузкой в CSV), карточки объектов с реквизитами и табличными
              частями, журнал регистрации, числовые метрики, список «где используется»,
              блоки кода с подсветкой.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Несколько баз</strong> — переключайтесь
              между базами клиентов в шапке.
            </li>
            <li>
              <strong className="text-[var(--fg)]">История</strong> — все диалоги
              сохраняются и группируются по датам.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Маскировка</strong> — переключатель в
              шапке скрывает реальные имена контрагентов и документов (заменяет на
              анонимные коды вроде <code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">[ORG-001]</code>).
              Полезно для скриншотов, переписки, ИТ-разбора.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Защита от случайностей</strong> — перед
              удалением или записью данных приложение спрашивает подтверждение.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Что нужно настроить (≈ 2 минуты)</h2>
          <ol className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-decimal">
            <li>
              <strong className="text-[var(--fg)]">Подключение к 1С</strong> — в вашей базе
              запускается специальная обработка-мост (EPF-файл, ставит ИТ-отдел) и слушает
              локальный порт (по умолчанию <span className="font-mono">6010</span>).
              Приложение само находит её — техническая часть скрыта.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Модель ИИ</strong> — введите API ключ
              вашего поставщика (OpenAI, Anthropic, Aitunnel, Xiaomi MiMo или локальная
              модель). Адрес и название модели уже подставлены по умолчанию.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Готово</strong> — задавайте вопросы.
            </li>
          </ol>
          <p className="text-sm text-[var(--fg-muted)] italic mt-2">
            Откройте{" "}
            <Link href="/settings" className="text-[var(--accent)] hover:underline">
              Настройки
            </Link>{" "}
            и заполните 2 секции. При первом запуске показывается мастер настройки.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Проверить что всё работает</h2>
          <p className="text-[var(--fg-muted)] leading-relaxed">
            Откройте{" "}
            <Link href="/status" className="text-[var(--accent)] hover:underline">
              страницу диагностики
            </Link>{" "}
            — там видно, доступна ли база 1С и модель ИИ. Зелёные галки = всё ок, оранжевый
            треугольник = смотрите подсказку рядом.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Безопасность данных</h2>
          <ul className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-disc">
            <li>
              <strong className="text-[var(--fg)]">API ключ модели</strong> хранится только
              на вашей машине, на сервер не отправляется. Один раз ввели — работает.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Данные базы 1С</strong> не покидают
              ваш контур — приложение работает локально, обращение к 1С идёт через ваш
              собственный сервер.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Опасные операции</strong> (удалить,
              записать) требуют явного подтверждения в диалоге.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Чувствительные данные</strong> —
              включите «Маскировка» в шапке. Реальные имена будут заменены на
              условные коды.
            </li>
          </ul>
        </section>

        <section className="pt-6 border-t border-[var(--border)]">
          <p className="text-xs text-[var(--fg-muted)]">
            Версия {APP_VERSION} · MIT License ·{" "}
            <a
              href="https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--accent)] hover:underline"
            >
              GitHub
            </a>
          </p>
        </section>
      </article>
    </div>
  );
}
