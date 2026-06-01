# 07 — Code Skeletons для старта

> Готовые скелеты ключевых классов и компонентов. Можно копировать в проект как стартовую точку.

## Backend (Python / FastAPI)

### `backend/app/models/connection.py` (обновлённая)

```python
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship


class MCPConnection(SQLModel, table=True):
    """Подключение к MCP-серверу (1С-база или вспомогательный MCP)."""
    __tablename__ = "mcp_connection"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    endpoint: str
    transport: Literal["http", "stdio"] = "http"

    # Capability discovery
    mode: Literal["epf", "cfe", "external", "legacy"] | None = None
    configuration: str | None = None
    platform_version: str | None = None
    extension_version: str | None = None
    ssl_version: str | None = None
    host: str | None = None
    capabilities: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )

    # Lifecycle
    is_active: bool = True
    last_handshake_at: datetime | None = None
    last_error: str | None = None

    # UI hints
    color: str | None = None
    icon: str | None = None

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    sessions: list["Session"] = Relationship(back_populates="connection")


# Alembic migration:
# add_capability_fields_to_connection.py
"""add capability fields to mcp_connection"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("mcp_connection", sa.Column("mode", sa.String(20), nullable=True))
    op.add_column("mcp_connection", sa.Column("configuration", sa.String(100), nullable=True))
    op.add_column("mcp_connection", sa.Column("platform_version", sa.String(50), nullable=True))
    op.add_column("mcp_connection", sa.Column("extension_version", sa.String(50), nullable=True))
    op.add_column("mcp_connection", sa.Column("ssl_version", sa.String(50), nullable=True))
    op.add_column("mcp_connection", sa.Column("host", sa.String(100), nullable=True))
    op.add_column("mcp_connection", sa.Column("capabilities", sa.JSON, nullable=False, server_default="[]"))
    op.add_column("mcp_connection", sa.Column("last_handshake_at", sa.DateTime, nullable=True))
    op.add_column("mcp_connection", sa.Column("last_error", sa.Text, nullable=True))


def downgrade():
    op.drop_column("mcp_connection", "last_error")
    op.drop_column("mcp_connection", "last_handshake_at")
    op.drop_column("mcp_connection", "capabilities")
    op.drop_column("mcp_connection", "host")
    op.drop_column("mcp_connection", "ssl_version")
    op.drop_column("mcp_connection", "extension_version")
    op.drop_column("mcp_connection", "platform_version")
    op.drop_column("mcp_connection", "configuration")
    op.drop_column("mcp_connection", "mode")
```

### `backend/app/services/capability_discovery.py`

```python
from dataclasses import dataclass
from typing import Literal

from app.models.connection import MCPConnection


@dataclass
class ConnectionMetadata:
    mode: Literal["epf", "cfe", "external", "legacy"]
    configuration: str | None = None
    platform_version: str | None = None
    extension_version: str | None = None
    ssl_version: str | None = None
    host: str | None = None
    features: list[str] = None

    def __post_init__(self):
        if self.features is None:
            self.features = []


def parse_capabilities(initialize_response: dict) -> ConnectionMetadata:
    """Парсит MCP initialize ответ → ConnectionMetadata."""
    capabilities = initialize_response.get("capabilities", {})
    exp = capabilities.get("experimental", {})
    analyst = exp.get("analyst-1c")

    if not analyst:
        # Legacy MCP — assume basic capabilities
        return _infer_from_tools(initialize_response)

    return ConnectionMetadata(
        mode=analyst.get("mode", "legacy"),
        configuration=analyst.get("configuration"),
        platform_version=analyst.get("platform"),
        extension_version=analyst.get("extensionVersion"),
        ssl_version=analyst.get("ssl_version"),
        host=analyst.get("host"),
        features=analyst.get("features", []),
    )


def _infer_from_tools(initialize_response: dict) -> ConnectionMetadata:
    """Backwards compat: выводит capabilities из advertised tools."""
    tools_dict = initialize_response.get("capabilities", {}).get("tools", {})

    inferred = []
    if "execute_query" in tools_dict:
        inferred.append("mcp.execute_query")
    if "execute_code" in tools_dict:
        inferred.append("mcp.execute_code")
    if "get_metadata" in tools_dict:
        inferred.append("mcp.get_metadata")
    if "get_event_log" in tools_dict:
        inferred.append("mcp.get_event_log")
    # ... heuristics для остальных

    return ConnectionMetadata(mode="legacy", features=inferred)


async def discover_capabilities(connection: MCPConnection, db) -> None:
    """Опрашивает MCP и обновляет capabilities в БД."""
    from app.services.mcp_clients.factory import create_mcp_client

    client = create_mcp_client(connection)

    try:
        init_response = await client.initialize()
        metadata = parse_capabilities(init_response)

        connection.mode = metadata.mode
        connection.configuration = metadata.configuration
        connection.platform_version = metadata.platform_version
        connection.extension_version = metadata.extension_version
        connection.ssl_version = metadata.ssl_version
        connection.host = metadata.host
        connection.capabilities = metadata.features
        connection.last_handshake_at = datetime.utcnow()
        connection.last_error = None

    except Exception as e:
        connection.last_error = str(e)
        connection.is_active = False

    await db.commit()
```

### `backend/app/services/mcp_orchestrator.py`

```python
from typing import Any

from app.models.connection import MCPConnection
from app.services.mcp_clients.base import MCPClient
from app.services.mcp_clients.factory import create_mcp_client


class MCPOrchestrator:
    """Координирует несколько MCP-клиентов под одной сессией."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._connections: dict[str, MCPConnection] = {}

    def register(self, connection: MCPConnection) -> None:
        """Регистрирует MCP подключение."""
        prefix = self._make_prefix(connection)
        self._clients[prefix] = create_mcp_client(connection)
        self._connections[prefix] = connection

    def unregister(self, connection_id: str) -> None:
        prefix = next(
            (p for p, c in self._connections.items() if str(c.id) == connection_id),
            None,
        )
        if prefix:
            del self._clients[prefix]
            del self._connections[prefix]

    async def list_unified_tools(self) -> list[dict[str, Any]]:
        """Возвращает все tools всех MCP с префиксами."""
        unified = []
        for prefix, client in self._clients.items():
            tools = await client.list_tools()
            for tool in tools:
                tool_copy = tool.model_copy()
                tool_copy.name = f"{prefix}.{tool.name}"
                # Augment description с указанием источника
                tool_copy.description = (
                    f"[{self._connections[prefix].name}] {tool_copy.description}"
                )
                unified.append(tool_copy.model_dump())
        return unified

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Маршрутизирует tool call к нужному MCP."""
        if "." not in name:
            raise ValueError(f"Tool name must have prefix: {name}")

        prefix, tool_name = name.split(".", 1)

        if prefix not in self._clients:
            raise ValueError(f"Unknown MCP prefix: {prefix}")

        return await self._clients[prefix].call_tool(tool_name, arguments)

    def _make_prefix(self, connection: MCPConnection) -> str:
        """Префикс для tools этого MCP. На основе name (slug)."""
        # "Транзит" → "transit"
        # "ИТС + Напарник" → "buddy"
        # "Синтаксис платформы" → "context"
        # Manual mapping в БД (поле short_name?) или slugify
        return _slugify(connection.name)[:20]


def _slugify(text: str) -> str:
    """Простой slugify для русского текста."""
    # transliteration → lowercase → remove non-alphanum → join with _
    # ... implementation
    pass
```

### `backend/app/services/rag/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Citation:
    source: str  # "v8std" / "ssl_api" / "platform_hbk"
    id: str
    title: str
    snippet: str
    full_url: str | None = None
    metadata: dict | None = None


class RAGRetriever(ABC):
    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[Citation]:
        ...

    @abstractmethod
    async def fetch(self, citation_id: str) -> str:
        """Полный текст citation по ID."""
        ...


class RAGIndexer(ABC):
    @abstractmethod
    async def index(self, force: bool = False) -> dict:
        """Индексирует источник. Возврат: статистика."""
        ...

    @abstractmethod
    async def get_status(self) -> dict:
        """Статус индекса: количество, дата, ошибки."""
        ...
```

### `backend/app/services/rag/v8std.py`

```python
import re
from pathlib import Path
from typing import Iterator

from app.services.rag.base import Citation, RAGIndexer, RAGRetriever


class V8stdIndexer(RAGIndexer):
    """Индексирует 317 стандартов разработки 1С."""

    def __init__(self, source_path: Path, vector_store):
        self.source_path = source_path
        self.vector_store = vector_store

    async def index(self, force: bool = False) -> dict:
        if not force and await self._is_indexed():
            return {"status": "already_indexed"}

        docs = list(self._iter_documents())
        embeddings = await self._embed_batch([d["text"] for d in docs])

        for doc, emb in zip(docs, embeddings):
            await self.vector_store.insert(
                collection="v8std",
                id=doc["id"],
                embedding=emb,
                metadata=doc,
            )

        return {"status": "ok", "count": len(docs)}

    def _iter_documents(self) -> Iterator[dict]:
        """Итерация по 317 стандартам."""
        for md_file in self.source_path.glob("**/*.md"):
            content = md_file.read_text(encoding="utf-8")

            # Парсинг frontmatter
            front_match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
            if front_match:
                fm, body = front_match.groups()
                meta = _parse_yaml(fm)
            else:
                meta = {}
                body = content

            std_id = meta.get("id") or md_file.stem  # "СтРД-783"
            title = meta.get("title") or _extract_first_h1(body)
            severity = meta.get("severity") or "info"

            # Разбивка на чанки (по секциям)
            for chunk_idx, chunk in enumerate(_split_into_chunks(body)):
                yield {
                    "id": f"{std_id}_chunk_{chunk_idx}",
                    "source": "v8std",
                    "std_id": std_id,
                    "title": title,
                    "severity": severity,
                    "text": chunk,
                    "url": f"https://its.1c.ru/db/v8std/content/{std_id}",
                }


class V8stdRetriever(RAGRetriever):
    def __init__(self, vector_store, embedding_client):
        self.vector_store = vector_store
        self.embedding_client = embedding_client

    async def search(self, query: str, top_k: int = 3) -> list[Citation]:
        query_emb = await self.embedding_client.embed([query])
        results = await self.vector_store.search(
            collection="v8std", embedding=query_emb[0], top_k=top_k
        )

        return [
            Citation(
                source="v8std",
                id=r["std_id"],
                title=r["title"],
                snippet=r["text"][:300],
                full_url=r["url"],
                metadata={"severity": r["severity"]},
            )
            for r in results
        ]

    async def fetch(self, citation_id: str) -> str:
        return await self.vector_store.fetch_all_chunks(
            collection="v8std", std_id=citation_id
        )
```

### `backend/app/services/bsl_lint/runner.py`

```python
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from app.services.bsl_lint.parser import parse_diagnostics


BSL_LS_JAR = Path(__file__).parent.parent.parent.parent / "bin" / "bsl-language-server-0.30.0-rc.2-exec.jar"
JAVA_HOME = Path(__file__).parent.parent.parent.parent / "bin" / "jre-17"


class BSLLintRunner:
    def __init__(self, cache=None):
        self.cache = cache
        self.java_path = JAVA_HOME / "bin" / "java"

    async def lint(self, code: str) -> list[dict]:
        """Прогоняет код через BSL LS, возвращает diagnostics."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        # Cache
        if self.cache:
            cached = await self.cache.get(f"bsl_lint:{code_hash}")
            if cached:
                return cached

        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bsl", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = Path(f.name)

        try:
            # Run BSL LS
            proc = await asyncio.create_subprocess_exec(
                str(self.java_path),
                "-jar",
                str(BSL_LS_JAR),
                "--analyze",
                "--src",
                str(tmp_path.parent),
                "--reporter",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=10.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise RuntimeError("BSL LS timeout")

            if proc.returncode != 0:
                raise RuntimeError(f"BSL LS failed: {stderr.decode()}")

            # Parse output
            report = json.loads(stdout.decode())
            diagnostics = parse_diagnostics(report)

            # Cache
            if self.cache:
                await self.cache.set(f"bsl_lint:{code_hash}", diagnostics)

            return diagnostics

        finally:
            tmp_path.unlink(missing_ok=True)
```

## Frontend (TypeScript / Next.js / React)

### `frontend/lib/capabilities.ts`

```typescript
export type Capability =
  // MCP base
  | 'mcp.execute_query'
  | 'mcp.execute_code'
  | 'mcp.get_metadata'
  | 'mcp.get_event_log'
  | 'mcp.find_references'
  | 'mcp.get_access_rights'
  | 'mcp.bsl_syntax_help'
  | 'connector.http_request'
  // tools_ui
  | 'tools_ui.query_console'
  | 'tools_ui.code_console'
  | 'tools_ui.dedup_finder'
  // CFE
  | 'cfe.persistent_http'
  | 'cfe.event_subscriptions'
  | 'cfe.method_overrides'
  | 'cfe.privileged_mode'
  | 'cfe.monitoring_register'
  | 'cfe.activity_stream'
  | 'cfe.posting_trace'
  | 'cfe.scheduled_jobs'
  | 'cfe.custom_commands'
  | 'cfe.settings_storage'
  | 'cfe.hot_reload_metadata'
  | 'auth.hmac_session'
  // external MCP
  | 'external.its_search'
  | 'external.its_fetch'
  | 'external.platform_search'
  | 'external.code_review'
  | 'external.documentation_diff'
  // backend services (не от MCP)
  | 'service.rag_v8std'
  | 'service.rag_ssl'
  | 'service.rag_platform'
  | 'service.bsl_ls'
  | 'service.metavision';


export type Mode = 'epf' | 'cfe' | 'external' | 'legacy';


export interface MCPConnection {
  id: string;
  name: string;
  endpoint: string;
  transport: 'http' | 'stdio';
  mode: Mode | null;
  configuration: string | null;
  platform_version: string | null;
  extension_version: string | null;
  capabilities: Capability[];
  is_active: boolean;
  last_handshake_at: string | null;
  last_error: string | null;
}


export const MODE_BADGES: Record<Mode, { label: string; className: string }> = {
  epf: {
    label: 'EPF',
    className: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  cfe: {
    label: 'CFE',
    className: 'bg-signal/15 text-signal border-signal/30',
  },
  external: {
    label: 'EXT',
    className: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
  },
  legacy: {
    label: 'LEGACY',
    className: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  },
};
```

### `frontend/hooks/useCapability.ts`

```typescript
import { useActiveConnection, useConnections } from '@/stores/connections';
import type { Capability } from '@/lib/capabilities';


export function useCapability(...required: Capability[]): boolean {
  const conn = useActiveConnection();
  if (!conn?.capabilities) return false;
  return required.every(cap => conn.capabilities.includes(cap));
}


export function useAllConnectionsCapability(...required: Capability[]): boolean {
  /** True если хотя бы одно подключение имеет все required. */
  const conns = useConnections();
  return conns.some(conn =>
    conn.is_active &&
    required.every(cap => conn.capabilities.includes(cap))
  );
}


export function useMode() {
  const conn = useActiveConnection();
  return conn?.mode ?? null;
}
```

### `frontend/lib/feature-modules.ts`

```typescript
import type { Capability } from './capabilities';
import type { ComponentType } from 'react';


type FeatureModule = {
  name: string;
  description: string;
  requires: Capability[];
  component: () => Promise<{ default: ComponentType<any> }>;
  placement?: 'sidebar' | 'header' | 'card' | 'onboarding';
  cardType?: string;
  enhances?: string[];
};


export const FEATURE_MODULES = {
  activity_stream: {
    name: 'Поток активности',
    description: 'Realtime-события в базе 1С',
    requires: ['cfe.activity_stream'],
    component: () => import('@/components/cfe/ActivityStreamSidebar'),
    placement: 'sidebar',
  } as FeatureModule,

  posting_trace_card: {
    name: 'Трассировка проведения',
    description: 'Детальная трассировка ОбработкаПроведения "до/после"',
    requires: ['cfe.posting_trace'],
    component: () => import('@/components/cfe/PostingTraceCard'),
    placement: 'card',
    cardType: 'PostingTraceCard',
  } as FeatureModule,

  bsl_diagnostics: {
    name: 'BSL Диагностики',
    description: 'Проверка BSL кода через Language Server',
    requires: ['service.bsl_ls'],
    component: () => import('@/components/lint/BSLDiagnosticsCard'),
    placement: 'card',
    cardType: 'BSLDiagnosticsCard',
    enhances: ['CodeCard'],
  } as FeatureModule,

  standards_citation: {
    name: 'Стандарты ИТС',
    description: 'Цитирование стандартов разработки в коде',
    requires: ['service.rag_v8std'],
    component: () => import('@/components/rag/StandardsCitationBlock'),
    placement: 'card',
    enhances: ['CodeCard'],
  } as FeatureModule,

  metavision_graph: {
    name: 'MetaVision граф',
    description: 'Интерактивный граф вызовов функций',
    requires: ['service.metavision'],
    component: () => import('@/components/analysis/MetaVisionGraphCard'),
    placement: 'card',
    cardType: 'MetaVisionGraphCard',
  } as FeatureModule,

  // ... остальные
} as const;


export type FeatureModuleKey = keyof typeof FEATURE_MODULES;
```

### `frontend/components/upgrade/UpgradeCTA.tsx`

```typescript
'use client';

import type { Capability, Mode } from '@/lib/capabilities';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ArrowUpRight } from 'lucide-react';


interface UpgradeCTAProps {
  feature: string;
  currentMode: Mode | null;
  requires: Capability[];
  description: string;
  benefits: string[];
  cta?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
}


export function UpgradeCTA({
  feature,
  currentMode,
  requires,
  description,
  benefits,
  cta,
}: UpgradeCTAProps) {
  const isCFEFeature = requires.some(r => r.startsWith('cfe.'));
  const isServiceFeature = requires.some(r => r.startsWith('service.'));

  let upgradePath = '';
  if (isCFEFeature && currentMode === 'epf') {
    upgradePath = 'Перейдите на CFE-расширение';
  } else if (isServiceFeature) {
    upgradePath = 'Запустите соответствующий сервис в Settings';
  } else {
    upgradePath = 'Подключите подходящий MCP';
  }

  return (
    <Card className="p-6 border-zinc-800 bg-zinc-950/50">
      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-mono uppercase text-zinc-500">
              Доступно в расширенном режиме
            </span>
          </div>
          <h3 className="text-lg font-semibold">{feature}</h3>
          <p className="text-sm text-zinc-400 mt-1">{description}</p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-mono uppercase text-zinc-500">
            Что даёт:
          </p>
          <ul className="space-y-1">
            {benefits.map((b, i) => (
              <li key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                <span className="text-signal">•</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="pt-2 border-t border-zinc-800">
          <p className="text-xs text-zinc-500 mb-3">{upgradePath}</p>
          {cta && (
            <Button
              variant="outline"
              size="sm"
              className="border-signal/30 text-signal hover:bg-signal/10"
              {...(cta.href ? { asChild: true } : {})}
              {...(cta.onClick ? { onClick: cta.onClick } : {})}
            >
              {cta.href ? (
                <a href={cta.href} target="_blank" rel="noopener">
                  {cta.label}
                  <ArrowUpRight className="ml-1 h-3 w-3" />
                </a>
              ) : (
                <>
                  {cta.label}
                  <ArrowUpRight className="ml-1 h-3 w-3" />
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
```

## 1С (BSL для EPF/CFE)

### `АП_MCPServerHTTP.bsl` (общий модуль)

```bsl
// АналитикПлюс — MCP HTTP Server
// Заимствовано из MCP_Toolkit v1.7.0 с адаптацией под двухрежимность
//
// Лицензия: <своя>
// Источник базового кода: MCP Toolkit (с разрешения автора)

#Область ПрограммныйИнтерфейс

// Возвращает capability response для MCP initialize.
// Различается для EPF и CFE.
//
Функция ПолучитьCapabilityResponse() Экспорт

	Ответ = Новый Структура;
	Ответ.Вставить("protocolVersion", "2024-11-05");
	Ответ.Вставить("serverInfo", СформироватьServerInfo());
	Ответ.Вставить("capabilities", СформироватьCapabilities());

	Возврат Ответ;

КонецФункции

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Функция СформироватьServerInfo()

	Информация = Новый Структура;

	#Если Расширение("АналитикПлюс") Тогда
		Информация.Вставить("name", "АналитикПлюс");
		Информация.Вставить("version", "2.0.0");
	#Иначе
		Информация.Вставить("name", "АналитикLite");
		Информация.Вставить("version", "2.0.0");
	#КонецЕсли

	Возврат Информация;

КонецФункции

Функция СформироватьCapabilities()

	Capabilities = Новый Структура;
	Capabilities.Вставить("tools", Новый Структура);

	Experimental = Новый Структура;
	Experimental.Вставить("analyst-1c", СформироватьAnalyst1CCapabilities());

	Capabilities.Вставить("experimental", Experimental);

	Возврат Capabilities;

КонецФункции

Функция СформироватьAnalyst1CCapabilities()

	Аналитик = Новый Структура;

	#Если Расширение("АналитикПлюс") Тогда
		// CFE mode — 23 capabilities
		Аналитик.Вставить("mode", "cfe");
		Аналитик.Вставить("extensionVersion", "2.0.5");
		Аналитик.Вставить("features", СписокCFEFeatures());
	#Иначе
		// EPF mode — 8 capabilities
		Аналитик.Вставить("mode", "epf");
		Аналитик.Вставить("epfVersion", "2.0.0");
		Аналитик.Вставить("features", СписокEPFFeatures());
	#КонецЕсли

	// Общая metadata
	Аналитик.Вставить("configuration", ОпределитьИмяКонфигурации());
	Аналитик.Вставить("platform", СтрокаСистемнойИнформации(Метаданные.ВерсияПлатформы));
	Аналитик.Вставить("host", СтрокаСоединенияИнформационнойБазы());

	Возврат Аналитик;

КонецФункции

Функция СписокEPFFeatures()
	Список = Новый Массив;
	Список.Добавить("mcp.execute_query");
	Список.Добавить("mcp.execute_code");
	Список.Добавить("mcp.get_metadata");
	Список.Добавить("mcp.get_event_log");
	Список.Добавить("mcp.find_references");
	Список.Добавить("mcp.get_access_rights");
	Список.Добавить("mcp.bsl_syntax_help");
	Список.Добавить("connector.http_request");
	Возврат Список;
КонецФункции

Функция СписокCFEFeatures()
	Список = СписокEPFFeatures();
	Список.Добавить("tools_ui.query_console");
	Список.Добавить("tools_ui.code_console");
	Список.Добавить("tools_ui.dedup_finder");
	Список.Добавить("cfe.persistent_http");
	Список.Добавить("cfe.event_subscriptions");
	Список.Добавить("cfe.method_overrides");
	Список.Добавить("cfe.privileged_mode");
	Список.Добавить("cfe.monitoring_register");
	Список.Добавить("cfe.activity_stream");
	Список.Добавить("cfe.posting_trace");
	Список.Добавить("cfe.scheduled_jobs");
	Список.Добавить("cfe.custom_commands");
	Список.Добавить("cfe.settings_storage");
	Список.Добавить("cfe.hot_reload_metadata");
	Список.Добавить("auth.hmac_session");
	Возврат Список;
КонецФункции

Функция ОпределитьИмяКонфигурации()
	Возврат Метаданные.Имя;
КонецФункции

#КонецОбласти
```

### `АП_AuthHMAC.bsl` (общий модуль для CFE)

```bsl
// АналитикПлюс — HMAC SSO для аутентификации web-приложения

#Область ПрограммныйИнтерфейс

// Генерирует HMAC-токен для текущего пользователя 1С.
// Используется веб-приложением для seamless авторизации.
//
Функция СгенерироватьТокен() Экспорт

	Данные = Новый Структура;
	Данные.Вставить("username", ИмяПользователя());
	Данные.Вставить("user_uid", Строка(ПараметрыСеанса.ТекущийПользователь.УникальныйИдентификатор()));
	Данные.Вставить("base_id", СтрокаСоединенияИнформационнойБазы());
	Данные.Вставить("expires", ТекущаяДатаСеанса() + 3600);  // 1 час
	Данные.Вставить("issued_at", ТекущаяДатаСеанса());

	ПолезнаяНагрузка = ЗаписьJSONВСтроку(Данные);

	СекретныйКлюч = ПолучитьИлиСоздатьСекрет();

	HMAC = РассчитатьHMAC_SHA256(ПолезнаяНагрузка, СекретныйКлюч);

	Токен = Base64String(ПолучитьДвоичныеДанныеИзСтроки(ПолезнаяНагрузка))
		+ "."
		+ Base64String(HMAC);

	Возврат Токен;

КонецФункции

Функция ПроверитьТокен(Токен) Экспорт

	Части = СтрРазделить(Токен, ".");
	Если Части.Количество() <> 2 Тогда
		Возврат Ложь;
	КонецЕсли;

	ПолезнаяНагрузкаBase64 = Части[0];
	HMACBase64 = Части[1];

	ПолезнаяНагрузка = ПолучитьСтрокуИзДвоичныхДанных(Base64Значение(ПолезнаяНагрузкаBase64));

	СекретныйКлюч = ПолучитьСекрет();
	Если СекретныйКлюч = Неопределено Тогда
		Возврат Ложь;
	КонецЕсли;

	ОжидаемыйHMAC = РассчитатьHMAC_SHA256(ПолезнаяНагрузка, СекретныйКлюч);
	ОжидаемыйHMACBase64 = Base64String(ОжидаемыйHMAC);

	Если HMACBase64 <> ОжидаемыйHMACBase64 Тогда
		Возврат Ложь;
	КонецЕсли;

	// Проверка expires
	Данные = ПрочитатьJSON(ПолезнаяНагрузка);
	Если Данные.expires < ТекущаяДатаСеанса() Тогда
		Возврат Ложь;
	КонецЕсли;

	Возврат Истина;

КонецФункции

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Функция ПолучитьИлиСоздатьСекрет()
	// Хранится в констатной или ХранилищеНастроек
	// ...
КонецФункции

Функция РассчитатьHMAC_SHA256(Сообщение, Ключ)
	// Использование Менеджер криптографии или внешней компоненты КриптоПро
	// ...
КонецФункции

#КонецОбласти
```

Это **skeleton** — реальные реализации будут уточнены в Phase 12 и Phase 13.
