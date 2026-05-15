"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

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
      </div>

      <article className="space-y-8 text-[var(--fg)]">
        <section className="space-y-3">
          <h2 className="text-2xl font-semibold">Что это?</h2>
          <p className="text-[var(--fg-muted)] leading-relaxed">
            <strong className="text-[var(--fg)]">1С Аналитик</strong> — чат-консоль для
            бизнес-аналитиков 1С. Аналог ChatGPT, но специализированный под работу с базами 1С через
            MCP Toolkit. Вы задаёте вопросы на естественном языке — модель сама вызывает нужные
            инструменты 1С и формирует ответ.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Как это работает</h2>
          <ol className="space-y-3 text-[var(--fg-muted)] leading-relaxed pl-5 list-decimal">
            <li>
              Вы пишете вопрос: «Покажи документы ОПП за вчера»
            </li>
            <li>
              Backend передаёт запрос LLM-модели (GPT-4 / Claude / Xiaomi MiMo — на ваш выбор), вместе со
              списком доступных инструментов 1С
            </li>
            <li>
              LLM решает: «Нужен <code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">execute_query</code>»
              — и формирует запрос
            </li>
            <li>
              Backend вызывает MCP Toolkit, который выполняет запрос к вашей живой базе 1С
            </li>
            <li>
              Результат возвращается LLM, она форматирует ответ + строит inline-карточку (таблица /
              объект / журнал / метрика / ссылки / код)
            </li>
            <li>
              Вы видите ответ за ≤30 секунд + можете развернуть «trace» — увидеть какие именно
              инструменты вызывались
            </li>
          </ol>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Что вы получите</h2>
          <ul className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-disc">
            <li>
              <strong className="text-[var(--fg)]">Не нужно знать SQL/BSL</strong> — пишите на
              русском, модель сама формирует запросы
            </li>
            <li>
              <strong className="text-[var(--fg)]">6 типов карточек</strong> — таблицы с
              сортировкой/CSV, карточки объектов с реквизитами и ТЧ, журнал регистрации, метрики,
              ссылки «где используется», код BSL с подсветкой
            </li>
            <li>
              <strong className="text-[var(--fg)]">Несколько баз одновременно</strong> — переключайтесь
              между базами клиентов через канал-селектор в шапке
            </li>
            <li>
              <strong className="text-[var(--fg)]">История</strong> — все диалоги сохраняются,
              группируются по датам
            </li>
            <li>
              <strong className="text-[var(--fg)]">Анонимизация</strong> — тоггл в шапке скрывает
              реальные имена контрагентов/документов токенами вида <code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">[ORG-001]</code>
            </li>
            <li>
              <strong className="text-[var(--fg)]">Безопасность</strong> — модальное подтверждение
              перед опасными операциями (Удалить, Записать)
            </li>
            <li>
              <strong className="text-[var(--fg)]">Trace</strong> — для каждого ответа видны
              вызванные инструменты + кнопка «Скопировать как curl»
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Что нужно настроить (≈ 2 минуты)</h2>
          <ol className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-decimal">
            <li>
              <strong className="text-[var(--fg)]">MCP Toolkit</strong> — обработка для 1С, которая
              даёт API доступ к базе. Запустите EPF в вашей 1С на порту 6010 (или другом)
            </li>
            <li>
              <strong className="text-[var(--fg)]">LLM провайдер</strong> — endpoint
              OpenAI-совместимого API + ключ. Подойдёт OpenAI, Anthropic, локальная LM Studio,
              Xiaomi MiMo и т.п.
            </li>
            <li>
              <strong className="text-[var(--fg)]">Готово</strong> — задавайте вопросы
            </li>
          </ol>
          <p className="text-sm text-[var(--fg-muted)] italic mt-2">
            Пройдите мастер настройки на главной странице или зайдите в{" "}
            <Link href="/settings" className="text-blue-400 hover:underline">
              Настройки
            </Link>
            .
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Проверить что всё работает</h2>
          <p className="text-[var(--fg-muted)] leading-relaxed">
            Откройте{" "}
            <Link href="/status" className="text-blue-400 hover:underline">
              страницу диагностики
            </Link>
            {" "}— она показывает статус backend, базы данных, MCP-подключений и LLM в одном
            месте. Зелёные галки = всё работает, красный = смотрите подсказку рядом.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Безопасность данных</h2>
          <ul className="space-y-2 text-[var(--fg-muted)] leading-relaxed pl-5 list-disc">
            <li>
              <strong className="text-[var(--fg)]">API ключ LLM</strong> хранится в{" "}
              <code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">sessionStorage</code>{" "}
              браузера и удаляется при закрытии вкладки. На сервере не сохраняется
            </li>
            <li>
              <strong className="text-[var(--fg)]">Данные базы 1С</strong> не покидают вашу машину —
              приложение работает локально, MCP вызывает 1С через ваш собственный сервер
            </li>
            <li>
              <strong className="text-[var(--fg)]">Опасные операции</strong> (<code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">Удалить</code>,{" "}
              <code className="font-mono text-xs px-1 bg-[var(--bg-elevated)] rounded">Записать</code>) перехватываются — выводится подтверждение
            </li>
            <li>
              <strong className="text-[var(--fg)]">Чувствительные данные</strong> — включите toggle
              «Анонимизация» в шапке. Реальные имена будут заменены токенами
            </li>
          </ul>
        </section>

        <section className="pt-6 border-t border-[var(--border)]">
          <p className="text-xs text-[var(--fg-muted)]">
            Версия 1.0 · MIT License ·{" "}
            <a
              href="https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:underline"
            >
              GitHub
            </a>
          </p>
        </section>
      </article>
    </div>
  );
}
