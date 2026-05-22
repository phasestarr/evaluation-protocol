from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres.base import Base


class OrganizationNodeType(str, enum.Enum):
    company = "company"
    head = "head"
    team = "team"


class OrganizationMembershipRole(str, enum.Enum):
    member = "member"
    leader = "leader"


class OrganizationNode(Base):
    __tablename__ = "organization_nodes"
    __table_args__ = (
        CheckConstraint(
            "(node_type != 'company') OR (parent_id IS NULL)",
            name="ck_organization_nodes_company_shape",
        ),
        CheckConstraint(
            "(node_type = 'company') OR (parent_id IS NOT NULL)",
            name="ck_organization_nodes_non_company_has_parent",
        ),
        Index(
            "uq_organization_nodes_single_root_company",
            "node_type",
            unique=True,
            postgresql_where=text("node_type = 'company' AND parent_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    node_type: Mapped[OrganizationNodeType] = mapped_column(
        Enum(OrganizationNodeType, name="organization_node_type"),
        nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("organization_nodes.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    parent: Mapped["OrganizationNode | None"] = relationship(
        "OrganizationNode",
        back_populates="children",
        remote_side=[id],
    )
    children: Mapped[list["OrganizationNode"]] = relationship(
        "OrganizationNode",
        back_populates="parent",
        passive_deletes=True,
    )
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        "OrganizationMembership",
        back_populates="organization_node",
    )


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

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    organization_node: Mapped["OrganizationNode"] = relationship("OrganizationNode", back_populates="memberships")


class OrganizationImportUser(Base):
    __tablename__ = "organization_import_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    attributes: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(120))
    office_phone: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    mobile: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="organization_import_user")


class PeerReviewTeam(Base):
    __tablename__ = "peer_review_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    members: Mapped[list["PeerReviewTeamMember"]] = relationship(
        "PeerReviewTeamMember",
        back_populates="team",
        passive_deletes=True,
    )


class PeerReviewTeamMember(Base):
    __tablename__ = "peer_review_team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_peer_review_team_members_team_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("peer_review_teams.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped["PeerReviewTeam"] = relationship("PeerReviewTeam", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="peer_team_members")
