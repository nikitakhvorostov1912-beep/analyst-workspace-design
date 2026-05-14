/**
 * Фейковые ChatMessage для ручного smoke-тестирования cards UI.
 * НЕ импортировать в продакшн-код.
 */

import type { ChatMessage } from "@/lib/types";

export const demoMessages: ChatMessage[] = [
  {
    id: "demo-user-1",
    role: "user",
    content: "Покажи таблицу контрагентов",
    created_at: new Date().toISOString(),
  },
  {
    id: "demo-table",
    role: "assistant",
    content: "Вот результаты запроса по контрагентам:",
    created_at: new Date().toISOString(),
    duration_ms: 320,
    tool_calls: [
      {
        id: "tc-1",
        name: "execute_query",
        args: { query: "ВЫБРАТЬ Наименование, ИНН ИЗ Справочник.Контрагенты ПЕРВЫЕ 5" },
        ok: true,
        duration_ms: 120,
      },
    ],
    cards: [
      {
        type: "table",
        payload: {
          columns: [
            { name: "Наименование", type: "String" },
            { name: "ИНН", type: "String" },
            { name: "Баланс", type: "Number" },
          ],
          rows: [
            ["ООО Ромашка", "7701234567", 125000.5],
            ["ИП Петров А.В.", "770987654", 0],
            ["АО Северсталь", "7803002929", 5600000],
            ["ООО Тест", "7700000001", null],
            ["ЗАО Пример", "7700000002", -12000],
          ],
          total: 5,
          meta: {
            query: "ВЫБРАТЬ Наименование, ИНН ИЗ Справочник.Контрагенты ПЕРВЫЕ 5",
            duration_ms: 98,
          },
        },
      },
    ],
  },
  {
    id: "demo-user-2",
    role: "user",
    content: "Что за объект Справочник.Контрагенты?",
    created_at: new Date().toISOString(),
  },
  {
    id: "demo-object",
    role: "assistant",
    content: "Справочник **Контрагенты** — хранит информацию о контрагентах организации.",
    created_at: new Date().toISOString(),
    cards: [
      {
        type: "object",
        payload: {
          header: {
            name: "Контрагенты",
            type: "Справочник",
            path: "Справочники.Контрагенты",
          },
          attributes: [
            { name: "Наименование", type: "Строка", value: undefined },
            { name: "ИНН", type: "Строка", value: undefined },
            { name: "КПП", type: "Строка", value: undefined },
            { name: "ЮридическоеФизическоеЛицо", type: "ПеречислениеСсылка.ЮридическоеФизическоеЛицо" },
          ],
          tabular_sections: [
            {
              name: "КонтактнаяИнформация",
              columns: ["Тип", "Вид", "Представление", "Объект"],
              rows_preview: [
                ["Адрес", "ЮридическийАдрес", "г. Москва, ул. Ленина 1", null],
              ],
            },
          ],
          forms: [
            { name: "ФормаЭлемента", type: "ФормаЭлемента" },
            { name: "ФормаСписка", type: "ФормаСписка" },
          ],
          templates: [
            { name: "Конверт", type: "MXLМакет" },
          ],
        },
      },
    ],
  },
  {
    id: "demo-user-3",
    role: "user",
    content: "Что в журнале сегодня?",
    created_at: new Date().toISOString(),
  },
  {
    id: "demo-log",
    role: "assistant",
    content: "Вот записи журнала за сегодня:",
    created_at: new Date().toISOString(),
    cards: [
      {
        type: "log",
        payload: {
          entries: [
            {
              time: new Date().toISOString(),
              level: "Error",
              user: "admin",
              event: "_$Data$_.Update",
              comment: "Ошибка при записи объекта: нарушение уникальности ключа",
            },
            {
              time: new Date(Date.now() - 60000).toISOString(),
              level: "Warning",
              user: "user1",
              event: "_$Session$_.Authentication",
              comment: undefined,
            },
            {
              time: new Date(Date.now() - 120000).toISOString(),
              level: "Info",
              user: "system",
              event: "_$Job$_.Start",
              comment: undefined,
            },
            {
              time: new Date(Date.now() - 180000).toISOString(),
              level: "Critical",
              user: "admin",
              event: "_$Access$_.AccessDenied",
              comment: "Попытка несанкционированного доступа к защищённому объекту",
            },
          ],
          next_cursor: "cursor_abc123",
        },
      },
    ],
  },
];
