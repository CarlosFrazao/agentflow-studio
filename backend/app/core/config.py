"""Configuração central via pydantic-settings.

URLs de integração (validadas pelo usuário em 2026-07-11):
- SRA:        MCP SSE em http://sra-app:3458/mcp/sse  (confirmado na Spec)
- Firecrawl:  MCP SSE em http://firecrawl-api-new:3002/mcp/sse
               com fallback REST em http://firecrawl-api-new:3002
- GitHub:     REST direto (api pública, sem MCP)
- Rede Docker externa: firecrawl_backend
- Timeout de chamada MCP ao SRA: 90s (corrige os 45s do PRD v1.1)
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "AgentFlow Studio"
    app_version: str = "1.1.0"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"

    # Static frontend dir (HTML servido em /). None = só API.
    # Default: <raiz do repo>/frontend/dist (build de produção do Vite).
    # Para servir o HTML estático legado, aponte para frontend_static.
    static_dir: Path | None = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "frontend" / "dist"
    )

    # Database (SQLite local do MVP)
    database_url: str = "sqlite+aiosqlite:///./data/agentflow.db"

    # CORS (frontend React em dev)
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- Integrações externas (MCP / REST) ---
    # SRA (Smart Research Agent) — MCP SSE remoto
    sra_mcp_url: str = "http://sra-app:3458/mcp/sse"
    sra_api_key: str | None = None  # vazio = sem auth (dev local)
    sra_call_timeout_s: float = 90.0  # corrige 45s do PRD

    # Firecrawl (self-hosted) — MCP SSE com fallback REST
    firecrawl_mcp_url: str = "http://firecrawl-api-new:3002/mcp/sse"
    firecrawl_rest_url: str = "http://firecrawl-api-new:3002"
    firecrawl_api_key: str = "local_bypass"  # placeholder aceito por instância self-hosted
    firecrawl_call_timeout_s: float = 30.0

    # GitHub API (REST direto, sem MCP)
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    github_call_timeout_s: float = 30.0

    # LLM (Gemini 2.5 Pro) — execução dos agentes
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"

    # LLM — provedores alternativos com fallback (sem chave = desativado)
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    ollama_base_url: str | None = None
    ollama_model: str = "llama3.1"

    # --- Compressão de artefatos entre agentes (Fase B1) ---
    # Modelo auxiliar barato usado apenas para resumir artefatos grandes
    # (ex: relatório do SRA) antes de repassá-los ao próximo agente.
    # Overrides opcionais por provedor: se vazio, usa o modelo padrão do provedor.
    aux_openrouter_model: str = "openai/gpt-4o-mini"
    aux_groq_model: str = "llama-3.1-8b-instant"
    aux_gemini_model: str = "gemini-2.5-flash"
    aux_ollama_model: str = "llama3.1"
    # Liga/desliga a compressão de artefatos (fail-open: se desligada, repassa cru).
    compression_enabled: bool = True
    # Só comprime artefatos acima deste tamanho (chars).
    compression_threshold_chars: int = Field(default=4000, gt=0)
    # Orçamento-alvo do resumo em tokens (proporcional ao conteúdo, com teto).
    compression_budget_tokens: int = Field(default=800, gt=0)

    # --- Memória de histórico do Conductor por orçamento de tokens (FEAT-007) ---
    # Teto de tokens acumulados das mensagens recentes injetadas no prompt do LLM.
    # Contagem aproximada: len(texto)//4 (4 chars ~= 1 token). Quando o acúmulo
    # recente->antiga ultrapassa o orçamento, as mensagens mais antigas são
    # resumidas via `compress_artifact` (ADR-C2) em vez de serem silenciosamente
    # cortadas — assim o Conductor preserva decisões da 1ª mensagem.
    conductor_history_token_budget: int = Field(default=3000, gt=0)

    # Sandbox de validação (Item E): docker | aws | modal
    sandbox_backend: str = "docker"
    aws_sandbox_function: str = "agentflow-sandbox"

    # --- Autenticação JWT (v1.2 — hardening do MVP single-tenant) ---
    # Em produção, defina JWT_SECRET via env (nunca deixe o default em produção).
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=60, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    bcrypt_rounds: int = Field(default=12, ge=4, le=15)

    # Circuit breaker (degradação graciosa)
    circuit_breaker_threshold: int = Field(default=3, ge=1)
    circuit_breaker_reset_s: float = Field(default=60.0, gt=0)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    # --- Demo mode (v1.2) ---
    # Quando True (ou ausência de GEMINI_API_KEY), o endpoint /cards/{id}/run
    # retorna um payload mock em vez de chamar os agentes LLM reais.
    # Evita custo e erros em demonstrações locais sem chave de API.
    demo_mode: bool = Field(default=False)

    # --- Definições declarativas de agentes (Item A do analise_omnigent.md) ---
    # Diretório onde os YAML de agentes customizados são persistidos.
    # Default: <raiz do repo>/.claude/skills (conforme CLAUDE.md).
    agents_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / ".claude" / "skills"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
