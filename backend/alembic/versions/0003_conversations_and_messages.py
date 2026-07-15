"""conversations and messages (F-023 Conductor)

Revision ID: 0003_conversations_and_messages
Revises: 0002_preference_archive
Cria as tabelas `conversations` e `messages` para a Orquestração Conversacional.
Fiel aos modelos em app/models/conversation.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_conversations_and_messages"
down_revision: Union[str, None] = "0002_preference_archive"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "conductor", "tool", name="msg_role"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=True),
        sa.Column("tool_input", sa.JSON(), nullable=True),
        sa.Column("tool_output", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
