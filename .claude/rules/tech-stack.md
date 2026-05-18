# Tech Stack (locked)

| Слой | Технология | Версия | Назначение |
|---|---|---|---|
| Frontend framework | Next.js | 15.5.x (App Router + Turbopack) | SSR + routing |
| UI library | React | 19.x | компонентная модель |
| Component lib | shadcn/ui (через @radix-ui) | latest | примитивы |
| Styling | Tailwind | 4.x | utility-first CSS |
| Fonts | IBM Plex Sans / Mono | latest | font-family |
| Backend | FastAPI | 0.115+ | API server |
| Validation | Pydantic | 2.9+ | schema validation |
| ASGI | uvicorn | 0.30+ | HTTP server |
| Storage | SQLite via aiosqlite | latest | persistent state |
| HTTP client | httpx | 0.27+ | внешние вызовы |
| LLM transport | OpenAI-compatible HTTP | — | MiMo / Claude / GPT |
| MCP transport | HTTP Streamable | spec 2024-11-05 | 1С MCP Toolkit |
| Testing — backend | pytest + pytest-asyncio | latest | unit + integration |
| Testing — frontend unit | Vitest | 4.x | components + utils |
| Testing — E2E | Playwright | 1.49+ | full-flow smoke |
| Package manager | pnpm | 11.x (fallback: npm) | frontend deps |
| Desktop wrapper | Electron + electron-builder | 33+ / 26+ | Windows installer |
| Backend bundling | PyInstaller | 6+ | one-file exe |
| Python | CPython | 3.12 | backend runtime |
| Node | Node.js | 22.14 | frontend runtime |
| Vector store (Phase 10) | sqlite-vec | TBD | embeddings + RAG |
| Embeddings (Phase 10) | OpenAI text-embedding-3-small | latest | default provider |

## Что НЕ используем (явно отвергнуто)

- ❌ Docker для аналитика (только Electron installer per Phase 7)
- ❌ Ollama / local LLM (cloud-only per pivot 2026-05-08, см. `memory/llm-providers.md`)
- ❌ Inter font (per design-bans.md)
- ❌ npm + create-react-app (используем pnpm + Next 15 App Router)
- ❌ class-components React (только hooks + function components)
- ❌ Redux/Zustand state managers (React Context достаточно для current scope)
- ❌ Yarn (pnpm выбран для disk efficiency)

## Версия привязки

При обновлении любой из главных версий — обновить **этот файл** + проверить smoke в `.planning/phases/<latest>/SMOKE.md`.
