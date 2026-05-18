"""add user session cascade

Revision ID: 20260518_000002
Revises: 20260518_000001
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260518_000002"
down_revision: Union[str, None] = "20260518_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("user_sessions_user_id_fkey", "user_sessions", type_="foreignkey")
    op.create_foreign_key(
        "user_sessions_user_id_fkey",
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("user_sessions_user_id_fkey", "user_sessions", type_="foreignkey")
    op.create_foreign_key(
        "user_sessions_user_id_fkey",
        "user_sessions",
        "users",
        ["user_id"],
        ["id"],
    )
