from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    ASSIGNMENT_PENDING,
    CYCLE_CLOSED,
    CYCLE_RUNNING,
    EVALUATION_TYPES,
    MANAGER_DETAIL,
    PEER,
    SELF,
    SYSTEM_IDLE,
    SYSTEM_RUNNING,
)
from app.db.postgres.models import (
    EvaluationCycle,
    EvaluationCycleGuide,
    EvaluationImportUserSnapshot,
    EvaluationCycleQuestion,
    EvaluationGuide,
    EvaluationMembershipSnapshot,
    EvaluationOrgNodeSnapshot,
    EvaluationParticipant,
    EvaluationPeerTeamMemberSnapshot,
    EvaluationPeerTeamSnapshot,
    EvaluationQuestion,
    EvaluationSystemState,
    OrganizationImportUser,
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
    PeerReviewTeam,
    ReviewAssignment,
    User,
)

settings = get_settings()


def seed_evaluation_system_state(db: Session) -> None:
    if db.get(EvaluationSystemState, 1) is None:
        db.add(EvaluationSystemState(id=1, status=SYSTEM_IDLE, current_cycle_id=None))
        db.commit()


def get_system_state(db: Session) -> EvaluationSystemState:
    state = db.get(EvaluationSystemState, 1)
    if state is None:
        state = EvaluationSystemState(id=1, status=SYSTEM_IDLE, current_cycle_id=None)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def get_system_state_for_update(db: Session) -> EvaluationSystemState:
    state = db.scalar(
        select(EvaluationSystemState)
        .where(EvaluationSystemState.id == 1)
        .with_for_update()
    )
    if state is None:
        state = EvaluationSystemState(id=1, status=SYSTEM_IDLE, current_cycle_id=None)
        db.add(state)
        db.flush()
    return state


def require_running_cycle(db: Session) -> EvaluationCycle:
    state = get_system_state(db)
    if state.status != SYSTEM_RUNNING or state.current_cycle_id is None:
        raise HTTPException(status_code=409, detail="Evaluation is not running")
    cycle = db.get(EvaluationCycle, state.current_cycle_id)
    if cycle is None or cycle.status != CYCLE_RUNNING:
        raise HTTPException(status_code=409, detail="Running evaluation cycle is not available")
    return cycle


def start_evaluation_cycle(db: Session, name: str) -> EvaluationCycle:
    state = get_system_state_for_update(db)
    if state.status != SYSTEM_IDLE:
        raise HTTPException(status_code=409, detail="Evaluation is already running")

    now = datetime.now(UTC)
    cycle = EvaluationCycle(name=name, snapshot_date=date.today(), status=CYCLE_RUNNING, started_at=now)
    db.add(cycle)
    db.flush()

    participant_by_user_id = snapshot_participants(db, cycle)
    snapshot_imported_users(db, cycle, participant_by_user_id)
    node_by_source_id = snapshot_org_nodes(db, cycle)
    snapshot_memberships(db, cycle, participant_by_user_id, node_by_source_id)
    snapshot_peer_teams(db, cycle, participant_by_user_id)
    snapshot_questions(db, cycle, node_by_source_id)
    snapshot_guides(db, cycle)
    generate_review_assignments(db, cycle)

    state.status = SYSTEM_RUNNING
    state.current_cycle_id = cycle.id
    db.commit()
    db.refresh(cycle)
    return cycle


def stop_evaluation_cycle(db: Session) -> None:
    state = get_system_state_for_update(db)
    if state.status != SYSTEM_RUNNING or state.current_cycle_id is None:
        raise HTTPException(status_code=400, detail="Evaluation is not running")
    cycle = db.get(EvaluationCycle, state.current_cycle_id)
    if cycle is not None:
        cycle.status = CYCLE_CLOSED
        cycle.ended_at = datetime.now(UTC)
    clear_live_setup_after_cycle(db)
    state.status = SYSTEM_IDLE
    state.current_cycle_id = None
    db.commit()


def clear_live_setup_after_cycle(db: Session) -> None:
    db.execute(delete(PeerReviewTeam))
    db.execute(delete(OrganizationImportUser))
    db.execute(delete(OrganizationMembership))
    db.execute(delete(EvaluationGuide))
    db.execute(delete(EvaluationQuestion))
    non_root_nodes = db.scalars(
        select(OrganizationNode).where(
            ~(
                (OrganizationNode.node_type == OrganizationNodeType.company)
                & (OrganizationNode.parent_id.is_(None))
            )
        )
    ).all()
    for node in sorted(non_root_nodes, key=lambda item: item.id, reverse=True):
        db.delete(node)
    root = db.scalar(
        select(OrganizationNode).where(
            OrganizationNode.node_type == OrganizationNodeType.company,
            OrganizationNode.parent_id.is_(None),
        )
    )
    if root is not None:
        root.name = "Company"


def snapshot_participants(db: Session, cycle: EvaluationCycle) -> dict[int, EvaluationParticipant]:
    users = db.scalars(
        select(User)
        .where(User.email != settings.initialization_email_normalized)
        .order_by(User.id)
    ).all()
    participant_by_user_id: dict[int, EvaluationParticipant] = {}
    for index, user in enumerate(users, start=1):
        participant = EvaluationParticipant(
            cycle_id=cycle.id,
            source_user_id=user.id,
            email_snapshot=user.email,
            display_name_snapshot=user.display_name,
            job_title_snapshot=user.job_title,
            system_role_snapshot=user.system_role.value,
            sort_order=index,
        )
        db.add(participant)
        db.flush()
        participant_by_user_id[user.id] = participant
    return participant_by_user_id


def snapshot_imported_users(
    db: Session,
    cycle: EvaluationCycle,
    participant_by_user_id: dict[int, EvaluationParticipant],
) -> None:
    imported_rows = db.scalars(
        select(OrganizationImportUser).order_by(OrganizationImportUser.sort_order, OrganizationImportUser.id)
    ).all()
    import_row_by_user_id = {row.user_id: row for row in imported_rows}
    participants = sorted(participant_by_user_id.values(), key=lambda item: (item.sort_order, item.id))
    last_sort_order = imported_rows[-1].sort_order if imported_rows else 0
    for index, participant in enumerate(participants, start=1):
        import_row = import_row_by_user_id.get(participant.source_user_id or 0)
        db.add(
            EvaluationImportUserSnapshot(
                cycle_id=cycle.id,
                source_import_user_id=import_row.id if import_row else None,
                participant_id=participant.id,
                attributes_snapshot=import_row.attributes if import_row else "",
                name_snapshot=(
                    import_row.name
                    if import_row
                    else (participant.display_name_snapshot or participant.email_snapshot or f"user-{participant.id}")
                ),
                title_snapshot=import_row.title if import_row else (participant.job_title_snapshot or ""),
                office_phone_snapshot=import_row.office_phone if import_row else "",
                mobile_snapshot=import_row.mobile if import_row else "",
                email_snapshot=import_row.email if import_row else (participant.email_snapshot or ""),
                note_snapshot=import_row.note if import_row else "",
                system_role_snapshot=participant.system_role_snapshot,
                sort_order_snapshot=import_row.sort_order if import_row else last_sort_order + index,
            )
        )
    db.flush()


def snapshot_org_nodes(db: Session, cycle: EvaluationCycle) -> dict[int, EvaluationOrgNodeSnapshot]:
    nodes = db.scalars(select(OrganizationNode).order_by(OrganizationNode.id)).all()
    snapshot_by_source_id: dict[int, EvaluationOrgNodeSnapshot] = {}
    pending = list(nodes)
    while pending:
        progressed = False
        for node in list(pending):
            parent_snapshot_id = None
            if node.parent_id is not None:
                parent = snapshot_by_source_id.get(node.parent_id)
                if parent is None:
                    continue
                parent_snapshot_id = parent.id
            snapshot = EvaluationOrgNodeSnapshot(
                cycle_id=cycle.id,
                source_node_id=node.id,
                name_snapshot=node.name,
                node_type_snapshot=node.node_type.value,
                parent_snapshot_id=parent_snapshot_id,
                sort_order=node.id,
            )
            db.add(snapshot)
            db.flush()
            snapshot_by_source_id[node.id] = snapshot
            pending.remove(node)
            progressed = True
        if not progressed:
            raise HTTPException(status_code=400, detail="Organization tree contains invalid parent references")
    return snapshot_by_source_id


def snapshot_memberships(
    db: Session,
    cycle: EvaluationCycle,
    participant_by_user_id: dict[int, EvaluationParticipant],
    node_by_source_id: dict[int, EvaluationOrgNodeSnapshot],
) -> None:
    memberships = db.scalars(select(OrganizationMembership).order_by(OrganizationMembership.id)).all()
    for membership in memberships:
        participant = participant_by_user_id.get(membership.user_id)
        node = node_by_source_id.get(membership.organization_node_id)
        if participant is None or node is None:
            continue
        db.add(
            EvaluationMembershipSnapshot(
                cycle_id=cycle.id,
                source_membership_id=membership.id,
                participant_id=participant.id,
                org_node_snapshot_id=node.id,
                membership_role_snapshot=membership.membership_role.value,
                sort_order=membership.id,
            )
        )
    db.flush()


def snapshot_peer_teams(
    db: Session,
    cycle: EvaluationCycle,
    participant_by_user_id: dict[int, EvaluationParticipant],
) -> None:
    teams = db.scalars(select(PeerReviewTeam).order_by(PeerReviewTeam.sort_order, PeerReviewTeam.id)).all()
    for team in teams:
        team_snapshot = EvaluationPeerTeamSnapshot(
            cycle_id=cycle.id,
            source_peer_team_id=team.id,
            name_snapshot=team.name,
            sort_order=team.sort_order,
        )
        db.add(team_snapshot)
        db.flush()
        for member in sorted(team.members, key=lambda item: (item.sort_order, item.id)):
            participant = participant_by_user_id.get(member.user_id)
            if participant is None:
                continue
            db.add(
                EvaluationPeerTeamMemberSnapshot(
                    cycle_id=cycle.id,
                    peer_team_snapshot_id=team_snapshot.id,
                    participant_id=participant.id,
                    sort_order=member.sort_order,
                )
            )
    db.flush()


def snapshot_questions(
    db: Session,
    cycle: EvaluationCycle,
    node_by_source_id: dict[int, EvaluationOrgNodeSnapshot],
) -> None:
    questions = db.scalars(
        select(EvaluationQuestion)
        .where(EvaluationQuestion.is_active.is_(True))
        .order_by(
            EvaluationQuestion.evaluation_type,
            EvaluationQuestion.organization_node_id,
            EvaluationQuestion.sort_order,
            EvaluationQuestion.id,
        )
    ).all()
    for question in questions:
        context_team_snapshot_id = None
        if question.evaluation_type == MANAGER_DETAIL:
            if question.organization_node_id is None:
                continue
            context_team_snapshot = node_by_source_id.get(question.organization_node_id)
            if context_team_snapshot is None:
                continue
            context_team_snapshot_id = context_team_snapshot.id
        db.add(
            EvaluationCycleQuestion(
                cycle_id=cycle.id,
                source_question_id=question.id,
                context_team_snapshot_id=context_team_snapshot_id,
                evaluation_type=question.evaluation_type,
                title_snapshot=question.title,
                description_snapshot=question.description,
                weight_snapshot=question.weight,
                sort_order_snapshot=question.sort_order,
            )
        )
    db.flush()


def snapshot_guides(db: Session, cycle: EvaluationCycle) -> None:
    guides = db.scalars(select(EvaluationGuide).order_by(EvaluationGuide.evaluation_type)).all()
    guide_by_type = {guide.evaluation_type: guide.content for guide in guides}
    for evaluation_type in sorted(EVALUATION_TYPES):
        db.add(
            EvaluationCycleGuide(
                cycle_id=cycle.id,
                evaluation_type=evaluation_type,
                content_markdown_snapshot=guide_by_type.get(evaluation_type, ""),
            )
        )
    db.flush()


def generate_review_assignments(db: Session, cycle: EvaluationCycle) -> None:
    participants = db.scalars(
        select(EvaluationParticipant)
        .where(EvaluationParticipant.cycle_id == cycle.id)
        .order_by(EvaluationParticipant.sort_order, EvaluationParticipant.id)
    ).all()
    sort_order = 1
    for participant in participants:
        db.add(
            ReviewAssignment(
                cycle_id=cycle.id,
                review_type=SELF,
                reviewer_participant_id=participant.id,
                target_participant_id=participant.id,
                status=ASSIGNMENT_PENDING,
                sort_order=sort_order,
            )
        )
        sort_order += 1

    sort_order = generate_peer_review_assignments(db, cycle, sort_order)
    generate_manager_detail_assignments(db, cycle, sort_order)
    db.flush()


def generate_peer_review_assignments(db: Session, cycle: EvaluationCycle, sort_order: int) -> int:
    team_snapshots = db.scalars(
        select(EvaluationPeerTeamSnapshot)
        .where(EvaluationPeerTeamSnapshot.cycle_id == cycle.id)
        .order_by(EvaluationPeerTeamSnapshot.sort_order, EvaluationPeerTeamSnapshot.id)
    ).all()
    for team_snapshot in team_snapshots:
        members = sorted(team_snapshot.members, key=lambda item: (item.sort_order, item.id))
        for reviewer_member in members:
            for target_member in members:
                db.add(
                    ReviewAssignment(
                        cycle_id=cycle.id,
                        review_type=PEER,
                        reviewer_participant_id=reviewer_member.participant_id,
                        target_participant_id=target_member.participant_id,
                        context_peer_team_snapshot_id=team_snapshot.id,
                        display_role_label_snapshot=team_snapshot.name_snapshot,
                        status=ASSIGNMENT_PENDING,
                        sort_order=sort_order,
                    )
                )
                sort_order += 1
    return sort_order


def generate_manager_detail_assignments(db: Session, cycle: EvaluationCycle, sort_order: int) -> int:
    team_snapshots = db.scalars(
        select(EvaluationOrgNodeSnapshot)
        .where(
            EvaluationOrgNodeSnapshot.cycle_id == cycle.id,
            EvaluationOrgNodeSnapshot.node_type_snapshot == OrganizationNodeType.team.value,
        )
        .order_by(EvaluationOrgNodeSnapshot.sort_order, EvaluationOrgNodeSnapshot.id)
    ).all()
    memberships = db.scalars(
        select(EvaluationMembershipSnapshot)
        .where(EvaluationMembershipSnapshot.cycle_id == cycle.id)
        .order_by(EvaluationMembershipSnapshot.sort_order, EvaluationMembershipSnapshot.id)
    ).all()
    memberships_by_node_id: dict[int, list[EvaluationMembershipSnapshot]] = defaultdict(list)
    for membership in memberships:
        memberships_by_node_id[membership.org_node_snapshot_id].append(membership)

    seen: set[tuple[int, int, int]] = set()
    for team_snapshot in team_snapshots:
        team_memberships = memberships_by_node_id.get(team_snapshot.id, [])
        if not team_memberships:
            continue
        team_member_targets = [
            membership
            for membership in team_memberships
            if membership.membership_role_snapshot == OrganizationMembershipRole.member.value
        ]
        team_all_targets = list(team_memberships)
        team_leaders = [
            membership
            for membership in team_memberships
            if membership.membership_role_snapshot == OrganizationMembershipRole.leader.value
        ]
        head_memberships = memberships_by_node_id.get(team_snapshot.parent_snapshot_id or 0, [])

        reviewer_targets: list[tuple[EvaluationMembershipSnapshot, list[EvaluationMembershipSnapshot], str]] = []
        reviewer_targets.extend((reviewer, team_member_targets, "팀장") for reviewer in team_leaders)
        reviewer_targets.extend((reviewer, team_all_targets, "본부") for reviewer in head_memberships)

        for reviewer, targets, role_label in reviewer_targets:
            for target in targets:
                key = (team_snapshot.id, reviewer.participant_id, target.participant_id)
                if key in seen:
                    continue
                seen.add(key)
                db.add(
                    ReviewAssignment(
                        cycle_id=cycle.id,
                        review_type=MANAGER_DETAIL,
                        reviewer_participant_id=reviewer.participant_id,
                        target_participant_id=target.participant_id,
                        context_team_snapshot_id=team_snapshot.id,
                        context_head_snapshot_id=team_snapshot.parent_snapshot_id,
                        display_role_label_snapshot=role_label,
                        status=ASSIGNMENT_PENDING,
                        sort_order=sort_order,
                    )
                )
                sort_order += 1
    return sort_order


def serialize_system_state(state: EvaluationSystemState, cycle: EvaluationCycle | None = None) -> dict:
    current_cycle = cycle or state.current_cycle
    return {
        "status": state.status,
        "current_cycle": serialize_cycle(current_cycle) if current_cycle else None,
    }


def serialize_cycle(cycle: EvaluationCycle) -> dict:
    return {
        "id": cycle.id,
        "name": cycle.name,
        "snapshot_date": cycle.snapshot_date.isoformat(),
        "status": cycle.status,
        "started_at": cycle.started_at.isoformat() if cycle.started_at else None,
        "ended_at": cycle.ended_at.isoformat() if cycle.ended_at else None,
    }


def require_cycle_participant(db: Session, cycle: EvaluationCycle, user: User) -> EvaluationParticipant:
    participant = db.scalar(
        select(EvaluationParticipant).where(
            EvaluationParticipant.cycle_id == cycle.id,
            EvaluationParticipant.source_user_id == user.id,
        )
    )
    if participant is None:
        raise HTTPException(status_code=403, detail="Current user is not included in this evaluation")
    return participant


def self_assignment(db: Session, cycle: EvaluationCycle, participant: EvaluationParticipant) -> ReviewAssignment:
    assignment = db.scalar(
        select(ReviewAssignment).where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == SELF,
            ReviewAssignment.reviewer_participant_id == participant.id,
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Self review assignment not found")
    return assignment


def cycle_questions(
    db: Session,
    cycle: EvaluationCycle,
    evaluation_type: str,
    context_team_snapshot_id: int | None = None,
) -> list[EvaluationCycleQuestion]:
    query = select(EvaluationCycleQuestion).where(
        EvaluationCycleQuestion.cycle_id == cycle.id,
        EvaluationCycleQuestion.evaluation_type == evaluation_type,
    )
    if evaluation_type == MANAGER_DETAIL:
        query = query.where(EvaluationCycleQuestion.context_team_snapshot_id == context_team_snapshot_id)
    else:
        query = query.where(EvaluationCycleQuestion.context_team_snapshot_id.is_(None))
    return db.scalars(query.order_by(EvaluationCycleQuestion.sort_order_snapshot, EvaluationCycleQuestion.id)).all()


def cycle_guide_content(db: Session, cycle: EvaluationCycle, evaluation_type: str) -> str:
    guide = db.scalar(
        select(EvaluationCycleGuide).where(
            EvaluationCycleGuide.cycle_id == cycle.id,
            EvaluationCycleGuide.evaluation_type == evaluation_type,
        )
    )
    return guide.content_markdown_snapshot if guide else ""
