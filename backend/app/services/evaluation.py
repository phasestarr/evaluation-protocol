from datetime import UTC, date, datetime
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import delete, func, select
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
    WEIGHTED_EVALUATION_TYPES,
)
from app.db.postgres.models import (
    EvaluationCycle,
    EvaluationCycleGuide,
    EvaluationCycleQuestion,
    EvaluationGuide,
    EvaluationMembershipSnapshot,
    EvaluationOrgNodeSnapshot,
    EvaluationPeerTeamMemberSnapshot,
    EvaluationPeerTeamSnapshot,
    EvaluationParticipant,
    EvaluationQuestion,
    EvaluationSystemState,
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationImportUser,
    OrganizationNode,
    OrganizationNodeType,
    PeerReviewTeamMember,
    PeerReviewTeam,
    ReviewAssignment,
    ReviewScore,
    SelfReviewAnswer,
    User,
)
from app.services.text import normalize_optional_text

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


def list_questions(db: Session) -> list[EvaluationQuestion]:
    return db.scalars(
        select(EvaluationQuestion).order_by(
            EvaluationQuestion.evaluation_type,
            EvaluationQuestion.organization_node_id,
            EvaluationQuestion.sort_order,
            EvaluationQuestion.id,
        )
    ).all()


def create_question(
    db: Session,
    evaluation_type_value: str,
    title_value: str,
    description: str | None,
    weight_value: int | None,
    organization_node_id: int | None = None,
) -> EvaluationQuestion:
    evaluation_type = parse_evaluation_type(evaluation_type_value)
    title = title_value.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Question title is required")
    normalized_description = normalize_optional_text(description)
    if normalized_description is None:
        raise HTTPException(status_code=400, detail="Question description is required")

    weight = None
    if evaluation_type in WEIGHTED_EVALUATION_TYPES:
        if weight_value is None or weight_value <= 0:
            raise HTTPException(status_code=400, detail="Question weight must be greater than zero")
        weight = weight_value

    if evaluation_type == MANAGER_DETAIL:
        if organization_node_id is None:
            raise HTTPException(status_code=400, detail="Manager detail questions require a team")
        organization_node = db.get(OrganizationNode, organization_node_id)
        if organization_node is None or organization_node.node_type != OrganizationNodeType.team:
            raise HTTPException(status_code=400, detail="Manager detail questions require an organization team")
    elif organization_node_id is not None:
        raise HTTPException(status_code=400, detail="Only manager detail questions can be scoped to a team")

    next_sort_order = (
        db.scalar(
            select(func.coalesce(func.max(EvaluationQuestion.sort_order), 0)).where(
                EvaluationQuestion.evaluation_type == evaluation_type,
                EvaluationQuestion.organization_node_id == organization_node_id,
            )
        )
        or 0
    ) + 1
    question = EvaluationQuestion(
        evaluation_type=evaluation_type,
        organization_node_id=organization_node_id,
        title=title,
        description=normalized_description,
        weight=weight,
        sort_order=next_sort_order,
        is_active=True,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: int) -> None:
    question = db.get(EvaluationQuestion, question_id)
    if question is not None:
        db.delete(question)
        db.commit()


def evaluation_guide_content(db: Session, evaluation_type: str) -> str:
    guide = db.scalar(select(EvaluationGuide).where(EvaluationGuide.evaluation_type == evaluation_type))
    return guide.content if guide else ""


def save_evaluation_guide(db: Session, evaluation_type_value: str, content: str) -> str:
    evaluation_type = parse_evaluation_type(evaluation_type_value)
    guide = db.scalar(select(EvaluationGuide).where(EvaluationGuide.evaluation_type == evaluation_type))
    if guide is None:
        guide = EvaluationGuide(evaluation_type=evaluation_type, content=content)
        db.add(guide)
    else:
        guide.content = content
    db.commit()
    return evaluation_type


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


def serialize_question(question: EvaluationQuestion, effective_weight_percent: float | None) -> dict:
    return {
        "id": question.id,
        "evaluation_type": question.evaluation_type,
        "organization_node_id": question.organization_node_id,
        "title": question.title,
        "description": question.description,
        "weight": question.weight,
        "effective_weight_percent": effective_weight_percent,
        "sort_order": question.sort_order,
        "is_active": question.is_active,
    }


def serialize_cycle_question(question: EvaluationCycleQuestion, effective_weight_percent: float | None) -> dict:
    return {
        "id": question.id,
        "evaluation_type": question.evaluation_type,
        "organization_node_id": question.context_team_snapshot_id,
        "title": question.title_snapshot,
        "description": question.description_snapshot,
        "weight": question.weight_snapshot,
        "effective_weight_percent": effective_weight_percent,
        "sort_order": question.sort_order_snapshot,
        "is_active": True,
    }


def serialize_questions_with_effective_weights(questions: list[EvaluationQuestion]) -> list[dict]:
    total_weight_by_scope: dict[tuple[str, int | None], int] = {}
    for question in questions:
        if question.evaluation_type in WEIGHTED_EVALUATION_TYPES:
            key = (question.evaluation_type, question.organization_node_id)
            total_weight_by_scope[key] = total_weight_by_scope.get(key, 0) + (question.weight or 0)
    result: list[dict] = []
    for question in questions:
        effective_weight = None
        total_weight = total_weight_by_scope.get((question.evaluation_type, question.organization_node_id), 0)
        if question.evaluation_type in WEIGHTED_EVALUATION_TYPES and total_weight > 0 and question.weight:
            effective_weight = round(question.weight / total_weight * 100, 2)
        result.append(serialize_question(question, effective_weight))
    return result


def serialize_cycle_questions_with_effective_weights(questions: list[EvaluationCycleQuestion]) -> list[dict]:
    total_weight_by_scope: dict[tuple[str, int | None], int] = {}
    for question in questions:
        if question.evaluation_type in WEIGHTED_EVALUATION_TYPES:
            key = (question.evaluation_type, question.context_team_snapshot_id)
            total_weight_by_scope[key] = total_weight_by_scope.get(key, 0) + (question.weight_snapshot or 0)
    result: list[dict] = []
    for question in questions:
        effective_weight = None
        total_weight = total_weight_by_scope.get((question.evaluation_type, question.context_team_snapshot_id), 0)
        if question.evaluation_type in WEIGHTED_EVALUATION_TYPES and total_weight > 0 and question.weight_snapshot:
            effective_weight = round(question.weight_snapshot / total_weight * 100, 2)
        result.append(serialize_cycle_question(question, effective_weight))
    return result


def parse_evaluation_type(value: str) -> str:
    if value not in EVALUATION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid evaluation type")
    return value


def save_self_answer(
    db: Session,
    assignment: ReviewAssignment,
    question: EvaluationCycleQuestion,
    answer_text: str,
) -> None:
    if assignment.cycle_id != question.cycle_id:
        raise HTTPException(status_code=400, detail="Assignment and question belong to different cycles")
    answer = db.scalar(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.assignment_id == assignment.id,
            SelfReviewAnswer.cycle_question_id == question.id,
        )
    )
    if answer is None:
        answer = SelfReviewAnswer(
            cycle_id=assignment.cycle_id,
            assignment_id=assignment.id,
            cycle_question_id=question.id,
            answer_text=answer_text,
        )
        db.add(answer)
    else:
        answer.answer_text = answer_text
    db.commit()


def save_review_score(db: Session, assignment: ReviewAssignment, question_id: int, score_value: int) -> None:
    score = db.scalar(
        select(ReviewScore).where(
            ReviewScore.assignment_id == assignment.id,
            ReviewScore.cycle_question_id == question_id,
        )
    )
    if score is None:
        db.add(
            ReviewScore(
                cycle_id=assignment.cycle_id,
                assignment_id=assignment.id,
                cycle_question_id=question_id,
                score=score_value,
            )
        )
    else:
        score.score = score_value


def admin_readiness(db: Session) -> dict:
    org_user_count = db.scalar(select(func.count()).select_from(OrganizationImportUser)) or 0
    non_root_node_count = db.scalar(
        select(func.count())
        .select_from(OrganizationNode)
        .where(OrganizationNode.node_type != OrganizationNodeType.company)
    ) or 0
    peer_team_count = db.scalar(select(func.count()).select_from(PeerReviewTeam)) or 0
    peer_team_member_count = db.scalar(select(func.count()).select_from(PeerReviewTeamMember)) or 0
    self_question_stats = active_question_stats(db, SELF)
    peer_question_stats = active_question_stats(db, PEER)
    manager_guide_complete = evaluation_guide_exists(db, MANAGER_DETAIL)

    teams = db.scalars(
        select(OrganizationNode)
        .where(OrganizationNode.node_type == OrganizationNodeType.team)
        .order_by(OrganizationNode.id)
    ).all()
    manager_question_stats = {
        team.id: active_question_stats(db, MANAGER_DETAIL, team.id)
        for team in teams
    }
    manager_team_items = [
        {
            "id": team.id,
            "name": team.name,
            "complete": manager_question_stats[team.id]["complete"],
            "question_count": manager_question_stats[team.id]["total_count"],
            "complete_question_count": manager_question_stats[team.id]["complete_count"],
        }
        for team in teams
    ]

    items = {
        "organization": {
            "complete": org_user_count > 0 and non_root_node_count > 0,
            "label": "조직 관리",
            "detail": f"사용자 {org_user_count}명, 조직 노드 {non_root_node_count}개",
        },
        "peer_teams": {
            "complete": peer_team_count > 0 and peer_team_member_count > 0,
            "label": "동료평가 팀 관리",
            "detail": f"팀 {peer_team_count}개, 멤버 {peer_team_member_count}명",
        },
        "self_questions": {
            "complete": self_question_stats["complete"],
            "label": "자기평가 문항 관리",
            "detail": question_readiness_detail(self_question_stats),
        },
        "peer_questions": {
            "complete": peer_question_stats["complete"],
            "label": "동료평가 문항 관리",
            "detail": question_readiness_detail(peer_question_stats),
        },
        "manager_detail_questions": {
            "complete": bool(manager_team_items) and all(item["complete"] for item in manager_team_items),
            "label": "팀원평가 문항 관리",
            "detail": (
                f"{'안내문 완료' if manager_guide_complete else '안내문 미완료'}, "
                f"완료 {sum(1 for item in manager_team_items if item['complete'])}/{len(manager_team_items)}팀"
            ),
            "teams": manager_team_items,
        },
    }
    return {
        "ready": all(item["complete"] for item in items.values()),
        "items": items,
    }


def active_question_stats(db: Session, evaluation_type: str, organization_node_id: int | None = None) -> dict:
    query = select(EvaluationQuestion).where(
        EvaluationQuestion.evaluation_type == evaluation_type,
        EvaluationQuestion.is_active.is_(True),
    )
    if evaluation_type == MANAGER_DETAIL:
        query = query.where(EvaluationQuestion.organization_node_id == organization_node_id)
    questions = db.scalars(query).all()
    total_count = len(questions)
    guide_complete = evaluation_guide_exists(db, evaluation_type)
    return {
        "complete": guide_complete and total_count > 0,
        "complete_count": total_count if guide_complete and total_count > 0 else 0,
        "guide_complete": guide_complete,
        "total_count": total_count,
    }


def evaluation_guide_exists(db: Session, evaluation_type: str) -> bool:
    return bool(evaluation_guide_content(db, evaluation_type).strip())


def question_readiness_detail(stats: dict) -> str:
    guide_label = "안내문 완료" if stats["guide_complete"] else "안내문 미완료"
    return f"{guide_label}, 문항 {stats['total_count']}개"
