from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    sessions: Mapped[list["UserSession"]] = relationship("UserSession", back_populates="user", passive_deletes=True)
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        "OrganizationMembership",
        back_populates="user",
        passive_deletes=True,
    )
    organization_import_user: Mapped["OrganizationImportUser | None"] = relationship(
        "OrganizationImportUser",
        back_populates="user",
        passive_deletes=True,
    )
    peer_team_members: Mapped[list["PeerReviewTeamMember"]] = relationship(
        "PeerReviewTeamMember",
        back_populates="user",
        passive_deletes=True,
    )


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

    user: Mapped["User"] = relationship("User", back_populates="sessions")


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
