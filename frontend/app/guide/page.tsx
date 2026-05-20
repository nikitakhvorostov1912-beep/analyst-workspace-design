import type { Metadata } from "next";
import { GuideLayout, type GuideSection } from "@/components/guide/GuideLayout";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  ClipboardCopy,
  Code2,
  Database,
  EyeOff,
  FileText,
  HelpCircle,
  Info,
  KeyRound,
  Lightbulb,
  Network,
  Plug,
  Search,
  Sparkles,
  Square,
  Sun,
  Table2,
  Target,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Гайд аналитика — 1С Аналитик",
  description: "Полное руководство по работе с приложением: подключения, инструменты MCP, сценарии, диагностика.",
};

// ============================================================================
// Mini-helpers — переиспользуемые блоки внутри секций
// ============================================================================

function Lead({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[15px] leading-[1.7] text-[var(--fg-1)] mb-5">{children}</p>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[14px] leading-[1.7] text-[var(--fg-2)] mb-4">{children}</p>
  );
}

function H3({ children, id }: { children: React.ReactNode; id?: string }) {
  return (
    <h3
      id={id}
      className="scroll-mt-20 text-[16px] font-semibold text-[var(--fg-1)] mt-8 mb-3"
      style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
    >
      {children}
    </h3>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd
      className="inline-flex items-center px-1.5 py-0.5 rounded border border-[var(--bd-2)] bg-[var(--bg-2)] text-[11px] font-mono text-[var(--fg-1)] tabular-nums"
      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
    >
      {children}
    </kbd>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code
      className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] text-[12.5px] text-[var(--fg-1)] border border-[var(--bd-1)]"
      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
    >
      {children}
    </code>
  );
}

type CalloutVariant = "info" | "warning" | "tip" | "danger";

const CALLOUT_STYLES: Record<
  CalloutVariant,
  { bg: string; border: string; icon: React.ReactNode }
> = {
  info: {
    bg: "var(--accent-08)",
    border: "var(--accent-20)",
    icon: <Info className="h-4 w-4 text-[var(--accent)]" />,
  },
  warning: {
    bg: "var(--warning-12)",
    border: "var(--warning-20)",
    icon: <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />,
  },
  tip: {
    bg: "var(--success-12)",
    border: "var(--success-20)",
    icon: <Lightbulb className="h-4 w-4 text-[var(--success)]" />,
  },
  danger: {
    bg: "var(--error-12)",
    border: "var(--error-20)",
    icon: <AlertTriangle className="h-4 w-4 text-[var(--error)]" />,
  },
};

function Callout({
  variant = "info",
  children,
}: {
  variant?: CalloutVariant;
  children: React.ReactNode;
}) {
  const s = CALLOUT_STYLES[variant];
  return (
    <div
      className="my-5 rounded-md border px-4 py-3 flex gap-3"
      style={{ background: s.bg, borderColor: s.border }}
    >
      <div className="flex-shrink-0 mt-0.5">{s.icon}</div>
      <div className="text-[13.5px] leading-[1.65] text-[var(--fg-1)] [&>p]:m-0">
        {children}
      </div>
    </div>
  );
}

interface ToolCardProps {
  name: string;
  icon: React.ReactNode;
  purpose: string;
  whenToUse: string;
  example?: string;
  cardType?: string;
}

function ToolCard({ name, icon, purpose, whenToUse, example, cardType }: ToolCardProps) {
  return (
    <div className="my-4 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--bd-1)] flex items-center gap-3 bg-[var(--bg-2)]">
        <span className="text-[var(--accent)]">{icon}</span>
        <code
          className="text-[13px] font-medium text-[var(--fg-1)]"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {name}
        </code>
        {cardType && (
          <span
            className="ml-auto text-[10px] text-[var(--fg-3)] uppercase tracking-[0.12em]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            → {cardType}
          </span>
        )}
      </div>
      <div className="px-4 py-3 space-y-2">
        <div>
          <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-3)] font-medium">
            Что делает:{" "}
          </span>
          <span className="text-[13px] text-[var(--fg-1)]">{purpose}</span>
        </div>
        <div>
          <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-3)] font-medium">
            Когда:{" "}
          </span>
          <span className="text-[13px] text-[var(--fg-2)]">{whenToUse}</span>
        </div>
        {example && (
          <div className="pt-2 mt-2 border-t border-[var(--bd-1)]">
            <div className="text-[11px] uppercase tracking-[0.12em] text-[var(--fg-3)] font-medium mb-1">
              Аналитик пишет:
            </div>
            <div
              className="text-[13px] text-[var(--fg-1)] italic"
              style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
            >
              «{example}»
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface ScenarioProps {
  title: string;
  ask: string;
  whatHappens: string[];
  result: string;
}

function Scenario({ title, ask, whatHappens, result }: ScenarioProps) {
  return (
    <div className="my-5 rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
      <div className="px-4 py-2.5 border-b border-[var(--bd-1)] bg-[var(--bg-2)] flex items-center gap-2">
        <Target className="h-3.5 w-3.5 text-[var(--accent)]" />
        <span className="text-[13px] font-medium text-[var(--fg-1)]">{title}</span>
      </div>
      <div className="px-4 py-3 space-y-3">
        <div>
          <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-3)] font-medium mb-1">
            Вы пишете:
          </div>
          <div
            className="text-[14px] text-[var(--fg-1)] italic pl-3 border-l-2 border-[var(--accent)]"
            style={{ fontFamily: "var(--font-plex-sans), system-ui" }}
          >
            «{ask}»
          </div>
        </div>
        <div>
          <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-3)] font-medium mb-1.5">
            Что под капотом:
          </div>
          <ol className="space-y-1 pl-5 list-decimal text-[13px] text-[var(--fg-2)]">
            {whatHappens.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
        <div className="pt-2 border-t border-[var(--bd-1)]">
          <div className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--fg-3)] font-medium mb-1">
            Что увидите:
          </div>
          <div className="text-[13px] text-[var(--fg-1)]">{result}</div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// SECTIONS
// ============================================================================

const SECTIONS: GuideSection[] = [
  // ----------------------------------------------------------------------
  // 1. С чего начать
  // ----------------------------------------------------------------------
  {
    id: "start",
    title: "С чего начать",
    content: (
      <>
        <Lead>
          1С Аналитик — это чат с базой 1С. Вы пишете вопрос на русском —
          приложение само формирует запрос к 1С и показывает ответ таблицей,
          карточкой документа или графиком. Без знаний SQL и языка запросов 1С.
        </Lead>

        <H3>За 3 минуты до первого вопроса</H3>
        <ol className="space-y-3 pl-5 list-decimal text-[14px] text-[var(--fg-2)] leading-[1.6] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Откройте Настройки</strong>{" "}
            (шестерёнка в правом верхнем углу) и добавьте подключение к вашей
            базе 1С. Подробности — раздел{" "}
            <a href="#connections" className="text-[var(--accent)] hover:underline">
              «Подключения к 1С»
            </a>
            .
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Введите API-ключ модели ИИ</strong>{" "}
            на той же странице. Адрес и название модели уже подставлены по умолчанию
            (Xiaomi MiMo v2.5 Pro).
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Выберите канал в шапке</strong> —
            это и есть выбор базы. Если подключение одно — оно подставится автоматически.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Задайте первый вопрос</strong> — внизу
            экрана. Например: «Какие документы есть в базе?»
          </li>
        </ol>

        <Callout variant="tip">
          <strong>Первый вопрос для разогрева:</strong>{" "}
          <em>«Покажи список справочников и сколько в каждом записей»</em> — даёт ясный
          обзор за 10 секунд, без вреда для базы (только чтение метаданных).
        </Callout>

        <H3>Что увидите на экране</H3>
        <ul className="space-y-2 pl-5 list-disc text-[14px] text-[var(--fg-2)] leading-[1.6] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Слева</strong> — список ваших
            сессий (диалогов), сгруппированных по датам. «Сегодня», «Вчера»,
            «На этой неделе».
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">В центре</strong> — текущий диалог
            и поле ввода. Сюда можно перетаскивать файлы и картинки.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Сверху</strong> — переключатель
            базы, индикатор модели, маскировка PII, иконки диагностики и настроек.
          </li>
        </ul>

        <Callout variant="info">
          Прочитайте раздел{" "}
          <a href="#scenarios" className="text-[var(--accent)] hover:underline">
            «Сценарии работы»
          </a>{" "}
          — 6 живых примеров запросов с пояснением, что делает приложение под
          капотом. Самый быстрый способ понять, что можно спрашивать.
        </Callout>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 2. Подключения к 1С (MCP)
  // ----------------------------------------------------------------------
  {
    id: "connections",
    title: "Подключения к 1С",
    content: (
      <>
        <Lead>
          Чтобы приложение могло читать вашу базу, оно подключается к ней через{" "}
          <strong>MCP</strong> — это специальный сервис, который запускается рядом с 1С
          и переводит запросы из приложения в команды для 1С.
        </Lead>

        <H3>Два режима подключения</H3>
        <P>
          В шапке рядом с названием базы вы видите бейдж типа подключения. Их два:
        </P>

        <div className="my-5 space-y-4">
          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[var(--bd-1)] bg-[var(--accent-08)] flex items-center gap-2">
              <Plug className="h-4 w-4 text-[var(--accent)]" />
              <span className="text-[13px] font-semibold text-[var(--fg-1)]">
                Локально (Встроенный сервер)
              </span>
            </div>
            <div className="px-4 py-3 text-[13.5px] text-[var(--fg-2)] leading-[1.6] space-y-2">
              <p>
                MCP-сервер запущен на той же машине, где работает 1С. Адрес обычно{" "}
                <Code>http://localhost:6010/mcp</Code>.
              </p>
              <p>
                <strong className="text-[var(--fg-1)]">Когда:</strong> вы работаете
                с базой клиента непосредственно на его сервере или у себя локально.
                Самый быстрый и надёжный путь. Данные базы не покидают контур.
              </p>
              <p>
                <strong className="text-[var(--fg-1)]">Как настраивает ИТ:</strong>{" "}
                в базе запускается внешняя обработка{" "}
                <Code>MCP_Toolkit_v1.7.0.epf</Code> → «Встроенный сервер» → «Запустить».
                Порт по умолчанию <Code>6010</Code>.
              </p>
            </div>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] overflow-hidden">
            <div
              className="px-4 py-2.5 border-b border-[var(--bd-1)] flex items-center gap-2"
              style={{ background: "rgba(168, 85, 247, 0.10)" }}
            >
              <Network className="h-4 w-4" style={{ color: "rgb(168, 85, 247)" }} />
              <span className="text-[13px] font-semibold text-[var(--fg-1)]">
                Прокси (Hugging Face Spaces)
              </span>
            </div>
            <div className="px-4 py-3 text-[13.5px] text-[var(--fg-2)] leading-[1.6] space-y-2">
              <p>
                Подключение идёт через прокси-сервер. Адрес —{" "}
                <Code>https://nikoiuy12-mcp-proxy.hf.space/mcp?channel=…</Code>.
              </p>
              <p>
                <strong className="text-[var(--fg-1)]">Когда:</strong> 1С базы клиента
                не доступна с вашей машины напрямую (другая сеть, VPN, удалённое
                подключение). У базы есть «канал» — короткое имя, через которое
                прокси находит конкретную базу среди нескольких.
              </p>
              <p>
                <strong className="text-[var(--fg-1)]">Что важно:</strong> данные
                идут через внешний прокси. Используйте только когда локальный режим
                невозможен. И обязательно включайте{" "}
                <a href="#chat-features" className="text-[var(--accent)] hover:underline">
                  маскировку
                </a>
                .
              </p>
            </div>
          </div>
        </div>

        <H3>Индикаторы статуса</H3>
        <P>
          Рядом с каждым подключением — цветная точка. Это не декорация, это реальный
          статус подключения:
        </P>
        <ul className="my-4 space-y-2.5 text-[13.5px] text-[var(--fg-2)] leading-[1.6]">
          <li className="flex items-start gap-2.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--success)] mt-1.5 flex-shrink-0" />
            <span>
              <strong className="text-[var(--fg-1)]">Зелёная (пульсирует)</strong> —
              онлайн. Последний ping прошёл, доступно N инструментов.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--warning)] mt-1.5 flex-shrink-0 animate-pulse" />
            <span>
              <strong className="text-[var(--fg-1)]">Жёлтая (мигает)</strong> — идёт
              проверка. Несколько секунд — нормально.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--error)] mt-1.5 flex-shrink-0" />
            <span>
              <strong className="text-[var(--fg-1)]">Красная</strong> — нет связи.
              Проверьте: запущена ли обработка в 1С, не закрыли ли вы её, не сменили
              ли порт.
            </span>
          </li>
          <li className="flex items-start gap-2.5">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--fg-4)] mt-1.5 flex-shrink-0" />
            <span>
              <strong className="text-[var(--fg-1)]">Серая</strong> — статус
              неизвестен (только что добавили подключение, ping ещё не запускался).
              Кликните по подключению — проверка запустится.
            </span>
          </li>
        </ul>

        <H3>Когда что-то идёт не так</H3>
        <P>
          Если связи нет — откройте{" "}
          <a href="#diagnostics" className="text-[var(--accent)] hover:underline">
            страницу диагностики
          </a>{" "}
          (значок графика в шапке). Там для каждого подключения видны: адрес, тип, ping,
          сколько инструментов отвечают и точная причина ошибки, если она была.
        </P>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 3. Инструменты MCP (что умеет помощник)
  // ----------------------------------------------------------------------
  {
    id: "mcp-tools",
    title: "Инструменты MCP",
    content: (
      <>
        <Lead>
          Под капотом приложение использует 10 инструментов MCP Toolkit и
          дополнительно справочник по платформе. Вам их вызывать вручную не нужно
          — модель сама решает, какой инструмент применить под ваш вопрос. Но
          понимать, что доступно, полезно: тогда вы знаете, о чём в принципе
          можно спрашивать.
        </Lead>

        <H3>Как читать описания</H3>
        <P>
          В таблице ниже у каждого инструмента — назначение, типичный пример вопроса
          от аналитика, и то, в виде какой карточки появится ответ в чате.
        </P>

        <H3 id="tool-get-metadata">Структура базы</H3>
        <ToolCard
          name="get_metadata"
          icon={<Database className="h-4 w-4" />}
          purpose="Список объектов конфигурации: справочники, документы, регистры, отчёты, обработки, перечисления, константы, роли, подсистемы, общие модули. Можно посмотреть конкретный объект целиком — с реквизитами, табличными частями, формами."
          whenToUse="«какие документы в базе», «структура справочника Контрагенты», «есть ли в базе регистр X», «какие реквизиты у документа Y»"
          example="Покажи структуру документа РеализацияТоваровУслуг"
          cardType="Object"
        />

        <H3 id="tool-execute-query">Запросы к данным</H3>
        <ToolCard
          name="execute_query"
          icon={<Search className="h-4 w-4" />}
          purpose="Реальный запрос на языке 1С к данным базы. Только чтение (SELECT). Используется для подсчётов, выборок, агрегатов, поиска по реквизитам. Всегда с лимитом строк."
          whenToUse="«сколько контрагентов с ИНН на 77», «топ-10 поставщиков по сумме закупок за квартал», «остатки на складе X», «средний срок оплаты по клиенту»"
          example="Покажи последние 20 реализаций за неделю с суммой больше 100 тысяч"
          cardType="Table или Metric"
        />

        <H3 id="tool-get-event-log">Журнал регистрации</H3>
        <ToolCard
          name="get_event_log"
          icon={<FileText className="h-4 w-4" />}
          purpose="События из журнала регистрации 1С: ошибки, предупреждения, действия пользователей, проведение документов. С фильтрами по времени, важности, пользователю, объекту."
          whenToUse="«что случилось вчера в 14:30», «есть ли ошибки за последний час», «кто записал документ X», «почему документ Y не провёлся»"
          example="Покажи ошибки за вчера у пользователя Иванова"
          cardType="Log"
        />

        <H3 id="tool-object-link">Конкретный объект</H3>
        <ToolCard
          name="get_object_by_link"
          icon={<Info className="h-4 w-4" />}
          purpose="Получить конкретный документ или элемент справочника по навигационной ссылке (вида e:1cv8s://… или Документ.X:UUID). Возвращает все реквизиты, табличные части, движения."
          whenToUse="«покажи документ по этой ссылке», «что в табличной части Товары у этого документа», «какие движения по регистру у заказа X»"
          example="Открой документ по ссылке e:1cv8s://localhost/ut_rt_copy/data?ref=…"
          cardType="Object"
        />

        <ToolCard
          name="get_link_of_object"
          icon={<ClipboardCopy className="h-4 w-4" />}
          purpose="Обратное действие: получить навигационную ссылку по описанию объекта (тип + ключевые реквизиты). Помогает зацепиться за нужный документ, когда есть только номер или ИНН."
          whenToUse="«дай ссылку на документ Реализация № 0042 от 12.03», «ссылка на контрагента с ИНН 7707083893»"
          example="Дай навигационную ссылку на заказ покупателя номер РТ-00012"
          cardType="—"
        />

        <H3 id="tool-references">Где используется объект</H3>
        <ToolCard
          name="find_references_to_object"
          icon={<Network className="h-4 w-4" />}
          purpose="Найти, где объект конфигурации (реквизит, общий модуль, регистр) используется в коде, формах, ролях. Группирует по типу использования: чтение, запись, отображение."
          whenToUse="«где используется реквизит X», «можно ли удалить общий модуль Y», «какие формы зависят от справочника Z»"
          example="Где в конфигурации используется реквизит ИНН справочника Контрагенты?"
          cardType="References"
        />

        <H3 id="tool-access-rights">Права доступа</H3>
        <ToolCard
          name="get_access_rights"
          icon={<KeyRound className="h-4 w-4" />}
          purpose="Права роли или конкретного пользователя на объект конфигурации: чтение, изменение, добавление, удаление, проведение."
          whenToUse="«какие права у роли Менеджер», «может ли пользователь Иванов проводить реализации», «кто имеет доступ к Кассовым операциям»"
          example="Какие права у роли БухгалтерУУ на документ Списание с расчётного счёта?"
          cardType="Table"
        />

        <H3 id="tool-execute-code">BSL-код</H3>
        <ToolCard
          name="execute_code"
          icon={<Code2 className="h-4 w-4" />}
          purpose="Выполнить произвольный код на BSL (язык 1С). Используется, когда задача не выражается обычным запросом — например, вызвать процедуру модуля, посчитать что-то с использованием функций платформы. Опасные операции (запись/удаление) требуют явного подтверждения."
          whenToUse="«перепроведи документ X», «вызови процедуру обновления остатков», «посчитай через функцию Y» — то что нельзя SELECT-запросом"
          example="Вызови ОбщегоНазначения.ТекущаяДатаСеанса() и покажи результат"
          cardType="Code (с inline-результатом)"
        />

        <Callout variant="warning">
          <strong>Безопасность по умолчанию:</strong> приложение всегда спрашивает
          подтверждение перед выполнением BSL-кода, который меняет данные.
          Просто чтение функций — без подтверждения.
        </Callout>

        <H3 id="tool-bsl-syntax">Справка по BSL и платформе</H3>
        <ToolCard
          name="get_bsl_syntax_help"
          icon={<FileText className="h-4 w-4" />}
          purpose="Справочник по встроенному языку и API платформы 1С: сигнатура функции, параметры, описание, примеры использования."
          whenToUse="«как вызвать ЗначениеЗаполнено», «какие параметры у ЗаписьЖурналаРегистрации», «что возвращает ОбщегоНазначения.ТекущаяДатаСеанса»"
          example="Покажи описание функции ОбщегоНазначения.ЗначениеРеквизитаОбъекта"
          cardType="Code"
        />

        <ToolCard
          name="submit_for_deanonymization"
          icon={<EyeOff className="h-4 w-4" />}
          purpose="Когда включена маскировка, приложение показывает условные коды вместо реальных имён. Этот инструмент позволяет модели вернуться к реальным значениям — но только локально, для дальнейших шагов рассуждения. Видимый текст ответа всё равно маскирован."
          whenToUse="Автоматически. Аналитику не нужно вызывать руками."
          cardType="—"
        />

        <H3 id="aux-bsl-context">Дополнительно: справочник API платформы</H3>
        <P>
          Рядом с инструментами MCP подключён вспомогательный справочник{" "}
          <Code>bsl-context</Code> — детальная база по API платформы 1С (8.3.x):
          типы, методы, свойства, конструкторы. Модель использует её, когда не
          уверена в точной сигнатуре платформенной функции.
        </P>
        <Callout variant="info">
          Этот справочник опционален: даже если он показан как «не подключён» на{" "}
          <a href="#diagnostics" className="text-[var(--accent)] hover:underline">
            странице диагностики
          </a>
          , приложение работает. Просто иногда модель будет менее уверена в
          платформенных вызовах.
        </Callout>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 4. Карточки в чате
  // ----------------------------------------------------------------------
  {
    id: "cards",
    title: "Карточки в чате",
    content: (
      <>
        <Lead>
          Ответы приходят не голым текстом, а структурированно. Под текстом ответа
          появляется одна или несколько карточек — таблица, объект, журнал, метрика
          и так далее. Карточки можно сортировать, копировать, выгружать.
        </Lead>

        <div className="my-6 space-y-3">
          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Table2 className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Table</h4>
              <span className="text-[11px] text-[var(--fg-3)]">Таблица</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Когда ответ — список строк (документы, контрагенты, остатки). Поддерживает
              сортировку по колонкам, копирование строки, выгрузку в CSV. Длинные
              значения обрезаются и раскрываются по клику.
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Info className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Object</h4>
              <span className="text-[11px] text-[var(--fg-3)]">Объект 1С</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Конкретный документ или элемент справочника со всеми реквизитами,
              табличными частями и движениями. Каждая ТЧ — отдельная свёрнутая
              секция, разворачивается кликом.
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Log</h4>
              <span className="text-[11px] text-[var(--fg-3)]">Журнал регистрации</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              События с уровнями (ошибка / предупреждение / информация / примечание),
              иконками и фильтром по уровню. Раскрытие записи показывает полный
              комментарий и связанные данные.
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Metric</h4>
              <span className="text-[11px] text-[var(--fg-3)]">Метрика</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Когда ответ — одно число с контекстом: «остаток на складе», «сумма за
              месяц», «количество документов». При наличии истории — мини-график
              изменений во времени (timeline).
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Network className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">References</h4>
              <span className="text-[11px] text-[var(--fg-3)]">Где используется</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Список ссылок «где этот объект используется», сгруппированный по типу
              использования: чтение в коде, запись, отображение на формах, в ролях,
              в подсистемах. Полезно перед рефакторингом или удалением объекта.
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Code2 className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Code</h4>
              <span className="text-[11px] text-[var(--fg-3)]">BSL / SQL / JSON</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Подсветка синтаксиса, кнопка копирования. Длинные блоки (более 6
              строк) свёрнуты по умолчанию с кнопкой «Показать N строк». Для
              исполнимых блоков — inline-результат выполнения.
            </p>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4 text-[var(--accent)]" />
              <h4 className="text-[14px] font-semibold text-[var(--fg-1)]">Chart</h4>
              <span className="text-[11px] text-[var(--fg-3)]">График</span>
            </div>
            <p className="text-[13px] text-[var(--fg-2)] leading-[1.6]">
              Pie, Bar или Line. Когда вопрос предполагает визуализацию — «динамика
              продаж по месяцам», «доли поставщиков». Модель сама выбирает тип графика.
              Tooltip показывает точные значения.
            </p>
          </div>
        </div>

        <H3>Трассировка</H3>
        <P>
          Под каждым ответом можно развернуть «трассировку» — увидеть, какие именно
          инструменты модель вызывала, с какими параметрами, что вернулось. Это
          неинвазивно: можете не смотреть, но для аудита и понимания — ценно.
        </P>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 5. Возможности чата
  // ----------------------------------------------------------------------
  {
    id: "chat-features",
    title: "Возможности чата",
    content: (
      <>
        <Lead>
          Помимо текстовых вопросов и таблиц-ответов, в чате доступно несколько
          специальных возможностей.
        </Lead>

        <H3 id="feat-files">Прикрепление файлов</H3>
        <P>
          Перетащите файл в окно чата или нажмите скрепку в поле ввода. Поддерживаются:
        </P>
        <ul className="my-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13.5px] text-[var(--fg-2)]">
          <li>• <Code>PDF</Code> — извлекается текст</li>
          <li>• <Code>DOCX</Code> — текст из Word</li>
          <li>• <Code>XLSX</Code> — таблицы Excel</li>
          <li>• <Code>CSV</Code> — табличные данные</li>
          <li>• <Code>TXT</Code> — любой простой текст</li>
        </ul>
        <P>
          Прикреплённый файл становится частью вопроса — модель видит его содержимое
          и может сопоставить с данными базы. Полезно для актов сверки, шаблонов
          договоров, выгрузок из других систем.
        </P>

        <H3 id="feat-vision">Картинки и скриншоты</H3>
        <P>
          PNG и JPG распознаются моделью с поддержкой зрения (Vision). Можно
          приложить скриншот ошибки 1С, фото бумажного документа, схему — и
          спросить про неё.
        </P>
        <Callout variant="tip">
          Когда приложите картинку, модель автоматически переключится на multimodal-вариант
          (например, <Code>mimo-v2-omni</Code>), который умеет с изображениями. Это
          происходит прозрачно — вам ничего делать не нужно.
        </Callout>

        <H3 id="feat-masking">Маскировка (анонимизация)</H3>
        <P>
          Переключатель «Маскировка» в шапке. Когда включён — приложение в выводимом
          тексте и карточках заменяет реальные имена контрагентов, номера документов
          и другие персональные данные на условные коды вида <Code>[ORG-001]</Code>,{" "}
          <Code>[DOC-042]</Code>.
        </P>
        <P>Используйте, когда:</P>
        <ul className="my-3 space-y-1.5 pl-5 list-disc text-[13.5px] text-[var(--fg-2)]">
          <li>Делаете скриншот для документации или презентации</li>
          <li>Передаёте чат коллеге для разбора</li>
          <li>Работаете через прокси-подключение</li>
          <li>Подключены к чужой базе и не хотите случайно сохранить реальные имена</li>
        </ul>

        <H3 id="feat-export">Экспорт чата</H3>
        <P>
          В шапке открытой сессии — кнопка <Kbd>↓ Экспорт</Kbd>. Скачивает весь
          диалог как Markdown-файл: вопросы, ответы, JSON-параметры инструментов,
          результаты, рассуждения модели. Удобно отправить разработчику, если ответы
          модели кажутся неточными.
        </P>

        <H3 id="feat-charts">Графики прямо в чате</H3>
        <P>
          Если модель отвечает блоком кода с пометкой <Code>chart</Code> и
          JSON-описанием, приложение рендерит график (Pie / Bar / Line). Просите явно:
          «покажи в виде графика», «нарисуй pie-диаграмму», «динамика по месяцам линией».
        </P>

        <H3 id="feat-sessions">История сессий</H3>
        <P>
          Слева — все ваши диалоги. Группируются по датам. По каждой сессии видно
          название (автоматически генерируется по первому вопросу) и время последнего
          сообщения. Сессии переключаются мгновенно, история сохраняется навсегда.
        </P>

        <H3 id="feat-theme">Светлая и тёмная темы</H3>
        <P>
          В правом верхнем углу — иконка <Sun className="inline h-3.5 w-3.5" /> /{" "}
          <Code>Moon</Code>. По умолчанию — тёмная (Ink). Светлая (Sand) — для печати
          или работы в светлом окружении. Выбор запоминается на этом устройстве.
        </P>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 6. Сценарии работы
  // ----------------------------------------------------------------------
  {
    id: "scenarios",
    title: "Сценарии работы",
    content: (
      <>
        <Lead>
          6 живых сценариев — от простых поисковых вопросов до многоступенчатых
          расследований. Каждый со звучным запросом, описанием того, что под
          капотом делает приложение, и видом результата.
        </Lead>

        <Scenario
          title="1. Найти документ по номеру или контрагенту"
          ask="Найди реализацию для контрагента ООО Ромашка за март"
          whatHappens={[
            "Модель вызывает execute_query с фильтром по Контрагент.Наименование = «Ромашка» и Дата в диапазоне марта",
            "Получает список документов (5–20 строк)",
            "Возвращает таблицей с колонками: Номер, Дата, Сумма, Статус",
          ]}
          result="Таблица (Table) с возможностью отсортировать по сумме и скопировать ссылку на нужный документ"
        />

        <Scenario
          title="2. Понять структуру незнакомой базы"
          ask="Какие основные документы и регистры в этой базе?"
          whatHappens={[
            "Модель последовательно вызывает get_metadata для meta_type=Документ, потом для РегистрНакопления, потом для РегистрСведений",
            "Каждый ответ — список объектов с краткими описаниями",
            "Модель формирует обзор: «основные документы такие-то, регистры накопления отслеживают X и Y…»",
          ]}
          result="Текстовый обзор + Object-карточки для каждой ключевой подсистемы"
        />

        <Scenario
          title="3. Разобраться, почему документ не проводится"
          ask="Документ Реализация № 0042 от 12.03 не проводится — посмотри почему"
          whatHappens={[
            "get_object_by_link — получить документ и его реквизиты",
            "get_event_log с фильтром по этому документу за последние сутки",
            "Если есть ошибки проведения — модель цитирует текст ошибки и комментирует",
          ]}
          result="Object-карточка документа + Log-карточка с ошибками + текстовый комментарий с предполагаемой причиной"
        />

        <Scenario
          title="4. Сравнить остатки по складам"
          ask="Сравни остатки по номенклатуре «Кабель ВВГ 3х2.5» на всех складах на сегодня"
          whatHappens={[
            "execute_query к виртуальной таблице РегистрНакопления.ТоварыНаСкладах.Остатки с фильтром по номенклатуре",
            "Группировка по складам, выгрузка с количеством",
            "Если складов более 5 — модель добавит ```chart с Bar-диаграммой",
          ]}
          result="Table с разбивкой по складам + Bar-Chart с долями"
        />

        <Scenario
          title="5. Аудит зависимостей перед удалением реквизита"
          ask="Где в конфигурации используется реквизит ИНН справочника Контрагенты?"
          whatHappens={[
            "find_references_to_object для Справочник.Контрагенты.Реквизит.ИНН",
            "Результаты группируются: чтение в коде, отображение на формах, отчёты, роли",
            "Модель комментирует риски удаления",
          ]}
          result="References-карточка со списком использований + текст «можно удалить / нельзя / нужно проверить»"
        />

        <Scenario
          title="6. Найти аномалию в журнале регистрации"
          ask="Были ли ошибки за последние сутки и у кого?"
          whatHappens={[
            "get_event_log с severity=Ошибка и временем за 24 часа",
            "Группировка по пользователям и метаданным",
            "Модель выделяет нетипичные паттерны (всплеск ошибок у одного пользователя, серия одной и той же ошибки)",
          ]}
          result="Log-карточка с записями + текстовое резюме: «у Иванова за час 14 одинаковых ошибок проведения — стоит посмотреть»"
        />

        <H3>Как формулировать запрос, чтобы получать хорошие ответы</H3>
        <ul className="space-y-2 pl-5 list-disc text-[14px] text-[var(--fg-2)] leading-[1.65] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Уточняйте период</strong> — «за вчера»,
            «за март 2026», «за последние 30 дней» лучше, чем «за период».
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Указывайте лимит</strong> — «топ-10»,
            «последние 20» — модель в любом случае поставит лимит, но ваш точнее.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Цепочки вопросов</strong> — можно
            уточнять следующим сообщением: «а теперь только за апрель» или «отсортируй
            по сумме». Модель помнит контекст сессии.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Просите формат</strong> — «выведи
            таблицей», «нарисуй графиком», «покажи карточкой документа».
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Если кажется, что ответ неверный</strong>{" "}
            — попросите «покажи запрос которым ты это получил» или разверните
            трассировку под ответом.
          </li>
        </ul>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 7. Память, навыки, аналитика (Hermes Integration — M6)
  // ----------------------------------------------------------------------
  {
    id: "memory-skills",
    title: "Память, навыки, аналитика",
    content: (
      <>
        <Lead>
          Приложение запоминает ваш контекст между сессиями, накапливает
          подсказки и считает статистику запросов. Три инструмента работают
          вместе: <strong className="text-[var(--fg-1)]">Постоянная память</strong>,{" "}
          <strong className="text-[var(--fg-1)]">Skills и Curator</strong>,{" "}
          <strong className="text-[var(--fg-1)]">Аналитика</strong>. Доступ — через{" "}
          <em>Настройки</em>.
        </Lead>

        <H3 id="memory">
          <Brain className="inline h-4 w-4 text-[var(--accent)] mr-1" /> Постоянная память
        </H3>
        <P>
          Два файла, которые инжектятся в каждый запрос к модели:
        </P>
        <ul className="space-y-2 pl-5 list-disc text-[14px] text-[var(--fg-2)] leading-[1.6] mb-5">
          <li>
            <code className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[12px]">
              MEMORY.md
            </code>{" "}
            — что ассистент знает о вашей базе: конвенции, переименования,
            нестандартные поля, типовые паттерны запросов.
          </li>
          <li>
            <code className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[12px]">
              USER.md
            </code>{" "}
            — что он знает о вас: предпочтения по форматам, стиль ответов,
            ваш домен (склад / зарплата / финансы).
          </li>
        </ul>
        <P>
          Память per-канал (каждая база — своя). Лимиты: MEMORY.md — 16 000 символов,
          USER.md — 8 000. Сканер находит попытки prompt injection в содержимом
          и помечает их в редакторе.
        </P>
        <Callout variant="tip">
          Открыть редактор: <strong>Настройки → Постоянная память</strong>. Удобно
          вписать «Мы используем имя НоменклатураИзделия вместо Номенклатура».
        </Callout>

        <H3 id="skills">
          <Sparkles className="inline h-4 w-4 text-[var(--accent)] mr-1" /> Skills и Curator
        </H3>
        <P>
          Skills — короткие инструкции «когда X — делай Y». Два источника:
        </P>
        <ul className="space-y-2 pl-5 list-disc text-[14px] text-[var(--fg-2)] leading-[1.6] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Агент (provenance: agent)</strong> —
            после каждого успешного диалога фоновая модель проверяет, есть ли
            повторяемый паттерн, и сохраняет его сама. Не блокирует ваш ответ.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Вы (provenance: user)</strong> —
            добавляете руками через форму на странице Skills. Например:
            «Когда юзер просит остатки ТМЦ — execute_query с виртуальной
            таблицей Регистр.Остатки и фильтром по складу».
          </li>
        </ul>
        <P>
          <strong className="text-[var(--fg-1)]">Curator</strong> — фоновая чистка.
          Архивирует только agent-skills, которые не использовались N дней
          (default 30). Pinned-skills неприкосновенны. Перед каждым прогоном
          делается backup — можно откатить.
        </P>
        <Callout variant="info">
          <strong>Dry run</strong> на странице Skills показывает, что бы Curator
          архивировал, без реальных изменений. Безопасно проверить логику.
        </Callout>

        <H3 id="insights">
          <BarChart3 className="inline h-4 w-4 text-[var(--accent)] mr-1" /> Аналитика
        </H3>
        <P>
          Дашборд по сессиям: сколько диалогов, сколько сообщений, какие
          инструменты вызывались чаще, средняя длительность tool call, ошибки.
          Период: 24 часа / 7 дней / 30 дней / всё время. Плюс оценочные
          токены и стоимость по текущей модели (приблизительно).
        </P>
        <P>
          Открыть: <strong>Настройки → Аналитика</strong> или сразу{" "}
          <code className="px-1 py-0.5 rounded bg-[var(--bg-2)] text-[12px]">
            /insights
          </code>
          .
        </P>

        <H3 id="clarify">
          <HelpCircle className="inline h-4 w-4 text-[var(--accent)] mr-1" /> Уточнения от агента
        </H3>
        <P>
          Если ваш запрос неоднозначный («покажи последние документы» — каких?
          за какой период?), ассистент не угадывает, а выводит компактный диалог
          с 1–4 вариантами и кнопкой «Свой ответ». Радио — если ответ один,
          чекбоксы — если можно выбрать несколько. Это быстрее, чем переписка
          в свободной форме.
        </P>

        <H3 id="stop">
          <Square className="inline h-3.5 w-3.5 text-[var(--accent)] mr-1" /> Кнопка «Стоп»
        </H3>
        <P>
          Пока идёт стрим ответа, обычная кнопка Send заменяется на квадрат-стоп.
          Нажатие — модель завершит текущий tool call gracefully, сохранит
          частичный ответ. Не страшно нажать — данные не теряются.
        </P>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 8. Настройки
  // ----------------------------------------------------------------------
  {
    id: "settings",
    title: "Настройки",
    content: (
      <>
        <Lead>
          Шестерёнка в правом верхнем углу. Все настройки локальны — хранятся на
          вашей машине, на сервер не отправляются.
        </Lead>

        <H3>Подключения к 1С</H3>
        <P>
          Список всех баз, к которым настроено подключение. Для каждой — название,
          адрес, тип (Локально / Прокси), статус.
        </P>
        <ul className="space-y-2 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.6] mb-4">
          <li>
            <strong className="text-[var(--fg-1)]">Добавить</strong> — кнопка «Новое
            подключение». Выберите тип (Локально или Прокси), укажите хост и порт
            (или канал для прокси), дайте имя — то самое, что увидите в шапке.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Редактировать</strong> — клик
            по существующему. Можно поменять имя, адрес, тип.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Удалить</strong> — корзина рядом
            с подключением. Сами сессии остаются, но новые сообщения к удалённой
            базе отправить нельзя.
          </li>
        </ul>

        <H3>Модель ИИ</H3>
        <P>Три обязательных поля:</P>
        <ul className="space-y-2 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.6] mb-4">
          <li>
            <strong className="text-[var(--fg-1)]">Адрес</strong> — URL OpenAI-совместимого
            API. По умолчанию подставлен.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">API-ключ</strong> — токен от
            вашего провайдера. Виден только звёздочками, расшифровать в UI нельзя.
            Хранится в локальном SQLite.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Модель</strong> — название
            конкретной модели (например, <Code>mimo-v2.5-pro</Code> или{" "}
            <Code>gpt-4o</Code>). По умолчанию — <Code>mimo-v2.5-pro</Code>.
          </li>
        </ul>
        <Callout variant="info">
          Можно подключить любого провайдера, который умеет в OpenAI-совместимый API
          с function calling: OpenAI, Anthropic (через прокси), Aitunnel, Xiaomi
          MiMo, локальную LM Studio. Адрес и название модели — особенность провайдера.
        </Callout>

        <H3>Маскировка</H3>
        <P>
          Можно включить «всегда маскировать новые сессии» — тогда при создании
          новой сессии переключатель в шапке уже стоит в положении «маскировка
          включена». Раздельно от глобального переключателя в шапке.
        </P>

        <H3>Дополнительно</H3>
        <ul className="space-y-2 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.6] mb-4">
          <li>
            <strong className="text-[var(--fg-1)]">Тема</strong> — переключатель
            (Sun / Moon) дублируется в шапке для удобства.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Сброс настроек</strong> — последняя
            опция внизу страницы. Удаляет подключения и настройки модели. Сессии не
            удаляет (для этого — отдельная кнопка «Очистить историю»).
          </li>
        </ul>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 8. Диагностика
  // ----------------------------------------------------------------------
  {
    id: "diagnostics",
    title: "Диагностика и проблемы",
    content: (
      <>
        <Lead>
          В шапке — иконка <Activity className="inline h-3.5 w-3.5" /> «Диагностика».
          Это страница, где видно состояние всех компонентов: подключения 1С,
          справочник BSL, окружение приложения, версии.
        </Lead>

        <H3>Что показывает страница /status</H3>

        <H3 id="diag-mcp">Раздел «Подключения 1С»</H3>
        <P>
          Список всех подключений в виде раскрываемых строк. Для каждого:
        </P>
        <ul className="my-3 space-y-1.5 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.6]">
          <li>Тип (Локально / Прокси) — бейдж</li>
          <li>Адрес — с кнопкой копирования</li>
          <li>Статус ping и время последней проверки</li>
          <li>Сколько инструментов отвечает (обычно 10 у MCP Toolkit)</li>
          <li>Список имён инструментов в виде чипов</li>
          <li>Текст ошибки, если ping не прошёл</li>
        </ul>

        <H3 id="diag-aux">Раздел «Дополнительные источники (aux MCP)»</H3>
        <P>
          Здесь показан справочник <Code>bsl-context</Code>. Возможные статусы:
        </P>
        <ul className="my-3 space-y-1.5 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.6]">
          <li>
            <strong className="text-[var(--success)]">Подключён</strong> — Java-процесс
            запущен, справочник доступен.
          </li>
          <li>
            <strong className="text-[var(--warning)]">Не настроен</strong> — в окружении
            нет переменных <Code>BSL_CONTEXT_*</Code>. Это не ошибка, просто
            справочник опциональный.
          </li>
          <li>
            <strong className="text-[var(--error)]">Ошибка</strong> — переменные есть,
            но процесс не стартует (нет Java, неверный путь к JAR, нет доступа к
            каталогу платформы).
          </li>
        </ul>

        <H3 id="diag-env">Раздел «Окружение приложения»</H3>
        <P>
          Снимок настроек backend без секретных значений: путь к SQLite, какие
          переменные окружения заданы, порты, версии библиотек. Если что-то
          сломалось, и пишете ИТ — приложите этот блок (можно скопировать целиком).
        </P>

        <H3>Если что-то не работает</H3>
        <div className="my-5 space-y-3">
          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-3.5">
            <div className="text-[13.5px] font-semibold text-[var(--fg-1)] mb-1.5">
              Подключение красное
            </div>
            <ul className="space-y-1 pl-5 list-disc text-[13px] text-[var(--fg-2)]">
              <li>Запущена ли обработка MCP Toolkit в самой 1С? (Сервис → Внешние обработки → MCP_Toolkit_v1.7.0)</li>
              <li>Не закрыли ли вы её случайно?</li>
              <li>Тот ли порт указан в Настройках (по умолчанию 6010)?</li>
              <li>Не блокирует ли firewall localhost:6010?</li>
            </ul>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-3.5">
            <div className="text-[13.5px] font-semibold text-[var(--fg-1)] mb-1.5">
              Модель отвечает медленно / зависает
            </div>
            <ul className="space-y-1 pl-5 list-disc text-[13px] text-[var(--fg-2)]">
              <li>Проверьте баланс / лимит у вашего LLM-провайдера.</li>
              <li>Если провайдер геоблокирует — нужен прокси (см. с админом).</li>
              <li>Попробуйте отправить простой вопрос — «привет» — без вызова инструментов. Если и это медленно, дело в модели.</li>
            </ul>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-3.5">
            <div className="text-[13.5px] font-semibold text-[var(--fg-1)] mb-1.5">
              Ответы кажутся неверными
            </div>
            <ul className="space-y-1 pl-5 list-disc text-[13px] text-[var(--fg-2)]">
              <li>Разверните трассировку под ответом — посмотрите, какие именно запросы выполнялись.</li>
              <li>Попросите модель «покажи запрос которым ты это получил».</li>
              <li>Экспортируйте чат (кнопка ↓ в сессии) и передайте разработчику.</li>
              <li>Уточните вопрос — чем конкретнее период, фильтр, формат, тем точнее ответ.</li>
            </ul>
          </div>

          <div className="rounded-md border border-[var(--bd-2)] bg-[var(--bg-1)] p-3.5">
            <div className="text-[13.5px] font-semibold text-[var(--fg-1)] mb-1.5">
              Справочник BSL «Не настроен»
            </div>
            <ul className="space-y-1 pl-5 list-disc text-[13px] text-[var(--fg-2)]">
              <li>Это нормально, если ИТ не подключал. Приложение работает без него.</li>
              <li>Если нужен — попросите ИТ задать <Code>BSL_CONTEXT_JAR_PATH</Code>, <Code>BSL_CONTEXT_JAVA</Code>, <Code>BSL_CONTEXT_PLATFORM_PATH</Code> в backend/.env и перезапустить приложение.</li>
            </ul>
          </div>
        </div>
      </>
    ),
  },

  // ----------------------------------------------------------------------
  // 9. Безопасность
  // ----------------------------------------------------------------------
  {
    id: "security",
    title: "Безопасность",
    content: (
      <>
        <Lead>
          Кратко — что приложение делает и чего никогда не делает с данными вашей
          базы.
        </Lead>

        <H3>Что приложение делает</H3>
        <ul className="space-y-2 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.65] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Читает</strong> структуру
            конфигурации, данные через SELECT-запросы, журнал регистрации, права.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Может</strong> выполнить BSL-код,
            но только с явным подтверждением через диалог. Опасные операции
            (запись, удаление) — каждый раз заново.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Хранит</strong> сессии и настройки
            в локальном SQLite на вашей машине. Файл лежит в каталоге backend.
          </li>
        </ul>

        <H3>Чего приложение не делает</H3>
        <ul className="space-y-2 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.65] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Не записывает</strong> данные в
            базу 1С без явного подтверждения. <Code>execute_query</Code> технически
            ограничен SELECT.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Не отправляет</strong> данные базы
            в публичный интернет, кроме модели ИИ (по вашему выбору). Если используете
            локальную модель (LM Studio) — данные вообще не покидают машину.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Не сохраняет</strong> API-ключи
            где-либо, кроме локального SQLite. На сервер их отправлять не нужно.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Не делает</strong> массовые
            операции по своей инициативе. Каждое действие — реакция на ваш конкретный
            вопрос.
          </li>
        </ul>

        <H3>Что нужно учитывать вам</H3>
        <ul className="space-y-2.5 pl-5 list-disc text-[13.5px] text-[var(--fg-2)] leading-[1.65] mb-5">
          <li>
            <strong className="text-[var(--fg-1)]">Прокси-режим = данные идут через прокси.</strong>{" "}
            HF Spaces — публичный сервис. Для чувствительных баз — только локально или со включённой маскировкой.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Облачные LLM видят содержимое запросов.</strong>{" "}
            Если выбран OpenAI / Anthropic / MiMo — текст вопроса и кусок данных из
            базы для формирования ответа уходит к ним. Это нормальный режим работы,
            но имейте в виду.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Маскировка не магия.</strong> Она
            скрывает имена в выводе, но модель в процессе рассуждения видит исходные
            данные (на этом основан вызов <Code>submit_for_deanonymization</Code> у
            модели). Защита — от случайного показа на скриншоте, не от утечки
            к провайдеру модели.
          </li>
          <li>
            <strong className="text-[var(--fg-1)]">Резервная копия — ваша ответственность.</strong>{" "}
            Перед сложными расследованиями делайте обычный бэкап базы. Особенно если
            подтверждаете <Code>execute_code</Code> с модифицирующими операциями.
          </li>
        </ul>

        <Callout variant="danger">
          <strong>Правило одной строки:</strong> если приложение спрашивает
          подтверждение перед выполнением BSL-кода — внимательно прочитайте, что
          именно оно собирается сделать. Никогда не нажимайте «Подтвердить»,
          если не понимаете, что делает код.
        </Callout>
      </>
    ),
  },
];

// ============================================================================
// PAGE
// ============================================================================

export default function GuidePage() {
  return (
    <GuideLayout
      title="Гайд аналитика"
      subtitle="Полное руководство: что это, как настроить, какие инструменты доступны, какие сценарии разбирать, что делать когда что-то не работает. Читать сверху вниз или прыгать по разделам через содержание слева."
      sections={SECTIONS}
    />
  );
}
