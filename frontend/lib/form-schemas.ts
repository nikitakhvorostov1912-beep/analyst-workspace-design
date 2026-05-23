import { z } from "zod";

export const mcpConnectionSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Название обязательно")
      .max(50, "Не больше 50 символов"),
    endpoint: z.string().url("Должен быть валидный URL"),
    channel: z.string().trim().max(60).optional().or(z.literal("")),
    anon_enabled: z.boolean().default(false),
    kind: z.enum(["embedded", "proxy"]).default("embedded"),
  })
  .refine(
    (data) => data.kind !== "proxy" || !!(data.channel && data.channel.trim()),
    {
      // При proxy-режиме канал обязателен — без него прокси-сервер не знает,
      // к какой удалённой 1С базе пересылать запросы.
      message: "Для прокси-подключения укажите профиль",
      path: ["channel"],
    },
  );

export const llmConfigSchema = z.object({
  endpoint: z.string().url("Должен быть валидный URL"),
  model: z
    .string()
    .trim()
    .min(1, "Модель обязательна")
    .max(100),
  temperature: z.number().min(0).max(2),
  api_key: z
    .string()
    .min(8, "API ключ слишком короткий")
    .max(200),
});

export const llmConfigUpdateSchema = z.object({
  endpoint: z.string().url("Должен быть валидный URL"),
  model: z
    .string()
    .trim()
    .min(1, "Модель обязательна")
    .max(100),
  temperature: z.number().min(0).max(2),
  api_key: z
    .string()
    .min(8, "API ключ слишком короткий")
    .max(200)
    .optional(),
});

export type MCPConnectionInput = z.infer<typeof mcpConnectionSchema>;
export type LLMConfigInput = z.infer<typeof llmConfigSchema>;
