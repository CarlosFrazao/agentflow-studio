"""agent owner namespace (FEAT-003 / B5-1)

Revision ID: 0004_agent_owner
Revises: 0003_conversations_and_messages
Adiciona a coluna `user_id` (FK users.id, nullable) à tabela `agents` para
nomear o dono de cada agente declarativo (namespace por tenant). NULL mantém
o agente compartilhado por todos (shared-by-design), preservando o contrato
legado da API. A autorização em update/delete exige o dono OU agente shared.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_agent_owner"
down_revision: Union[str, None] = "0003_conversations_and_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_user_id", "agents", "users", ["user_id"], ["id"]
    )
    op.create_index("ix_agents_user_id", "agents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_user_id", table_name="agents")
    op.drop_constraint("fk_agents_user_id", "agents", type_="foreignkey")
    op.drop_column("agents", "user_id")
