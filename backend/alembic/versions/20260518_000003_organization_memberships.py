"""organization memberships

Revision ID: 20260518_000003
Revises: 20260518_000002
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260518_000003"
down_revision: Union[str, None] = "20260518_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE organization_membership_role AS ENUM ('member', 'leader');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    membership_role = postgresql.ENUM("member", "leader", name="organization_membership_role", create_type=False)

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_node_id", sa.Integer(), nullable=False),
        sa.Column("membership_role", membership_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_node_id"], ["organization_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organization_memberships_organization_node_id"), "organization_memberships", ["organization_node_id"], unique=False)
    op.create_index(op.f("ix_organization_memberships_user_id"), "organization_memberships", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_organization_memberships_user_id"), table_name="organization_memberships")
    op.drop_index(op.f("ix_organization_memberships_organization_node_id"), table_name="organization_memberships")
    op.drop_table("organization_memberships")
    sa.Enum(name="organization_membership_role").drop(op.get_bind(), checkfirst=True)
