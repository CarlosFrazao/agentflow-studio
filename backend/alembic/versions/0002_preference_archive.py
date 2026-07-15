"""preference archive flag (Fase D1 — F-010)

Revision ID: 0002_preference_archive
Revises: 0001_initial
Adiciona a coluna `archived` a `user_preferences` para remoção recuperável
de preferências sem perder o histórico físico (Fase D1).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_preference_archive"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "archived")
