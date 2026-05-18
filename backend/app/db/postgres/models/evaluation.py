import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres.base import Base


class SystemRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class OrganizationRole(str, enum.Enum):
    staff = "staff"
    manager = "manager"


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
    organization_role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name="organization_role"),
        default=OrganizationRole.staff,
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
