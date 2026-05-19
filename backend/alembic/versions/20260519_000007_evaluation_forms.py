"""evaluation forms

Revision ID: 20260519_000007
Revises: 20260519_000006
Create Date: 2026-05-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_000007"
down_revision: Union[str, None] = "20260519_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("evaluation_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_questions_evaluation_type"), "evaluation_questions", ["evaluation_type"], unique=False)

    op.create_table(
        "self_review_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["evaluation_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "question_id", name="uq_self_review_answers_user_question"),
    )
    op.create_index(op.f("ix_self_review_answers_question_id"), "self_review_answers", ["question_id"], unique=False)
    op.create_index(op.f("ix_self_review_answers_user_id"), "self_review_answers", ["user_id"], unique=False)

    op.create_table(
        "peer_review_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("team_node_id", sa.Integer(), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["evaluation_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_node_id"], ["organization_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reviewer_user_id",
            "team_node_id",
            "target_user_id",
            "question_id",
            name="uq_peer_review_scores_context_target_question",
        ),
    )
    op.create_index(op.f("ix_peer_review_scores_question_id"), "peer_review_scores", ["question_id"], unique=False)
    op.create_index(op.f("ix_peer_review_scores_reviewer_user_id"), "peer_review_scores", ["reviewer_user_id"], unique=False)
    op.create_index(op.f("ix_peer_review_scores_target_user_id"), "peer_review_scores", ["target_user_id"], unique=False)
    op.create_index(op.f("ix_peer_review_scores_team_node_id"), "peer_review_scores", ["team_node_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_peer_review_scores_team_node_id"), table_name="peer_review_scores")
    op.drop_index(op.f("ix_peer_review_scores_target_user_id"), table_name="peer_review_scores")
    op.drop_index(op.f("ix_peer_review_scores_reviewer_user_id"), table_name="peer_review_scores")
    op.drop_index(op.f("ix_peer_review_scores_question_id"), table_name="peer_review_scores")
    op.drop_table("peer_review_scores")
    op.drop_index(op.f("ix_self_review_answers_user_id"), table_name="self_review_answers")
    op.drop_index(op.f("ix_self_review_answers_question_id"), table_name="self_review_answers")
    op.drop_table("self_review_answers")
    op.drop_index(op.f("ix_evaluation_questions_evaluation_type"), table_name="evaluation_questions")
    op.drop_table("evaluation_questions")
