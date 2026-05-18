# Дизайн-ограничения (что НЕ делать)

## Цитаты пользователя

> да епт, удали все это лишнее, ты открывал пронт энд и бэкэнд раньше, мне нравился тот концпепт
— MSG #19

> что это ты же помнишь что было приветсвенная строка, оранжевый дизайн как в чате  дизайн ты че, мы же открывали
— MSG #20

> @C:\Users\Khvorostov\Downloads\НОвая концепция.zip ты на приколе? Я же просил сделать как аналитик 1с нахера ты накидал куча ненужного если я происл поставить чат во главе как у нас сейчас
— MSG #26

## Жёсткие правила
- **Чат во главе** — единственный workflow. NL → LLM → tool_calls → cards
- **Никаких 8 экранов** wizard'а в концепциях (моя ошибка с v5 промптом для Claude Design)
- **Никаких work-modes** Discovery/Triage/Investigate/Mapping/Knowledge (v0 mistake)
- **Никакого Object-IDE** с tree метаданных слева (v0 mistake)
- **Никакого Workflow editor** карточками операций (v0b mistake)
- **Никаких AI right-rail** «инсайтов» и «магических подсказок»

## Запреты из CLAUDE.md (preserve)
- Inter font, purple-cyan gradients, glass morphism, decorative emoji
- Mobile-first вёрстка (desktop only, ≥ 1280px)
- Светлая тема как опция

## Оранжевый дизайн — что это
- Пользователь помнит «приветсвенная строка, оранжевый дизайн»
- Это **OnboardingDialog Step 1** — «Подключите вашу базу 1С» (`components/onboarding/OnboardingDialog.tsx`)
- Оранжевый возможно ассоциация с #d97757 (Claude.ai brand) или FOUC до загрузки темы
- В коде проекта реальный оранжевый отсутствует — палитра dark+IBM Plex+clinical-blue

## Claude Design — workflow
- Пользователь сам открывает `claude.ai/design` в браузере
- Моя задача: подготовить промпт + контекст (CLAUDE.md, скриншоты, ban-list)
- Импорт обратно через `/from-design <path>` после export ZIP
- В ОДНУ папку upload (MSG #24): «слишком много можно одну папку скинуть просто с кодом базы»
