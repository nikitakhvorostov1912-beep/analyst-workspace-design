/**
 * Каталог LLM-провайдеров — единая точка истины для UI выбора модели.
 *
 * Используется в LLMConfigForm (полная настройка) и ModelBadge (быстрый
 * переключатель из шапки). Общий список — расширять одним местом.
 *
 * Только OpenAI-compatible API. Все ключи проходят validation через UI или
 * env-fallback в backend (resolve_default_api_key per endpoint).
 *
 * P3.1 rev3 (2026-05-22): каталог обновлён под актуальные модели весны 2026.
 * Web search 2026-05-22 показал:
 * - DeepSeek V4 Pro/Flash (релиз 24 апреля 2026) — старые chat/reasoner
 *   deprecated до 24 июля 2026
 * - Qwen 3.7 Max/Plus (релиз 20-21 мая 2026) — флагман с autonomous до 35h
 * - MiMo V2.5 Pro (релиз 22 апреля 2026) — 1T MoE, 42B активных, 1M context
 * - GLM-5.1, MiniMax M2.7, Nemotron 3 Nano Omni — новые флагманы NVIDIA NIM
 *
 * Стратегия:
 * - NVIDIA NIM — база с вшитым ключом, новые модели всех вендоров через
 *   один аккаунт (NIM это marketplace)
 * - Cloud.ru — 152-ФЗ compliance (РФ-ДЦ)
 * - DeepSeek прямой — самая дешёвая цена на DeepSeek V4
 * - MiMo — китайский bargain через свой API
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
  /** Для UI badge «РФ-ДЦ ✓» / «За рубежом — требует согласие». */
  compliance?: ProviderCompliance;
  models: ModelPreset[];
}

export const CUSTOM_MODEL_ID = "__custom__";
// P3.1 rev3 (2026-05-22): DeepSeek V4 Flash на NVIDIA NIM — дефолтная база.
// 284B MoE, 1M context, оптимизирован под кодинг и агентов (~10x быстрее
// V4 Pro при сравнимом качестве на BSL/SQL задачах). Стабильно работает
// с tool_calls в pipeline.
export const DEFAULT_PRESET_ID = "deepseek-ai/deepseek-v4-flash";

export const PROVIDERS: Provider[] = [
  {
    // База — NVIDIA NIM. Один ключ покрывает все модели marketplace.
    // Зашит в installer через desktop/resources/embedded.env.
    // Если квота NVIDIA developer-тира кончится — аналитик введёт свой
    // ключ через Настройки (UI поддерживает per-user override).
    //
    // Состав каталога синхронизирован с https://build.nvidia.com/models
    // на 2026-05-22 (web search). Включены только модели с подтверждённой
    // поддержкой tool_calls (нужно для нашего MCP-orchestrator).
    id: "nvidia-nim",
    label: "NVIDIA NIM (база)",
    endpoint: "https://integrate.api.nvidia.com/v1",
    keyHint: "nvapi-... (или используется встроенный)",
    keyDocsUrl: "build.nvidia.com (вкладка «API keys»)",
    embedKeyAvailable: true,
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "deepseek-ai/deepseek-v4-flash",
        label: "DeepSeek V4 Flash",
        description: "Рекомендуется · 284B MoE · 1M контекст · быстрый кодинг",
      },
      {
        id: "deepseek-ai/deepseek-v4-pro",
        label: "DeepSeek V4 Pro",
        description: "Флагман · 1.6T MoE · 1M контекст · для сложного reasoning",
      },
      {
        id: "zhipuai/glm-5.1",
        label: "GLM-5.1",
        description: "Флагман Zhipu · агенты, кодинг, long-horizon задачи",
      },
      {
        id: "qwen/qwen3-coder-plus",
        label: "Qwen3 Coder Plus",
        description: "Alibaba · coding-агент с tool_calls и кодом",
      },
      {
        id: "qwen/qwen3-coder-480b-a35b-instruct",
        label: "Qwen3 Coder 480B (open)",
        description: "Open-source MoE 480B · сильна в BSL/SQL",
      },
      {
        id: "minimax-ai/minimax-m2.7",
        label: "MiniMax M2.7",
        description: "230B · кодинг, reasoning, офисные задачи",
      },
      {
        id: "nvidia/nemotron-3-nano-omni",
        label: "Nemotron 3 Nano Omni",
        description: "NVIDIA omni-modal · текст + изображения + видео + аудио",
      },
      {
        id: "meta/llama-4-scout-17b-16e-instruct",
        label: "Llama 4 Scout",
        description: "Meta · флагман 2026 · открытый MoE",
      },
      {
        id: "mistralai/mistral-large-3-675b-instruct-2512",
        label: "Mistral Large 3 (675B)",
        description: "Mistral × NVIDIA · мощный MoE для глубокого анализа",
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
    // DeepSeek прямой API — самый дешёвый для V4 серии.
    // Цены V4 Pro (после скидки): $1.74/$3.48 за 1M input/output.
    // Старые deepseek-chat / deepseek-reasoner deprecated до 24 июля 2026.
    id: "deepseek",
    label: "DeepSeek (дешёвый китайский)",
    endpoint: "https://api.deepseek.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "platform.deepseek.com/api_keys",
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "deepseek-v4-flash",
        label: "DeepSeek V4 Flash",
        description: "284B MoE · 1M контекст · быстрый и дешёвый",
      },
      {
        id: "deepseek-v4-pro",
        label: "DeepSeek V4 Pro",
        description: "1.6T MoE · 1M контекст · флагман DeepSeek",
      },
    ],
  },
  {
    // Xiaomi MiMo — V2.5 Pro вышел 22.04.2026.
    // 1T MoE с 42B активных, 1M context, omni-modal (текст/image/audio/video),
    // 1000+ tool calls подряд. Цена $1 / 1M input — конкурент DeepSeek V4 Flash.
    id: "xiaomi-mimo",
    label: "Xiaomi MiMo (китайский)",
    endpoint: "https://api.xiaomimimo.com/v1",
    keyHint: "sk-...",
    keyDocsUrl: "api.xiaomimimo.com",
    compliance: { russian_dc: false, fz152: false },
    models: [
      {
        id: "mimo-v2.5-pro",
        label: "MiMo V2.5 Pro",
        description: "Флагман · 1T MoE · 1M контекст · 1000+ tool_calls подряд",
      },
      {
        id: "mimo-v2-pro",
        label: "MiMo V2 Pro",
        description: "Стабильная база · дешевле V2.5",
      },
      {
        id: "mimo-v2-omni",
        label: "MiMo V2 Omni",
        description: "Multimodal — текст + image + audio + video",
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
