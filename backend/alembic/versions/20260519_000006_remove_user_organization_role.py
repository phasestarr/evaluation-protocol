"""remove user organization role

Revision ID: 20260519_000006
Revises: 20260518_000005
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260519_000006"
down_revision: Union[str, None] = "20260518_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS organization_role")
    op.execute("DROP TYPE IF EXISTS organization_role")


def downgrade() -> None:
    pass
