/**
 * Каталог LLM-провайдеров — единая точка истины для UI выбора модели.
 *
 * Используется в LLMConfigForm (полная настройка) и ModelBadge (быстрый
 * переключатель из шапки). До 2026-05-21 список жил inline в LLMConfigForm
 * и был доступен только из настроек — теперь общий, можно расширять одним местом.
 *
 * Только OpenAI-compatible API. Anthropic Claude прямой API не подходит
 * (формат сообщений другой), поэтому Claude — через OpenRouter.
 *
 * Зашитый ключ в desktop/.env работает только для Xiaomi MiMo (embedKeyAvailable).
 * Для остальных провайдеров аналитик вводит свой ключ.
 *
 * При появлении новых моделей в 2026+ — добавлять сюда; ModelBadge popover
 * автоматически подхватит.
 */

export interface ModelPreset {
  id: string;
  label: string;
  description: string;
}

export interface Provider {
  id: string;
  label: string;
  endpoint: string;
  keyHint: string;
  keyDocsUrl: string;
  /** True для провайдеров где .env-ключ из дистрибутива подходит (на 2026-05-21 это только MiMo). */
  embedKeyAvailable?: boolean;
  models: ModelPreset[];
}

export const CUSTOM_MODEL_ID = "__custom__";
export const DEFAULT_PRESET_ID = "mimo-v2.5-pro";

export const PROVIDERS: Provider[] = [
  {
    id: "xiaomi-mimo",
    label: "Xiaomi MiMo",
    endpoint: "https://api.xiaomimimo.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "api.xiaomimimo.com",
    embedKeyAvailable: true,
    models: [
      {
        id: "mimo-v2.5-pro",
        label: "MiMo v2.5 Pro",
        description: "Основная — рекомендуется по умолчанию",
      },
      {
        id: "mimo-v2.5-mini",
        label: "MiMo v2.5 Mini",
        description: "Быстрее и дешевле — для простых вопросов",
      },
      {
        id: "mimo-v2-omni",
        label: "MiMo v2 Omni",
        description: "С распознаванием изображений (PNG/JPG)",
      },
    ],
  },
  {
    id: "openai",
    label: "OpenAI",
    endpoint: "https://api.openai.com/v1",
    keyHint: "sk-proj-...",
    keyDocsUrl: "platform.openai.com/api-keys",
    models: [
      {
        id: "gpt-4.1",
        label: "GPT-4.1",
        description: "Флагман 2026 — длинный контекст 1M, точные ответы",
      },
      {
        id: "gpt-4.1-mini",
        label: "GPT-4.1 Mini",
        description: "Бюджетная новая — баланс скорости и качества",
      },
      {
        id: "gpt-4o",
        label: "GPT-4o",
        description: "Multimodal — текст, картинки, голос",
      },
      {
        id: "o3-mini",
        label: "o3-mini",
        description: "Reasoning — думает дольше, для сложных задач",
      },
    ],
  },
  {
    id: "anthropic-or",
    label: "Anthropic Claude (через OpenRouter)",
    endpoint: "https://openrouter.ai/api/v1",
    keyHint: "sk-or-v1-...",
    keyDocsUrl: "openrouter.ai/keys",
    models: [
      {
        id: "anthropic/claude-opus-4.5",
        label: "Claude Opus 4.5",
        description: "Самая мощная модель Anthropic — для анализа и кода",
      },
      {
        id: "anthropic/claude-sonnet-4.5",
        label: "Claude Sonnet 4.5",
        description: "Топ-баланс качества и цены — рекомендуется",
      },
      {
        id: "anthropic/claude-haiku-4.5",
        label: "Claude Haiku 4.5",
        description: "Быстрая и дешёвая — для коротких запросов",
      },
    ],
  },
  {
    id: "nvidia-nim",
    label: "NVIDIA NIM",
    endpoint: "https://integrate.api.nvidia.com/v1",
    keyHint: "nvapi-...",
    keyDocsUrl: "build.nvidia.com (вкладка «API keys»)",
    // embedKeyAvailable не ставим — sandbox блокирует запись ключа в installer,
    // пользователь сам раздаёт ключ коллегам и они вводят его через UI один раз.
    // Backend всё равно умеет per-provider env-fallback (resolve_default_api_key),
    // так что желающий админ может добавить DEFAULT_LLM_API_KEY_NVIDIA в .env
    // своей установки и тогда коллеги увидят зелёную плашку «Ключ из .env».
    // Список проверен реальным curl-прогоном 2026-05-21 на developer-аккаунте:
    // включены только модели которые корректно возвращают `tool_calls` (нужно
    // для нашего MCP-orchestrator). Llama 4 Maverick исключён — он отдаёт JSON
    // в content вместо tool_calls. Nemotron 70B / Ultra 253B — 404 на developer-тире.
    models: [
      {
        id: "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        label: "Llama Nemotron Super 49B v1.5",
        description: "Флагман NVIDIA Nemotron — точнее в tools/RAG",
      },
      {
        id: "meta/llama-3.3-70b-instruct",
        label: "Llama 3.3 70B (NIM)",
        description: "Meta — стабильная база, проверено с tools",
      },
      {
        id: "mistralai/mistral-large-3-675b-instruct-2512",
        label: "Mistral Large 3 (675B)",
        description: "Mistral × NVIDIA — мощный MoE",
      },
      {
        id: "mistralai/mistral-medium-3.5-128b",
        label: "Mistral Medium 3.5 (128B)",
        description: "Баланс цены и качества",
      },
      {
        id: "nvidia/nvidia-nemotron-nano-9b-v2",
        label: "Nemotron Nano 9B",
        description: "Компактная и быстрая — для простых запросов",
      },
    ],
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    endpoint: "https://api.deepseek.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "platform.deepseek.com/api_keys",
    models: [
      {
        id: "deepseek-chat",
        label: "DeepSeek V3",
        description: "Сильная и очень дешёвая",
      },
      {
        id: "deepseek-reasoner",
        label: "DeepSeek R1",
        description: "Reasoning — конкурент o3, дешевле",
      },
    ],
  },
  {
    id: "openrouter",
    label: "OpenRouter (Gemini, Llama, прочее)",
    endpoint: "https://openrouter.ai/api/v1",
    keyHint: "sk-or-v1-...",
    keyDocsUrl: "openrouter.ai/keys",
    models: [
      {
        id: "google/gemini-2.5-pro",
        label: "Gemini 2.5 Pro",
        description: "Google — флагман 2026, контекст до 2M токенов",
      },
      {
        id: "google/gemini-2.5-flash",
        label: "Gemini 2.5 Flash",
        description: "Google — быстрая и дешёвая",
      },
      {
        id: "meta-llama/llama-4-maverick",
        label: "Llama 4 Maverick",
        description: "Meta — новейший Llama, открытый MoE",
      },
    ],
  },
  {
    id: "groq",
    label: "Groq (самая быстрая)",
    endpoint: "https://api.groq.com/openai/v1",
    keyHint: "gsk_...",
    keyDocsUrl: "console.groq.com/keys",
    models: [
      {
        id: "llama-3.3-70b-versatile",
        label: "Llama 3.3 70B",
        description: "На LPU Groq — мгновенный ответ",
      },
      {
        id: "deepseek-r1-distill-llama-70b",
        label: "DeepSeek R1 Distill 70B",
        description: "Reasoning, дистилл в Llama — быстрый",
      },
    ],
  },
  {
    id: "mistral",
    label: "Mistral",
    endpoint: "https://api.mistral.ai/v1",
    keyHint: "...",
    keyDocsUrl: "console.mistral.ai/api-keys",
    models: [
      {
        id: "mistral-large-latest",
        label: "Mistral Large",
        description: "Флагман — 2026 поколение",
      },
      {
        id: "mistral-medium-latest",
        label: "Mistral Medium",
        description: "Баланс цены и качества",
      },
    ],
  },
  {
    id: "xai",
    label: "xAI Grok",
    endpoint: "https://api.x.ai/v1",
    keyHint: "xai-...",
    keyDocsUrl: "console.x.ai",
    models: [
      {
        id: "grok-3",
        label: "Grok 3",
        description: "Флагман xAI — свежие данные из X",
      },
      {
        id: "grok-3-mini",
        label: "Grok 3 Mini",
        description: "Бюджетный — для коротких запросов",
      },
    ],
  },
];

/** Плоский lookup id → {provider, model}. Строится один раз. */
const FLAT_MAP = (() => {
  const m = new Map<string, { provider: Provider; model: ModelPreset }>();
  for (const provider of PROVIDERS) {
    for (const model of provider.models) {
      m.set(model.id, { provider, model });
    }
  }
  return m;
})();

export function resolveProviderAndModel(modelId: string):
  | { provider: Provider; model: ModelPreset }
  | null {
  return FLAT_MAP.get(modelId) ?? null;
}
