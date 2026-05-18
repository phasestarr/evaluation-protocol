"""drop obsolete user is_whitelisted column

Revision ID: 20260518_000004
Revises: 20260518_000003
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260518_000004"
down_revision: Union[str, None] = "20260518_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "is_whitelisted")


def downgrade() -> None:
    op.add_column("users", sa.Column("is_whitelisted", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("users", "is_whitelisted", server_default=None)
