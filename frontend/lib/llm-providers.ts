/**
 * Каталог LLM-провайдеров — единая точка истины для UI выбора модели.
 *
 * Используется в LLMConfigForm (полная настройка) и ModelBadge (быстрый
 * переключатель из шапки). Общий список — расширять одним местом.
 *
 * Только OpenAI-compatible API. Все ключи проходят validation через UI или
 * env-fallback в backend (resolve_default_api_key per endpoint).
 *
 * P3.1 rev2 (2026-05-23): каталог сокращён под коммерческую стратегию.
 * NVIDIA NIM — база (вшитый ключ в installer), Cloud.ru — для 152-ФЗ
 * compliance, DeepSeek + MiMo — дешёвые китайские альтернативы. OpenAI,
 * Anthropic, Groq, Mistral direct, xAI Grok убраны из UI (можно вернуть
 * через "Свой endpoint", если кому-то нужно).
 *
 * При появлении новых моделей в 2026+ — добавлять сюда; ModelBadge popover
 * автоматически подхватит.
 */

export interface ModelPreset {
  id: string;
  label: string;
  description: string;
}

/**
 * Compliance-флаги для UI badge.
 * russian_dc=true означает что провайдер хостится в РФ-дата-центре и
 * данные не пересекают границу (152-ФЗ snapshot pre-flight).
 * fz152=true означает что использовать провайдер по умолчанию без
 * дополнительного согласия субъектов ПД безопасно.
 *
 * Источник статуса: P3.3 (UI badges + migration UX) в COMMERCE-PLAN-2026-05-23.
 */
export interface ProviderCompliance {
  russian_dc: boolean;
  fz152: boolean;
}

export interface Provider {
  id: string;
  label: string;
  endpoint: string;
  keyHint: string;
  keyDocsUrl: string;
  /** True для провайдеров где env-ключ из дистрибутива подходит.
   * NVIDIA NIM — вшит в installer как «база» (один ключ на много моделей).
   */
  embedKeyAvailable?: boolean;
  /** Для UI badge «РФ-ДЦ ✓» / «За рубежом — требует согласие». См. P3.3. */
  compliance?: ProviderCompliance;
  models: ModelPreset[];
}

export const CUSTOM_MODEL_ID = "__custom__";
// P3.1 rev2 (2026-05-23): NVIDIA Llama Nemotron Super 49B — дефолтная база.
// Стабильно работает с tool_calls, ключ NVIDIA вшит в installer (один
// ключ покрывает все модели NIM), доступна без отдельной регистрации
// пользователя.
export const DEFAULT_PRESET_ID = "nvidia/llama-3.3-nemotron-super-49b-v1.5";

export const PROVIDERS: Provider[] = [
  {
    // База — NVIDIA NIM. Один ключ покрывает все модели платформы.
    // Зашит в installer через desktop/resources/embedded.env.
    // Если квота NVIDIA developer-тира кончится — аналитик введёт свой
    // ключ через Настройки (UI поддерживает per-user override).
    //
    // Список моделей проверен на developer-аккаунте (curl tool_calls roundtrip).
    // Исключены: Llama 4 Maverick (отдаёт JSON в content вместо tool_calls).
    id: "nvidia-nim",
    label: "NVIDIA NIM (база)",
    endpoint: "https://integrate.api.nvidia.com/v1",
    keyHint: "nvapi-... (или используется встроенный)",
    keyDocsUrl: "build.nvidia.com (вкладка «API keys»)",
    embedKeyAvailable: true,
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        label: "Llama Nemotron Super 49B v1.5",
        description: "Рекомендуется по умолчанию · точная работа с tools/RAG",
      },
      {
        id: "deepseek-ai/deepseek-r1",
        label: "DeepSeek R1 (через NVIDIA)",
        description: "Reasoning-модель · для сложных запросов и анализа",
      },
      {
        id: "deepseek-ai/deepseek-v3.1",
        label: "DeepSeek V3.1 (через NVIDIA)",
        description: "Универсальная · сильна в коде и логике",
      },
      {
        id: "meta/llama-3.3-70b-instruct",
        label: "Llama 3.3 70B",
        description: "Meta · стабильная база с надёжными tool_calls",
      },
      {
        id: "qwen/qwen3-coder-480b-a35b-instruct",
        label: "Qwen3-Coder 480B",
        description: "Лучшая на BSL/SQL · MoE 480B параметров",
      },
      {
        id: "qwen/qwen2.5-coder-32b-instruct",
        label: "Qwen 2.5 Coder 32B",
        description: "Быстрее и дешевле для типовых запросов к коду",
      },
      {
        id: "mistralai/mistral-large-3-675b-instruct-2512",
        label: "Mistral Large 3 (675B)",
        description: "Mistral × NVIDIA · мощный MoE для глубокого анализа",
      },
      {
        id: "mistralai/mistral-medium-3.5-128b",
        label: "Mistral Medium 3.5 (128B)",
        description: "Баланс цены и качества",
      },
      {
        id: "nvidia/nvidia-nemotron-nano-9b-v2",
        label: "Nemotron Nano 9B",
        description: "Компактная · мгновенный ответ на простые вопросы",
      },
    ],
  },
  {
    // 152-ФЗ alternative — РФ-ДЦ. Для клиентов с jur требованием
    // «данные не пересекают границу».
    id: "cloud-ru-qwen3",
    label: "Cloud.ru Foundation Models (РФ-ДЦ)",
    endpoint: "https://foundation-models.api.cloud.ru/v1",
    keyHint: "sk-... (из Cloud.ru console)",
    keyDocsUrl: "cloud.ru/docs/foundation-models",
    // embedKeyAvailable не ставим — каждая компания регистрируется в
    // Cloud.ru сама. Backend поддерживает per-provider env override
    // через DEFAULT_LLM_API_KEY_CLOUD_RU для коллег внутри одной команды.
    compliance: { russian_dc: true, fz152: true },
    models: [
      {
        id: "Qwen/Qwen3-Coder-480B-A35B-Instruct",
        label: "Qwen3-Coder-480B",
        description: "БЕСПЛАТНО · РФ-ДЦ · лучшее на BSL",
      },
    ],
  },
  {
    // DeepSeek прямой API — самый дешёвый вариант для DeepSeek R1/V3.
    // Цены: $0.27/1M input · $1.10/1M output (V3.1) — на порядок дешевле OpenAI.
    id: "deepseek",
    label: "DeepSeek (дешёвый китайский)",
    endpoint: "https://api.deepseek.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "platform.deepseek.com/api_keys",
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "deepseek-chat",
        label: "DeepSeek V3.1",
        description: "Сильная и очень дешёвая · 128K контекст",
      },
      {
        id: "deepseek-reasoner",
        label: "DeepSeek R1",
        description: "Reasoning · конкурент o3 за 10% цены",
      },
    ],
  },
  {
    // Xiaomi MiMo — китайский bargain, для быстрых дешёвых запросов.
    id: "xiaomi-mimo",
    label: "Xiaomi MiMo (китайский)",
    endpoint: "https://api.xiaomimimo.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "api.xiaomimimo.com",
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "mimo-v2.5-pro",
        label: "MiMo v2.5 Pro",
        description: "Основная — баланс качества и цены",
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
