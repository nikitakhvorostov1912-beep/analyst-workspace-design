from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatAttachment(BaseModel):
    """Один прикреплённый к сообщению файл — клиент base64-кодирует содержимое."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=255)
    mime: str = Field(default="", max_length=200)
    content_base64: str = Field(min_length=1)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message: str
    session_id: str | None = None
    channel_id: str = Field(min_length=1)
    # api key пробрасывается через header X-LLM-API-Key, в теле НЕ передаётся
    # Опциональные прикреплённые файлы — PDF, DOCX, XLSX, TXT, CSV, JSON, XML, MD.
    # Cap MAX_ATTACHMENTS_PER_MESSAGE=5 на сообщение, MAX_TEXT_PER_FILE=50000 символов
    # после извлечения. Изображения пока не поддерживаются (Phase 2 — multimodal).
    attachments: list[ChatAttachment] = Field(default_factory=list, max_length=5)


class ChatSSEEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str
    data: dict


class MCPPingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_version: str
    tool_count: int
    session_id: str
    duration_ms: int


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]


# Тип подключения к 1С MCP: "embedded" — EPF MCP_Toolkit на машине аналитика
# слушает локально на http://localhost:<port>/mcp; "proxy" — EPF на сервере, доступ
# через HF Spaces / Cloudflare Tunnel с channel-параметром.
# Для аналитика два сценария принципиально разные: локальный embedded работает
# только пока его 1С открыта, proxy — пока обработка запущена на удалённом сервере.
MCPKind = Literal["embedded", "proxy"]


class MCPConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    endpoint: str
    channel: str | None = None
    anon_enabled: bool = False
    kind: MCPKind = "embedded"
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


class MCPConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=200)
    endpoint: str = Field(min_length=1)
    channel: str | None = None
    anon_enabled: bool = False
    kind: MCPKind = "embedded"

    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("endpoint должен начинаться с http:// или https://")
        return v

    def model_post_init(self, _context: object) -> None:
        self.validate_endpoint(self.endpoint)
        if self.kind == "proxy" and not (self.channel and self.channel.strip()):
            raise ValueError(
                "Для прокси-подключения нужно указать канал — параметр channel пустой."
            )


class MCPConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    endpoint: str | None = None
    channel: str | None = None
    anon_enabled: bool | None = None
    kind: MCPKind | None = None

    def model_post_init(self, _context: object) -> None:
        if self.endpoint is not None:
            if not (self.endpoint.startswith("http://") or self.endpoint.startswith("https://")):
                raise ValueError("endpoint должен начинаться с http:// или https://")


class MCPConnectionFull(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    endpoint: str
    channel: str | None = None
    anon_enabled: bool = False
    kind: MCPKind = "embedded"
    last_seen_at: datetime | None = None
    created_at: datetime


class MCPConnectionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connections: list[MCPConnectionFull]


class MCPPingWithTimestampResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_version: str
    tool_count: int
    session_id: str
    duration_ms: int
    last_seen_at: datetime | None = None
    # Phase: видимость стека для аналитика. kind — embedded/proxy (echo из БД),
    # server_name — название сервера из MCP initialize, tool_names — список первых
    # 20 имён инструментов для UI-чипов в /status.
    kind: MCPKind = "embedded"
    server_name: str = ""
    tool_names: list[str] = Field(default_factory=list)


class AuxMCPStatus(BaseModel):
    """Статус одного вспомогательного MCP-сервера (например bsl-context).

    Используется в /diagnostics/aux чтобы /status видел весь стек, не только
    основное подключение к 1С.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    configured: bool
    status: Literal["ok", "error", "not_configured"]
    tool_count: int = 0
    error_hint: str | None = None


class AuxDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aux: list[AuxMCPStatus] = Field(default_factory=list)


class EnvDiagnosticsResponse(BaseModel):
    """Sanitized снимок окружения backend для UI «Диагностика».

    НЕ содержит секретов (API ключи, пароли). Аналитик видит:
    - откуда читается LLM-дефолт (адрес + модель)
    - какие пути к BSL-справочнику настроены (если есть)
    - какие origins разрешены для CORS (что важно при «фронт не подключается»)
    - какие переменные окружения backend ожидает но не получил
    """

    model_config = ConfigDict(extra="forbid")

    app_version: str
    environment: Literal["dev", "prod"]
    default_llm_endpoint: str
    default_llm_model: str
    # Aux MCP: bsl-context (см. config.bsl_context_*)
    bsl_context_jar: str  # пустая строка = не настроено
    bsl_context_java: str
    bsl_context_platform_path: str
    cors_origins: list[str]
    # SQLite — только относительный путь, чтобы аналитик понимал где база
    sqlite_path: str
    # Имена переменных, которые backend читает — для подсказки «как настроить»
    env_var_names: dict[str, str] = Field(default_factory=dict)


# --- Sessions CRUD models (Plan 2.3) ---


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = None
    channel_id: str = Field(min_length=1)


class SessionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    channel_id: str
    updated_at: datetime
    message_count: int


class SessionsGrouped(BaseModel):
    model_config = ConfigDict(extra="forbid")

    today: list[SessionListItem] = []
    yesterday: list[SessionListItem] = []
    this_week: list[SessionListItem] = []
    earlier: list[SessionListItem] = []


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    channel_id: str
    created_at: datetime
    updated_at: datetime


class MessageRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: Literal["user", "assistant", "tool"]
    content: str | None
    tool_calls: list[dict[str, Any]] | None
    cards: list[dict[str, Any]] | None
    duration_ms: int | None
    created_at: datetime


class SessionMessages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[MessageRow]


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)


class ConfirmRequest(BaseModel):
    """Тело POST /chat/confirm (SEC-01)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_call_id: str = Field(min_length=1)
    approved: bool


# --- LogCard load-more models (Plan 03-04) ---


class LoadMoreRequest(BaseModel):
    """Тело POST /sessions/{sid}/messages/{mid}/cards/{cid}/load-more."""

    model_config = ConfigDict(extra="forbid", strict=True)

    cursor: str = Field(min_length=1)


class LogPagePayload(BaseModel):
    """Ответ load-more endpoint: страница записей журнала."""

    model_config = ConfigDict(extra="forbid")

    entries: list[dict[str, Any]]
    next_cursor: str | None = None


# --- Deanonymize models (Plan 04-01) ---

_ANON_TOKEN_PATTERN = r"^\[[A-Z]+-\d+\]$"


def _validate_token(v: str) -> str:
    import re
    if not re.match(_ANON_TOKEN_PATTERN, v):
        raise ValueError(f"invalid anon token format: {v!r}")
    return v


class DeanonymizeRequest(BaseModel):
    """Тело POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize.

    tokens: список anon-токенов вида [ORG-001], [INN-001] и т.д.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    tokens: list[str] = Field(min_length=1, max_length=200)

    @classmethod
    def validate_tokens(cls, tokens: list[str]) -> list[str]:
        import re
        for tok in tokens:
            if not re.match(_ANON_TOKEN_PATTERN, tok):
                raise ValueError(f"invalid anon token format: {tok!r}")
        return tokens

    def model_post_init(self, _context: object) -> None:
        import re
        for tok in self.tokens:
            if not re.match(_ANON_TOKEN_PATTERN, tok):
                raise ValueError(f"invalid anon token format: {tok!r}")


class DeanonymizeResponse(BaseModel):
    """Ответ deanonymize endpoint."""

    model_config = ConfigDict(extra="forbid")

    mapping: dict[str, str]


# --- Search models (Plan 04-03) ---


class SearchResultItem(BaseModel):
    """Один результат полнотекстового поиска."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    session_title: str | None
    message_id: str
    snippet: str
    created_at: str
    channel_id: str


class SearchResponse(BaseModel):
    """Ответ GET /search."""

    model_config = ConfigDict(extra="forbid")

    results: list[SearchResultItem]
    total: int
    query: str


# --- Metadata suggest models (Plan 04-03) ---


class MetadataSuggestItem(BaseModel):
    """Один объект метаданных из кеша."""

    model_config = ConfigDict(extra="forbid")

    object_type: str
    name: str
    full_path: str
    presentation: str | None = None


class MetadataSuggestResponse(BaseModel):
    """Ответ GET /channels/{id}/metadata-suggest."""

    model_config = ConfigDict(extra="forbid")

    items: list[MetadataSuggestItem]
    cached: bool
    stale: bool = False


# --- LLM Config models (Plan 5.1) ---


class LLMConfigCreate(BaseModel):
    """Тело POST /llm-config. API ключ передаётся через header, не хранится."""

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=100)
    temperature: float = Field(ge=0.0, le=2.0, default=0.3)

    def model_post_init(self, _context: object) -> None:
        if not (self.endpoint.startswith("http://") or self.endpoint.startswith("https://")):
            raise ValueError("endpoint должен начинаться с http:// или https://")


class LLMConfigUpdate(BaseModel):
    """Тело PATCH /llm-config/default. Все поля опциональны."""

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    def model_post_init(self, _context: object) -> None:
        if self.endpoint is not None:
            if not (self.endpoint.startswith("http://") or self.endpoint.startswith("https://")):
                raise ValueError("endpoint должен начинаться с http:// или https://")


class LLMConfigResponse(BaseModel):
    """Ответ /llm-config. API ключ ОТСУТСТВУЕТ (T-05-01)."""

    model_config = ConfigDict(extra="forbid")

    id: str  # всегда "default"
    endpoint: str
    model: str
    temperature: float
    updated_at: datetime | None = None


class LLMConfigTestRequest(BaseModel):
    """Тело POST /llm-config/test. API ключ — в header X-LLM-API-Key.

    UX: temperature опциональная — клиенты обычно отправляют тот же payload,
    что и в /llm-config (Create/Update). Игнорируем её в test endpoint
    (test шлёт `max_tokens=1` без temperature), но не отвергаем.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    endpoint: str
    model: str
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class LLMConfigTestResponse(BaseModel):
    """Ответ POST /llm-config/test.

    error_code values: invalid_key, network_error, timeout, server_error, invalid_endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
