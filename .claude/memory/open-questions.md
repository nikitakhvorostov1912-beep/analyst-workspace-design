# Open questions (нужны решения)

## От пользователя ждут ответа
1. **«Оранжевый дизайн с приветственной строкой»** — это OnboardingDialog Step 1 или что-то другое? (см. design-constraints.md)
2. **Брать P1 из BACKLOG-POST-MVP сейчас?** Кандидаты:
   - Drill-down TableCard → ObjectCard по клику
   - Rate-limiting на `/chat` endpoint
   - Cross-card раскрытие anon-токенов
3. **Multi-LLM** — расширять `llm_settings` singleton до multi-profile router сейчас или в M5?
4. **STACK** — какие именно глобальные скиллы из `C:\CLOUDE_PR\.claude\skills\` и `~/.claude/skills\` подцепить к проекту?
   Мой шорт-лист: `claude-design`, `playwright-test`, `reflect`, `weekly-improve`, `inspect`. Остальные 100+ — 1С-специфичные (cf-init/epf-build/skd-compile) и НЕ применимы.
5. **SESSIONS DB** — миграция при первом запуске Electron или предзаливать в installer?
6. **LEARN engine** — Anthropic Memory Tool (управляемый) или собственный RAG (SQLite-vss + embeddings)?

## Известные технические долги
- Electron-updater не реализован (auto-update обещан в MSG #12)
- Code signing для Windows не настроен (SmartScreen warns при установке)
- pnpm vs npx неконсистентно (`pnpm` через corepack отвалился на node 22.14, в dev запускаю через `npx next`)
