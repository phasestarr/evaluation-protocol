"""add import user snapshots

Revision ID: 20260522_000002
Revises: 20260518_000001
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260522_000002"
down_revision: Union[str, None] = "20260518_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_import_user_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_import_user_id", sa.Integer(), nullable=True),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("attributes_snapshot", sa.String(length=20), nullable=False),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("title_snapshot", sa.String(length=200), nullable=False),
        sa.Column("office_phone_snapshot", sa.String(length=60), nullable=False),
        sa.Column("mobile_snapshot", sa.String(length=60), nullable=False),
        sa.Column("email_snapshot", sa.String(length=320), nullable=False),
        sa.Column("note_snapshot", sa.Text(), nullable=False),
        sa.Column("system_role_snapshot", sa.String(length=30), nullable=False),
        sa.Column("sort_order_snapshot", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_import_user_id"], ["organization_import_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["cycle_id", "participant_id"],
            ["evaluation_participants.cycle_id", "evaluation_participants.id"],
            ondelete="CASCADE",
            name="fk_evaluation_import_user_snapshots_cycle_participant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "id", name="uq_evaluation_import_user_snapshots_cycle_id_id"),
        sa.UniqueConstraint("cycle_id", "participant_id", name="uq_evaluation_import_user_snapshots_cycle_participant"),
    )
    op.create_index(
        op.f("ix_evaluation_import_user_snapshots_cycle_id"),
        "evaluation_import_user_snapshots",
        ["cycle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_import_user_snapshots_participant_id"),
        "evaluation_import_user_snapshots",
        ["participant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evaluation_import_user_snapshots_source_import_user_id"),
        "evaluation_import_user_snapshots",
        ["source_import_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_import_user_snapshots_source_import_user_id"), table_name="evaluation_import_user_snapshots")
    op.drop_index(op.f("ix_evaluation_import_user_snapshots_participant_id"), table_name="evaluation_import_user_snapshots")
    op.drop_index(op.f("ix_evaluation_import_user_snapshots_cycle_id"), table_name="evaluation_import_user_snapshots")
    op.drop_table("evaluation_import_user_snapshots")
