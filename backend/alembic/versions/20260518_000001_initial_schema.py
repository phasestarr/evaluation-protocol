"""initial schema

Revision ID: 20260518_000001
Revises:
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260518_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE system_role AS ENUM ('user', 'admin');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE oauth_status AS ENUM ('pending', 'completed', 'denied', 'failed', 'expired');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE organization_node_type AS ENUM ('company', 'head', 'team');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
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

    system_role = postgresql.ENUM("user", "admin", name="system_role", create_type=False)
    oauth_status = postgresql.ENUM("pending", "completed", "denied", "failed", "expired", name="oauth_status", create_type=False)
    organization_node_type = postgresql.ENUM("company", "head", "team", name="organization_node_type", create_type=False)
    organization_membership_role = postgresql.ENUM("member", "leader", name="organization_membership_role", create_type=False)

    # User and auth/session tables.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("system_role", system_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_whitelist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_whitelist_email"), "user_whitelist", ["email"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_user_sessions_session_key_hash"), "user_sessions", ["session_key_hash"], unique=True)
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)

    op.create_table(
        "oauth_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=160), nullable=False),
        sa.Column("nonce", sa.String(length=160), nullable=False),
        sa.Column("status", oauth_status, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("redirect_after", sa.String(length=500), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_transactions_email"), "oauth_transactions", ["email"], unique=False)
    op.create_index(op.f("ix_oauth_transactions_state"), "oauth_transactions", ["state"], unique=True)

    # Live organization tables.
    op.create_table(
        "organization_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("node_type", organization_node_type, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("(node_type != 'company') OR (parent_id IS NULL)", name="ck_organization_nodes_company_shape"),
        sa.CheckConstraint("(node_type = 'company') OR (parent_id IS NOT NULL)", name="ck_organization_nodes_non_company_has_parent"),
        sa.ForeignKeyConstraint(["parent_id"], ["organization_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_organization_nodes_single_root_company",
        "organization_nodes",
        ["node_type"],
        unique=True,
        postgresql_where=sa.text("node_type = 'company' AND parent_id IS NULL"),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_node_id", sa.Integer(), nullable=False),
        sa.Column("membership_role", organization_membership_role, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["organization_node_id"], ["organization_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organization_memberships_organization_node_id"), "organization_memberships", ["organization_node_id"], unique=False)
    op.create_index(op.f("ix_organization_memberships_user_id"), "organization_memberships", ["user_id"], unique=False)

    op.create_table(
        "organization_import_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("attributes", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column("office_phone", sa.String(length=60), nullable=False),
        sa.Column("mobile", sa.String(length=60), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_organization_import_users_email"),
        sa.UniqueConstraint("user_id", name="uq_organization_import_users_user_id"),
    )
    op.create_index(op.f("ix_organization_import_users_email"), "organization_import_users", ["email"], unique=False)
    op.create_index(op.f("ix_organization_import_users_name"), "organization_import_users", ["name"], unique=False)
    op.create_index(op.f("ix_organization_import_users_user_id"), "organization_import_users", ["user_id"], unique=False)

    op.create_table(
        "peer_review_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_peer_review_teams_name"),
    )

    op.create_table(
        "peer_review_team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["peer_review_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_peer_review_team_members_team_user"),
    )
    op.create_index(op.f("ix_peer_review_team_members_team_id"), "peer_review_team_members", ["team_id"], unique=False)
    op.create_index(op.f("ix_peer_review_team_members_user_id"), "peer_review_team_members", ["user_id"], unique=False)

    # Evaluation template and cycle tables.
    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("organization_node_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint(
            "((evaluation_type = 'manager_detail' AND organization_node_id IS NOT NULL) "
            "OR (evaluation_type != 'manager_detail' AND organization_node_id IS NULL))",
            name="ck_evaluation_questions_manager_detail_team_scope",
        ),
        sa.ForeignKeyConstraint(["organization_node_id"], ["organization_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_questions_evaluation_type"), "evaluation_questions", ["evaluation_type"], unique=False)
    op.create_index(op.f("ix_evaluation_questions_organization_node_id"), "evaluation_questions", ["organization_node_id"], unique=False)
    op.create_index("ix_evaluation_questions_type_org_node", "evaluation_questions", ["evaluation_type", "organization_node_id"], unique=False)

    op.create_table(
        "evaluation_guides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_guides_evaluation_type"), "evaluation_guides", ["evaluation_type"], unique=True)

    op.create_table(
        "evaluation_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("status IN ('running', 'closed')", name="ck_evaluation_cycles_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_cycles_status"), "evaluation_cycles", ["status"], unique=False)
    op.create_index(
        "uq_evaluation_cycles_one_running",
        "evaluation_cycles",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )

    op.create_table(
        "evaluation_system_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_cycle_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("status IN ('idle', 'running')", name="ck_evaluation_system_state_status"),
        sa.CheckConstraint(
            "((status = 'idle' AND current_cycle_id IS NULL) OR (status = 'running' AND current_cycle_id IS NOT NULL))",
            name="ck_evaluation_system_state_status_cycle",
        ),
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
        sa.UniqueConstraint("cycle_id", "id", name="uq_evaluation_participants_cycle_id_id"),
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
        sa.UniqueConstraint("cycle_id", "id", name="uq_evaluation_org_node_snapshots_cycle_id_id"),
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
        sa.ForeignKeyConstraint(["source_membership_id"], ["organization_memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_node_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id", "participant_id"], ["evaluation_participants.cycle_id", "evaluation_participants.id"], ondelete="CASCADE", name="fk_evaluation_membership_snapshots_cycle_participant"),
        sa.ForeignKeyConstraint(["cycle_id", "org_node_snapshot_id"], ["evaluation_org_node_snapshots.cycle_id", "evaluation_org_node_snapshots.id"], ondelete="CASCADE", name="fk_evaluation_membership_snapshots_cycle_org_node"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "source_membership_id", name="uq_evaluation_membership_snapshots_cycle_source_membership"),
    )
    op.create_index(op.f("ix_evaluation_membership_snapshots_cycle_id"), "evaluation_membership_snapshots", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_org_node_snapshot_id"), "evaluation_membership_snapshots", ["org_node_snapshot_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_participant_id"), "evaluation_membership_snapshots", ["participant_id"], unique=False)
    op.create_index(op.f("ix_evaluation_membership_snapshots_source_membership_id"), "evaluation_membership_snapshots", ["source_membership_id"], unique=False)

    op.create_table(
        "evaluation_peer_team_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_peer_team_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_peer_team_id"], ["peer_review_teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "id", name="uq_evaluation_peer_team_snapshots_cycle_id_id"),
        sa.UniqueConstraint("cycle_id", "source_peer_team_id", name="uq_evaluation_peer_team_snapshots_cycle_source_team"),
    )
    op.create_index(op.f("ix_evaluation_peer_team_snapshots_cycle_id"), "evaluation_peer_team_snapshots", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_peer_team_snapshots_source_peer_team_id"), "evaluation_peer_team_snapshots", ["source_peer_team_id"], unique=False)

    op.create_table(
        "evaluation_peer_team_member_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("peer_team_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("participant_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["peer_team_snapshot_id"], ["evaluation_peer_team_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id", "peer_team_snapshot_id"], ["evaluation_peer_team_snapshots.cycle_id", "evaluation_peer_team_snapshots.id"], ondelete="CASCADE", name="fk_evaluation_peer_team_member_snapshots_cycle_team"),
        sa.ForeignKeyConstraint(["cycle_id", "participant_id"], ["evaluation_participants.cycle_id", "evaluation_participants.id"], ondelete="CASCADE", name="fk_evaluation_peer_team_member_snapshots_cycle_participant"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("peer_team_snapshot_id", "participant_id", name="uq_evaluation_peer_team_member_snapshots_team_participant"),
    )
    op.create_index(op.f("ix_evaluation_peer_team_member_snapshots_cycle_id"), "evaluation_peer_team_member_snapshots", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_evaluation_peer_team_member_snapshots_participant_id"), "evaluation_peer_team_member_snapshots", ["participant_id"], unique=False)
    op.create_index(op.f("ix_evaluation_peer_team_member_snapshots_peer_team_snapshot_id"), "evaluation_peer_team_member_snapshots", ["peer_team_snapshot_id"], unique=False)

    op.create_table(
        "evaluation_cycle_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("source_question_id", sa.Integer(), nullable=True),
        sa.Column("context_team_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("title_snapshot", sa.String(length=160), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("weight_snapshot", sa.Integer(), nullable=True),
        sa.Column("sort_order_snapshot", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_team_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_question_id"], ["evaluation_questions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cycle_id", "context_team_snapshot_id"], ["evaluation_org_node_snapshots.cycle_id", "evaluation_org_node_snapshots.id"], ondelete="CASCADE", name="fk_evaluation_cycle_questions_cycle_team"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "id", name="uq_evaluation_cycle_questions_cycle_id_id"),
    )
    op.create_index(op.f("ix_evaluation_cycle_questions_context_team_snapshot_id"), "evaluation_cycle_questions", ["context_team_snapshot_id"], unique=False)
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
        sa.Column("context_peer_team_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("context_team_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("context_head_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("display_role_label_snapshot", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_participant_id"], ["evaluation_participants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_peer_team_snapshot_id"], ["evaluation_peer_team_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_team_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["context_head_snapshot_id"], ["evaluation_org_node_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id", "reviewer_participant_id"], ["evaluation_participants.cycle_id", "evaluation_participants.id"], ondelete="CASCADE", name="fk_review_assignments_cycle_reviewer"),
        sa.ForeignKeyConstraint(["cycle_id", "target_participant_id"], ["evaluation_participants.cycle_id", "evaluation_participants.id"], ondelete="CASCADE", name="fk_review_assignments_cycle_target"),
        sa.ForeignKeyConstraint(["cycle_id", "context_peer_team_snapshot_id"], ["evaluation_peer_team_snapshots.cycle_id", "evaluation_peer_team_snapshots.id"], ondelete="CASCADE", name="fk_review_assignments_cycle_peer_team"),
        sa.ForeignKeyConstraint(["cycle_id", "context_team_snapshot_id"], ["evaluation_org_node_snapshots.cycle_id", "evaluation_org_node_snapshots.id"], ondelete="CASCADE", name="fk_review_assignments_cycle_team"),
        sa.ForeignKeyConstraint(["cycle_id", "context_head_snapshot_id"], ["evaluation_org_node_snapshots.cycle_id", "evaluation_org_node_snapshots.id"], ondelete="CASCADE", name="fk_review_assignments_cycle_head"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "id", name="uq_review_assignments_cycle_id_id"),
    )
    op.create_index(op.f("ix_review_assignments_context_head_snapshot_id"), "review_assignments", ["context_head_snapshot_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_context_peer_team_snapshot_id"), "review_assignments", ["context_peer_team_snapshot_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_context_team_snapshot_id"), "review_assignments", ["context_team_snapshot_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_cycle_id"), "review_assignments", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_review_type"), "review_assignments", ["review_type"], unique=False)
    op.create_index(op.f("ix_review_assignments_reviewer_participant_id"), "review_assignments", ["reviewer_participant_id"], unique=False)
    op.create_index(op.f("ix_review_assignments_target_participant_id"), "review_assignments", ["target_participant_id"], unique=False)

    op.create_table(
        "self_review_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("cycle_question_id", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["review_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_question_id"], ["evaluation_cycle_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id", "assignment_id"], ["review_assignments.cycle_id", "review_assignments.id"], ondelete="CASCADE", name="fk_self_review_answers_cycle_assignment"),
        sa.ForeignKeyConstraint(["cycle_id", "cycle_question_id"], ["evaluation_cycle_questions.cycle_id", "evaluation_cycle_questions.id"], ondelete="CASCADE", name="fk_self_review_answers_cycle_question"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "cycle_question_id", name="uq_self_review_answers_assignment_question"),
    )
    op.create_index(op.f("ix_self_review_answers_assignment_id"), "self_review_answers", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_self_review_answers_cycle_id"), "self_review_answers", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_self_review_answers_cycle_question_id"), "self_review_answers", ["cycle_question_id"], unique=False)

    op.create_table(
        "review_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("cycle_question_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["evaluation_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["review_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_question_id"], ["evaluation_cycle_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id", "assignment_id"], ["review_assignments.cycle_id", "review_assignments.id"], ondelete="CASCADE", name="fk_review_scores_cycle_assignment"),
        sa.ForeignKeyConstraint(["cycle_id", "cycle_question_id"], ["evaluation_cycle_questions.cycle_id", "evaluation_cycle_questions.id"], ondelete="CASCADE", name="fk_review_scores_cycle_question"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "cycle_question_id", name="uq_review_scores_assignment_question"),
    )
    op.create_index(op.f("ix_review_scores_assignment_id"), "review_scores", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_review_scores_cycle_id"), "review_scores", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_review_scores_cycle_question_id"), "review_scores", ["cycle_question_id"], unique=False)


def downgrade() -> None:
    op.drop_table("review_scores")
    op.drop_table("self_review_answers")
    op.drop_table("review_assignments")
    op.drop_table("evaluation_cycle_guides")
    op.drop_table("evaluation_cycle_questions")
    op.drop_table("evaluation_peer_team_member_snapshots")
    op.drop_table("evaluation_peer_team_snapshots")
    op.drop_table("evaluation_membership_snapshots")
    op.drop_table("evaluation_org_node_snapshots")
    op.drop_table("evaluation_participants")
    op.drop_table("evaluation_system_state")
    op.drop_index("uq_evaluation_cycles_one_running", table_name="evaluation_cycles")
    op.drop_table("evaluation_cycles")
    op.drop_index(op.f("ix_evaluation_guides_evaluation_type"), table_name="evaluation_guides")
    op.drop_table("evaluation_guides")
    op.drop_index(op.f("ix_evaluation_questions_evaluation_type"), table_name="evaluation_questions")
    op.drop_table("evaluation_questions")

    op.drop_table("peer_review_team_members")
    op.drop_table("peer_review_teams")
    op.drop_table("organization_import_users")
    op.drop_table("organization_memberships")
    op.drop_index("uq_organization_nodes_single_root_company", table_name="organization_nodes")
    op.drop_table("organization_nodes")

    op.drop_table("oauth_transactions")
    op.drop_table("user_sessions")
    op.drop_table("user_whitelist")
    op.drop_table("users")

    sa.Enum(name="organization_membership_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="organization_node_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="oauth_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="system_role").drop(op.get_bind(), checkfirst=True)
