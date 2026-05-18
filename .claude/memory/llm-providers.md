# LLM-провайдеры (MSG #11/12)

## Цитаты пользователя
> 1с это проект онли для 1с, ... все должно быть в приложении с возможностью подключения к разным моделям по апи
— MSG #11

> Я же явно сказал что это может быть любая можель которая рабочает через апи, в моем варианте это мимо от сяоми, локальные модели пока откинем
— MSG #12

## Решено
| Провайдер | Статус | Транспорт |
|---|---|---|
| **Xiaomi MiMo** | priority (default по моему стеку) | OpenAI-compatible HTTP |
| Anthropic Claude | supported | OpenAI-compatible через proxy ИЛИ Anthropic SDK |
| OpenAI GPT | supported | OpenAI HTTP |
| Yandex GPT | supported | через OpenAI-compat shim |
| GigaChat | supported | через OpenAI-compat shim |
| Grok (xAI) | supported | OpenAI-compat |
| **Ollama / локальные модели** | **NO** — «откинем пока» (MSG #12) | — |

## Текущее состояние
- В коде: `llm_settings` singleton (1 профиль)
- Backlog: multi-profile LLM router (упоминается в Phase 5 release notes)
- API ключи: sessionStorage browser (НЕ backend) — security trade-off из v1.0
