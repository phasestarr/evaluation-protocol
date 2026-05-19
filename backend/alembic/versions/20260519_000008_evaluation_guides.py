"""evaluation guides

Revision ID: 20260519_000008
Revises: 20260519_000007
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_000008"
down_revision: Union[str, None] = "20260519_000007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_guides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_guides_evaluation_type"), "evaluation_guides", ["evaluation_type"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_guides_evaluation_type"), table_name="evaluation_guides")
    op.drop_table("evaluation_guides")
