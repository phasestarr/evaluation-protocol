import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres.base import Base


class SystemRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class OAuthStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    denied = "denied"
    failed = "failed"
    expired = "expired"


class OrganizationNodeType(str, enum.Enum):
    company = "company"
    head = "head"
    team = "team"


class OrganizationMembershipRole(str, enum.Enum):
    member = "member"
    leader = "leader"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(120))
    system_role: Mapped[SystemRole] = mapped_column(
        Enum(SystemRole, name="system_role"),
        default=SystemRole.user,
        nullable=False,
    )
    organization_node_id: Mapped[int | None] = mapped_column(ForeignKey("organization_nodes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization_node: Mapped["OrganizationNode | None"] = relationship(back_populates="users")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", passive_deletes=True)
    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user", passive_deletes=True)


class UserWhitelist(Base):
    __tablename__ = "user_whitelist"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class OAuthTransaction(Base):
    __tablename__ = "oauth_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    nonce: Mapped[str] = mapped_column(String(160))
    status: Mapped[OAuthStatus] = mapped_column(
        Enum(OAuthStatus, name="oauth_status"),
        default=OAuthStatus.pending,
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    redirect_after: Mapped[str] = mapped_column(String(500), default="/", nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationNode(Base):
    __tablename__ = "organization_nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    node_type: Mapped[OrganizationNodeType] = mapped_column(
        Enum(OrganizationNodeType, name="organization_node_type"),
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("organization_nodes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    parent: Mapped["OrganizationNode | None"] = relationship(
        back_populates="children",
        remote_side=[id],
    )
    children: Mapped[list["OrganizationNode"]] = relationship(back_populates="parent")
    users: Mapped[list[User]] = relationship(back_populates="organization_node")
    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="organization_node")


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_node_id: Mapped[int] = mapped_column(ForeignKey("organization_nodes.id", ondelete="CASCADE"), index=True)
    membership_role: Mapped[OrganizationMembershipRole] = mapped_column(
        Enum(OrganizationMembershipRole, name="organization_membership_role"),
        default=OrganizationMembershipRole.member,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships")
    organization_node: Mapped[OrganizationNode] = relationship(back_populates="memberships")


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_type: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    self_answers: Mapped[list["SelfReviewAnswer"]] = relationship(back_populates="question", passive_deletes=True)
    peer_scores: Mapped[list["PeerReviewScore"]] = relationship(back_populates="question", passive_deletes=True)


class EvaluationGuide(Base):
    __tablename__ = "evaluation_guides"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_type: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SelfReviewAnswer(Base):
    __tablename__ = "self_review_answers"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_self_review_answers_user_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="CASCADE"), index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship()
    question: Mapped[EvaluationQuestion] = relationship(back_populates="self_answers")


class PeerReviewScore(Base):
    __tablename__ = "peer_review_scores"
    __table_args__ = (
        UniqueConstraint(
            "reviewer_user_id",
            "team_node_id",
            "target_user_id",
            "question_id",
            name="uq_peer_review_scores_context_target_question",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    team_node_id: Mapped[int] = mapped_column(ForeignKey("organization_nodes.id", ondelete="CASCADE"), index=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_user_id])
    team_node: Mapped[OrganizationNode] = relationship(foreign_keys=[team_node_id])
    target: Mapped[User] = relationship(foreign_keys=[target_user_id])
    question: Mapped[EvaluationQuestion] = relationship(back_populates="peer_scores")
