"""cycle snapshots

Revision ID: 20260519_000009
Revises: 20260519_000008
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_000009"
down_revision: Union[str, None] = "20260519_000008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS peer_review_scores")
    op.execute("DROP TABLE IF EXISTS self_review_answers")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS organization_node_id")

    op.drop_constraint("organization_nodes_parent_id_fkey", "organization_nodes", type_="foreignkey")
    op.create_foreign_key(
        "organization_nodes_parent_id_fkey",
        "organization_nodes",
        "organization_nodes",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "evaluation_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_cycles_status"), "evaluation_cycles", ["status"], unique=False)

    op.create_table(
        "evaluation_system_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_cycle_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["current_cycle_id"], ["evaluation_cycles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "evaluation_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_user_id", sa.Integer(), nullable=True),
        sa.Column("email_snapshot", sa.String(length=320), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("job_title_snapshot", sa.String(length=120), nullable=True),
        sa.Column("system_role_snapshot", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "source_user_id", name="uq_evaluation_participants_cycle_source_user"),
    )
    op.create_index(op.f("ix_evaluation_participants_cycle_id"), "evaluation_participants", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_participants_source_user_id"), "evaluation_participants", ["source_user_id"], unique=False)

    op.create_table(
        "evaluation_org_node_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_node_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("node_type_snapshot", sa.String(length=30), nullable=False),
        sa.Column("parent_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["organization_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "source_node_id", name="uq_evaluation_org_node_snapshots_cycle_source_node"),
    )
    op.create_index(op.f("ix_evaluation_org_node_snapshots_cycle_id"), "evaluation_org_node_snapshots", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_org_node_snapshots_source_node_id"), "evaluation_org_node_snapshots", ["source_node_id"], unique=False)

    op.create_table(
        "evaluation_membership_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_membership_id", sa.Integer(), nullable=True),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("org_node_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("membership_role_snapshot", sa.String(length=30), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_node_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_membership_id"], ["organization_memberships.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "source_membership_id", name="uq_evaluation_membership_snapshots_cycle_source_membership"),
    )
    op.create_index(op.f("ix_evaluation_membership_snapshots_cycle_id"), "evaluation_membership_snapshots", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_org_node_snapshot_id"), "evaluation_membership_snapshots", ["org_node_snapshot_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_participant_id"), "evaluation_membership_snapshots", ["participant_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_source_membership_id"), "evaluation_membership_snapshots", ["source_membership_id"], unique=False)

    op.create_table(
        "evaluation_cycle_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_question_id", sa.Integer(), nullable=True),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("title_snapshot", sa.String(length=160), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("weight_snapshot", sa.Integer(), nullable=True),
        sa.Column("sort_order_snapshot", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_question_id"], ["evaluation_questions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_cycle_questions_cycle_id"), "evaluation_cycle_questions", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_cycle_questions_evaluation_type"), "evaluation_cycle_questions", ["evaluation_type"], unique=False)
    op.create_index(op.f("ix_evaluation_cycle_questions_source_question_id"), "evaluation_cycle_questions", ["source_question_id"], unique=False)

    op.create_table(
        "evaluation_cycle_guides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("content_markdown_snapshot", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "evaluation_type", name="uq_evaluation_cycle_guides_cycle_type"),
    )
    op.create_index(op.f("ix_evaluation_cycle_guides_cycle_id"), "evaluation_cycle_guides", ["cycle_id"], unique=False)

    op.create_table(
        "review_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("review_type", sa.String(length=30), nullable=False),
        sa.Column("reviewer_participant_id", sa.Integer(), nullable=False),
        sa.Column("target_participant_id", sa.Integer(), nullable=True),
        sa.Column("context_team_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("context_head_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("display_role_label_snapshot", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["context_head_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_team_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_assignments_context_head_snapshot_id"), "review_assignments", ["context_head_snapshot_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_context_team_snapshot_id"), "review_assignments", ["context_team_snapshot_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_cycle_id"), "review_assignments", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_review_type"), "review_assignments", ["review_type"], unique=False)
    op.create_index(op.f("ix_review_assignments_reviewer_participant_id"), "review_assignments", ["reviewer_participant_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_target_participant_id"), "review_assignments", ["target_participant_id"], unique=False)

    op.create_table(
        "self_review_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("cycle_question_id", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["review_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_question_id"], ["evaluation_cycle_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "cycle_question_id", name="uq_self_review_answers_assignment_question"),
    )
    op.create_index(op.f("ix_self_review_answers_assignment_id"), "self_review_answers", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_self_review_answers_cycle_question_id"), "self_review_answers", ["cycle_question_id"], unique=False)

    op.create_table(
        "review_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("cycle_question_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["review_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_question_id"], ["evaluation_cycle_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "cycle_question_id", name="uq_review_scores_assignment_question"),
    )
    op.create_index(op.f("ix_review_scores_assignment_id"), "review_scores", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_review_scores_cycle_question_id"), "review_scores", ["cycle_question_id"], unique=False)

    op.execute("INSERT INTO evaluation_system_state (id, status) VALUES (1, 'idle') ON CONFLICT (id) DO NOTHING")


def downgrade() -> None:
    op.drop_table("review_scores")
    op.drop_table("self_review_answers")
    op.drop_table("review_assignments")
    op.drop_table("evaluation_cycle_guides")
    op.drop_table("evaluation_cycle_questions")
    op.drop_table("evaluation_membership_snapshots")
    op.drop_table("evaluation_org_node_snapshots")
    op.drop_table("evaluation_participants")
    op.drop_table("evaluation_system_state")
    op.drop_index(op.f("ix_evaluation_cycles_status"), table_name="evaluation_cycles")
    op.drop_table("evaluation_cycles")
    op.add_column("users", sa.Column("organization_node_id", sa.Integer(), nullable=True))
    op.create_foreign_key("users_organization_node_id_fkey", "users", "organization_nodes", ["organization_node_id"], ["id"])
