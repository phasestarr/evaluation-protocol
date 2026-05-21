import enum
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", passive_deletes=True)
    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user", passive_deletes=True)
    organization_import_user: Mapped["OrganizationImportUser | None"] = relationship(
        back_populates="user",
        passive_deletes=True,
    )
    peer_team_members: Mapped[list["PeerReviewTeamMember"]] = relationship(
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
        back_populates="children",
        remote_side=[id],
    )
    children: Mapped[list["OrganizationNode"]] = relationship(back_populates="parent", passive_deletes=True)
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

    user: Mapped[User] = relationship(back_populates="organization_import_user")


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

    team: Mapped[PeerReviewTeam] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="peer_team_members")


class EvaluationQuestion(Base):
    __tablename__ = "evaluation_questions"
    __table_args__ = (
        CheckConstraint(
            "((evaluation_type = 'manager_detail' AND organization_node_id IS NOT NULL) "
            "OR (evaluation_type != 'manager_detail' AND organization_node_id IS NULL))",
            name="ck_evaluation_questions_manager_detail_team_scope",
        ),
        Index("ix_evaluation_questions_type_org_node", "evaluation_type", "organization_node_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    organization_node_id: Mapped[int | None] = mapped_column(ForeignKey("organization_nodes.id", ondelete="CASCADE"), index=True)
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

    organization_node: Mapped[OrganizationNode | None] = relationship()


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


class EvaluationCycle(Base):
    __tablename__ = "evaluation_cycles"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'closed')", name="ck_evaluation_cycles_status"),
        Index(
            "uq_evaluation_cycles_one_running",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participants: Mapped[list["EvaluationParticipant"]] = relationship(back_populates="cycle", passive_deletes=True)
    org_nodes: Mapped[list["EvaluationOrgNodeSnapshot"]] = relationship(back_populates="cycle", passive_deletes=True)
    memberships: Mapped[list["EvaluationMembershipSnapshot"]] = relationship(back_populates="cycle", passive_deletes=True)
    peer_team_snapshots: Mapped[list["EvaluationPeerTeamSnapshot"]] = relationship(back_populates="cycle", passive_deletes=True)
    questions: Mapped[list["EvaluationCycleQuestion"]] = relationship(back_populates="cycle", passive_deletes=True)
    guides: Mapped[list["EvaluationCycleGuide"]] = relationship(back_populates="cycle", passive_deletes=True)
    assignments: Mapped[list["ReviewAssignment"]] = relationship(back_populates="cycle", passive_deletes=True)


class EvaluationSystemState(Base):
    __tablename__ = "evaluation_system_state"
    __table_args__ = (
        CheckConstraint("status IN ('idle', 'running')", name="ck_evaluation_system_state_status"),
        CheckConstraint(
            "((status = 'idle' AND current_cycle_id IS NULL) OR (status = 'running' AND current_cycle_id IS NOT NULL))",
            name="ck_evaluation_system_state_status_cycle",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    current_cycle: Mapped[EvaluationCycle | None] = relationship()


class EvaluationParticipant(Base):
    __tablename__ = "evaluation_participants"
    __table_args__ = (
        UniqueConstraint("cycle_id", "source_user_id", name="uq_evaluation_participants_cycle_source_user"),
        UniqueConstraint("cycle_id", "id", name="uq_evaluation_participants_cycle_id_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    source_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    email_snapshot: Mapped[str | None] = mapped_column(String(320))
    display_name_snapshot: Mapped[str | None] = mapped_column(String(200))
    job_title_snapshot: Mapped[str | None] = mapped_column(String(120))
    system_role_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="participants")
    source_user: Mapped[User | None] = relationship()
    memberships: Mapped[list["EvaluationMembershipSnapshot"]] = relationship(back_populates="participant", passive_deletes=True)


class EvaluationOrgNodeSnapshot(Base):
    __tablename__ = "evaluation_org_node_snapshots"
    __table_args__ = (
        UniqueConstraint("cycle_id", "source_node_id", name="uq_evaluation_org_node_snapshots_cycle_source_node"),
        UniqueConstraint("cycle_id", "id", name="uq_evaluation_org_node_snapshots_cycle_id_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    source_node_id: Mapped[int | None] = mapped_column(ForeignKey("organization_nodes.id", ondelete="SET NULL"), index=True)
    name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    node_type_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_org_node_snapshots.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="org_nodes")
    source_node: Mapped[OrganizationNode | None] = relationship()
    parent: Mapped["EvaluationOrgNodeSnapshot | None"] = relationship(remote_side=[id])
    memberships: Mapped[list["EvaluationMembershipSnapshot"]] = relationship(back_populates="org_node", passive_deletes=True)


class EvaluationMembershipSnapshot(Base):
    __tablename__ = "evaluation_membership_snapshots"
    __table_args__ = (
        UniqueConstraint("cycle_id", "source_membership_id", name="uq_evaluation_membership_snapshots_cycle_source_membership"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    source_membership_id: Mapped[int | None] = mapped_column(ForeignKey("organization_memberships.id", ondelete="SET NULL"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("evaluation_participants.id", ondelete="CASCADE"), index=True)
    org_node_snapshot_id: Mapped[int] = mapped_column(ForeignKey("evaluation_org_node_snapshots.id", ondelete="CASCADE"), index=True)
    membership_role_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="memberships")
    participant: Mapped[EvaluationParticipant] = relationship(back_populates="memberships")
    org_node: Mapped[EvaluationOrgNodeSnapshot] = relationship(back_populates="memberships")


class EvaluationPeerTeamSnapshot(Base):
    __tablename__ = "evaluation_peer_team_snapshots"
    __table_args__ = (
        UniqueConstraint("cycle_id", "id", name="uq_evaluation_peer_team_snapshots_cycle_id_id"),
        UniqueConstraint("cycle_id", "source_peer_team_id", name="uq_evaluation_peer_team_snapshots_cycle_source_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    source_peer_team_id: Mapped[int | None] = mapped_column(ForeignKey("peer_review_teams.id", ondelete="SET NULL"), index=True)
    name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="peer_team_snapshots")
    source_peer_team: Mapped[PeerReviewTeam | None] = relationship()
    members: Mapped[list["EvaluationPeerTeamMemberSnapshot"]] = relationship(back_populates="peer_team", passive_deletes=True)


class EvaluationPeerTeamMemberSnapshot(Base):
    __tablename__ = "evaluation_peer_team_member_snapshots"
    __table_args__ = (
        UniqueConstraint("peer_team_snapshot_id", "participant_id", name="uq_evaluation_peer_team_member_snapshots_team_participant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    peer_team_snapshot_id: Mapped[int] = mapped_column(ForeignKey("evaluation_peer_team_snapshots.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("evaluation_participants.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    peer_team: Mapped[EvaluationPeerTeamSnapshot] = relationship(back_populates="members")
    participant: Mapped[EvaluationParticipant] = relationship()


class EvaluationCycleQuestion(Base):
    __tablename__ = "evaluation_cycle_questions"
    __table_args__ = (UniqueConstraint("cycle_id", "id", name="uq_evaluation_cycle_questions_cycle_id_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    source_question_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_questions.id", ondelete="SET NULL"), index=True)
    context_team_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_org_node_snapshots.id", ondelete="CASCADE"), index=True)
    evaluation_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    description_snapshot: Mapped[str | None] = mapped_column(Text)
    weight_snapshot: Mapped[int | None] = mapped_column(Integer)
    sort_order_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="questions")
    source_question: Mapped[EvaluationQuestion | None] = relationship()
    context_team: Mapped[EvaluationOrgNodeSnapshot | None] = relationship()
    self_answers: Mapped[list["SelfReviewAnswer"]] = relationship(back_populates="cycle_question", passive_deletes=True)
    scores: Mapped[list["ReviewScore"]] = relationship(back_populates="cycle_question", passive_deletes=True)


class EvaluationCycleGuide(Base):
    __tablename__ = "evaluation_cycle_guides"
    __table_args__ = (UniqueConstraint("cycle_id", "evaluation_type", name="uq_evaluation_cycle_guides_cycle_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    evaluation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content_markdown_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="guides")


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"
    __table_args__ = (UniqueConstraint("cycle_id", "id", name="uq_review_assignments_cycle_id_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    review_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    reviewer_participant_id: Mapped[int] = mapped_column(ForeignKey("evaluation_participants.id", ondelete="CASCADE"), index=True)
    target_participant_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_participants.id", ondelete="CASCADE"), index=True)
    context_peer_team_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_peer_team_snapshots.id", ondelete="CASCADE"), index=True)
    context_team_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_org_node_snapshots.id", ondelete="CASCADE"), index=True)
    context_head_snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_org_node_snapshots.id", ondelete="CASCADE"), index=True)
    display_role_label_snapshot: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cycle: Mapped[EvaluationCycle] = relationship(back_populates="assignments")
    reviewer: Mapped[EvaluationParticipant] = relationship(foreign_keys=[reviewer_participant_id])
    target: Mapped[EvaluationParticipant | None] = relationship(foreign_keys=[target_participant_id])
    context_peer_team: Mapped[EvaluationPeerTeamSnapshot | None] = relationship(foreign_keys=[context_peer_team_snapshot_id])
    context_team: Mapped[EvaluationOrgNodeSnapshot | None] = relationship(foreign_keys=[context_team_snapshot_id])
    context_head: Mapped[EvaluationOrgNodeSnapshot | None] = relationship(foreign_keys=[context_head_snapshot_id])
    self_answers: Mapped[list["SelfReviewAnswer"]] = relationship(back_populates="assignment", passive_deletes=True)
    scores: Mapped[list["ReviewScore"]] = relationship(back_populates="assignment", passive_deletes=True)


class SelfReviewAnswer(Base):
    __tablename__ = "self_review_answers"
    __table_args__ = (UniqueConstraint("assignment_id", "cycle_question_id", name="uq_self_review_answers_assignment_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("review_assignments.id", ondelete="CASCADE"), index=True)
    cycle_question_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycle_questions.id", ondelete="CASCADE"), index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    assignment: Mapped[ReviewAssignment] = relationship(back_populates="self_answers")
    cycle_question: Mapped[EvaluationCycleQuestion] = relationship(back_populates="self_answers")


class ReviewScore(Base):
    __tablename__ = "review_scores"
    __table_args__ = (UniqueConstraint("assignment_id", "cycle_question_id", name="uq_review_scores_assignment_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("review_assignments.id", ondelete="CASCADE"), index=True)
    cycle_question_id: Mapped[int] = mapped_column(ForeignKey("evaluation_cycle_questions.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    assignment: Mapped[ReviewAssignment] = relationship(back_populates="scores")
    cycle_question: Mapped[EvaluationCycleQuestion] = relationship(back_populates="scores")
