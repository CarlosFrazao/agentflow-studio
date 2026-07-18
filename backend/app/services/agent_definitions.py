"""Serviço de definições declarativas de agentes (Item A do analise_omnigent.md).

Persiste cada agente em dois lugares, mantendo-os em sincronia:
1. SQLite (`agents`) — fonte de verdade para a API/UI.
2. Arquivo YAML em `settings.agents_dir` (`.claude/skills/`) — portável e
   editável por humanos, conforme exigido pelo CLAUDE.md.

Toda escrita em disco é tolerante a falha: se o diretório não for gravável,
o registro no banco ainda é feito e o erro é logado (nunca silenciado).
"""

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.agent import Agent as AgentModel
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate

logger = get_logger("agent_definitions")

settings = get_settings()
AGENTS_DIR = settings.agents_dir


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.lower())


def _yaml_path(slug: str) -> Path:
    return AGENTS_DIR / f"{slug}.yaml"


def _write_yaml(agent: AgentModel) -> None:
    """Espelha o agente em YAML. Falhas de disco são logadas, não fatal."""
    try:
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": agent.name,
            "model": agent.model,
            "system_prompt": agent.system_prompt,
            "allowed_tools": agent.allowed_tools,
            "max_tokens_budget": agent.max_tokens_budget,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        }
        _yaml_path(_slug(agent.name)).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - depende do FS
        logger.error("agent_yaml_write_failed", name=agent.name, error=str(exc))


async def create_agent(body: AgentCreate, session: AsyncSession) -> AgentResponse:
    existing = (
        await session.scalars(select(AgentModel).where(AgentModel.name == body.name))
    ).first()
    if existing is not None:
        from app.core.exceptions import ConflictError

        raise ConflictError(f"Agent already exists: {body.name}")
    agent = AgentModel(
        name=body.name,
        model=body.model,
        system_prompt=body.system_prompt,
        allowed_tools=body.allowed_tools,
        max_tokens_budget=body.max_tokens_budget,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    _write_yaml(agent)
    return AgentResponse.model_validate(agent)


async def list_agents(session: AsyncSession) -> list[AgentResponse]:
    rows = (await session.scalars(select(AgentModel))).all()
    return [AgentResponse.model_validate(r) for r in rows]


async def get_agent_by_name(name: str, session: AsyncSession) -> AgentResponse | None:
    agent = (
        await session.scalars(select(AgentModel).where(AgentModel.name == name))
    ).first()
    return AgentResponse.model_validate(agent) if agent else None


async def update_agent_by_name(
    name: str, body: AgentUpdate, session: AsyncSession
) -> AgentResponse | None:
    agent = (
        await session.scalars(select(AgentModel).where(AgentModel.name == name))
    ).first()
    if agent is None:
        return None
    if body.model is not None:
        agent.model = body.model
    if body.system_prompt is not None:
        agent.system_prompt = body.system_prompt
    if body.allowed_tools is not None:
        agent.allowed_tools = body.allowed_tools
    if body.max_tokens_budget is not None:
        agent.max_tokens_budget = body.max_tokens_budget
    await session.commit()
    await session.refresh(agent)
    _write_yaml(agent)
    return AgentResponse.model_validate(agent)


async def delete_agent_by_name(name: str, session: AsyncSession) -> None:
    agent = (
        await session.scalars(select(AgentModel).where(AgentModel.name == name))
    ).first()
    if agent is None:
        return
    await session.delete(agent)
    await session.commit()
    yaml_file = _yaml_path(_slug(name))
    if yaml_file.exists():
        yaml_file.unlink()
