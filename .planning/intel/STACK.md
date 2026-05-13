# Stack Intel

**Source:** Pre-loaded from project design phase + global CLAUDE.md preferences.

## Frontend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Framework | Next.js | 15.x (App Router) | RSC + streaming + SSE support out of box |
| UI Library | React | 19.x | Latest stable, RSC-compatible |
| Styling | Tailwind CSS | 4.x | Utility-first, dark theme via class |
| Components | shadcn/ui | latest | Copy-paste primitives, full control |
| Fonts | IBM Plex Sans + IBM Plex Mono | latest | Поддержка кириллицы, не overused |
| State | React Query / SWR (TBD) | TBD | Для server state (sessions, messages) |
| Forms | React Hook Form + Zod | latest | Type-safe validation |
| Markdown | react-markdown + remark-gfm | latest | Render assistant responses |
| Icons | lucide-react | latest | Tree-shakeable, consistent |
| Package Manager | pnpm | 9.x | Fast, monorepo-friendly |

## Backend

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Framework | FastAPI | 0.115+ | Async, Pydantic v2, OpenAPI auto-docs |
| Validation | Pydantic | 2.x | Strict types, fast |
| ASGI Server | Uvicorn (dev) / Gunicorn+Uvicorn (prod) | latest | Standard для FastAPI |
| HTTP Client | httpx | latest | Async + streaming + типизация |
| LLM SDK | openai | 1.x | OpenAI-compatible API client (works for Xiaomi MiMo etc.) |
| MCP Client | custom (httpx-based) | — | Streamable HTTP transport (JSON-RPC 2.0 over HTTP/SSE) |
| Database | SQLite + aiosqlite | 3.x | Embedded, single-file, sufficient для MVP |
| Migrations | Alembic | latest | DDL versioning |
| Testing | pytest + pytest-asyncio + httpx (test client) | latest | Standard FastAPI stack |
| Linting | ruff | latest | Fast, replaces black + isort + flake8 |
| Type Check | mypy or pyright | latest | Strict |

## DevOps

| Component | Choice | Version | Rationale |
|-----------|--------|---------|-----------|
| Containerization | Docker | latest | docker-compose для local |
| CI/CD | GitHub Actions | — | Lint + test on PR |
| Process Manager | Docker Compose | latest | Single-machine, no k8s |

## What NOT to use

- ❌ **Inter font** — overused в AI-output
- ❌ **Vite/CRA** — у нас Next.js full stack (SSR + RSC)
- ❌ **Redux/Zustand global state** — server state через SWR/RQ, локальный — useState
- ❌ **Bun runtime** — pnpm + node standard, меньше surprises
- ❌ **PostgreSQL для MVP** — оверкилл, SQLite single-file достаточно
- ❌ **TypeORM/Prisma** — у нас Python backend, ORM не нужен (raw SQL + aiosqlite)
- ❌ **Redis** — single-user, queue не нужен
- ❌ **GraphQL** — REST + SSE достаточно
- ❌ **WebSockets** — SSE достаточно для chat streaming (unidirectional)
