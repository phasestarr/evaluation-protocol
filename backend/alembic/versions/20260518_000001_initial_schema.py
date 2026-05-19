"""initial schema

Revision ID: 20260518_000001
Revises:
Create Date: 2026-05-18
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

    system_role = postgresql.ENUM("user", "admin", name="system_role", create_type=False)
    oauth_status = postgresql.ENUM("pending", "completed", "denied", "failed", "expired", name="oauth_status", create_type=False)
    organization_node_type = postgresql.ENUM("company", "head", "team", name="organization_node_type", create_type=False)

    op.create_table(
        "organization_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("node_type", organization_node_type, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["organization_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("system_role", system_role, nullable=False),
        sa.Column("is_whitelisted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_whitelist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_whitelist_email"), "user_whitelist", ["email"], unique=True)

    op.create_table(
        "oauth_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=160), nullable=False),
        sa.Column("nonce", sa.String(length=160), nullable=False),
        sa.Column("status", oauth_status, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("redirect_after", sa.String(length=500), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_transactions_email"), "oauth_transactions", ["email"], unique=False)
    op.create_index(op.f("ix_oauth_transactions_state"), "oauth_transactions", ["state"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_user_sessions_session_key_hash"), "user_sessions", ["session_key_hash"], unique=True)
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_session_key_hash"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_expires_at"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_oauth_transactions_state"), table_name="oauth_transactions")
    op.drop_index(op.f("ix_oauth_transactions_email"), table_name="oauth_transactions")
    op.drop_table("oauth_transactions")
    op.drop_index(op.f("ix_user_whitelist_email"), table_name="user_whitelist")
    op.drop_table("user_whitelist")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("organization_nodes")

    sa.Enum(name="organization_node_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="oauth_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="system_role").drop(op.get_bind(), checkfirst=True)
