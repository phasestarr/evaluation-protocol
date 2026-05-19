from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import (
    ASSIGNMENT_PENDING,
    CYCLE_CLOSED,
    CYCLE_RUNNING,
    EVALUATION_TYPES,
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
    EvaluationParticipant,
    EvaluationQuestion,
    EvaluationSystemState,
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
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


def require_running_cycle(db: Session) -> EvaluationCycle:
    state = get_system_state(db)
    if state.status != SYSTEM_RUNNING or state.current_cycle_id is None:
        raise HTTPException(status_code=409, detail="Evaluation is not running")
    cycle = db.get(EvaluationCycle, state.current_cycle_id)
    if cycle is None or cycle.status != CYCLE_RUNNING:
        raise HTTPException(status_code=409, detail="Running evaluation cycle is not available")
    return cycle


def start_evaluation_cycle(db: Session, name: str) -> EvaluationCycle:
    state = get_system_state(db)
    if state.status != SYSTEM_IDLE:
        raise HTTPException(status_code=409, detail="Evaluation is already running")

    now = datetime.now(UTC)
    cycle = EvaluationCycle(name=name, snapshot_date=date.today(), status=CYCLE_RUNNING, started_at=now)
    db.add(cycle)
    db.flush()

    participant_by_user_id = snapshot_participants(db, cycle)
    node_by_source_id = snapshot_org_nodes(db, cycle)
    snapshot_memberships(db, cycle, participant_by_user_id, node_by_source_id)
    snapshot_questions(db, cycle)
    snapshot_guides(db, cycle)
    generate_review_assignments(db, cycle)

    state.status = SYSTEM_RUNNING
    state.current_cycle_id = cycle.id
    db.commit()
    db.refresh(cycle)
    return cycle


def stop_evaluation_cycle(db: Session) -> None:
    state = get_system_state(db)
    if state.status != SYSTEM_RUNNING or state.current_cycle_id is None:
        raise HTTPException(status_code=400, detail="Evaluation is not running")
    cycle = db.get(EvaluationCycle, state.current_cycle_id)
    if cycle is not None:
        cycle.status = CYCLE_CLOSED
        cycle.ended_at = datetime.now(UTC)
    state.status = SYSTEM_IDLE
    state.current_cycle_id = None
    db.commit()


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


def snapshot_questions(db: Session, cycle: EvaluationCycle) -> None:
    questions = db.scalars(
        select(EvaluationQuestion)
        .where(EvaluationQuestion.is_active.is_(True))
        .order_by(EvaluationQuestion.evaluation_type, EvaluationQuestion.sort_order, EvaluationQuestion.id)
    ).all()
    for question in questions:
        db.add(
            EvaluationCycleQuestion(
                cycle_id=cycle.id,
                source_question_id=question.id,
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

    team_nodes = db.scalars(
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
    memberships_by_node_id: dict[int, list[EvaluationMembershipSnapshot]] = {}
    for membership in memberships:
        memberships_by_node_id.setdefault(membership.org_node_snapshot_id, []).append(membership)

    seen_peer_contexts: set[tuple[int, int]] = set()
    seen_peer_assignments: set[tuple[int, int, int]] = set()
    for team in team_nodes:
        team_memberships = sorted(memberships_by_node_id.get(team.id, []), key=snapshot_membership_sort_key)
        head_memberships = sorted(memberships_by_node_id.get(team.parent_snapshot_id or -1, []), key=snapshot_membership_sort_key)
        targets = dedupe_membership_targets([*head_memberships, *team_memberships])
        for reviewer_membership in team_memberships:
            reviewer_id = reviewer_membership.participant_id
            context_key = (reviewer_id, team.id)
            if context_key in seen_peer_contexts:
                continue
            seen_peer_contexts.add(context_key)
            for target_membership in targets:
                assignment_key = (reviewer_id, team.id, target_membership.participant_id)
                if assignment_key in seen_peer_assignments:
                    continue
                seen_peer_assignments.add(assignment_key)
                db.add(
                    ReviewAssignment(
                        cycle_id=cycle.id,
                        review_type=PEER,
                        reviewer_participant_id=reviewer_id,
                        target_participant_id=target_membership.participant_id,
                        context_team_snapshot_id=team.id,
                        context_head_snapshot_id=team.parent_snapshot_id,
                        display_role_label_snapshot=snapshot_membership_role_display(target_membership),
                        status=ASSIGNMENT_PENDING,
                        sort_order=sort_order,
                    )
                )
                sort_order += 1
    db.flush()


def snapshot_membership_sort_key(membership: EvaluationMembershipSnapshot) -> tuple[list[int], int, int]:
    role_priority = 0 if membership.membership_role_snapshot == OrganizationMembershipRole.leader.value else 1
    return snapshot_node_path_ids(membership.org_node), role_priority, membership.sort_order


def snapshot_node_path_ids(node: EvaluationOrgNodeSnapshot) -> list[int]:
    ids: list[int] = []
    cursor: EvaluationOrgNodeSnapshot | None = node
    while cursor is not None:
        ids.append(cursor.sort_order)
        cursor = cursor.parent
    return list(reversed(ids))


def dedupe_membership_targets(memberships: list[EvaluationMembershipSnapshot]) -> list[EvaluationMembershipSnapshot]:
    seen_participant_ids: set[int] = set()
    targets: list[EvaluationMembershipSnapshot] = []
    for membership in sorted(memberships, key=snapshot_membership_sort_key):
        if membership.participant_id in seen_participant_ids:
            continue
        seen_participant_ids.add(membership.participant_id)
        targets.append(membership)
    return targets


def snapshot_membership_role_display(membership: EvaluationMembershipSnapshot) -> str:
    if membership.membership_role_snapshot == OrganizationMembershipRole.member.value:
        if membership.org_node.node_type_snapshot == OrganizationNodeType.head.value:
            return "본부원"
        return "팀원"
    if membership.org_node.node_type_snapshot == OrganizationNodeType.head.value:
        return "본부장"
    if membership.org_node.node_type_snapshot == OrganizationNodeType.team.value:
        return "팀장"
    return "관리자"


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
        select(EvaluationQuestion).order_by(EvaluationQuestion.evaluation_type, EvaluationQuestion.sort_order, EvaluationQuestion.id)
    ).all()


def create_question(
    db: Session,
    evaluation_type_value: str,
    title_value: str,
    description: str | None,
    weight_value: int | None,
) -> EvaluationQuestion:
    evaluation_type = parse_evaluation_type(evaluation_type_value)
    title = title_value.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Question title is required")

    weight = None
    if evaluation_type in WEIGHTED_EVALUATION_TYPES:
        if weight_value is None or weight_value <= 0:
            raise HTTPException(status_code=400, detail="Question weight must be greater than zero")
        weight = weight_value

    next_sort_order = (
        db.scalar(
            select(func.coalesce(func.max(EvaluationQuestion.sort_order), 0)).where(
                EvaluationQuestion.evaluation_type == evaluation_type
            )
        )
        or 0
    ) + 1
    question = EvaluationQuestion(
        evaluation_type=evaluation_type,
        title=title,
        description=normalize_optional_text(description),
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


def cycle_questions(db: Session, cycle: EvaluationCycle, evaluation_type: str) -> list[EvaluationCycleQuestion]:
    return db.scalars(
        select(EvaluationCycleQuestion)
        .where(
            EvaluationCycleQuestion.cycle_id == cycle.id,
            EvaluationCycleQuestion.evaluation_type == evaluation_type,
        )
        .order_by(EvaluationCycleQuestion.sort_order_snapshot, EvaluationCycleQuestion.id)
    ).all()


def cycle_guide_content(db: Session, cycle: EvaluationCycle, evaluation_type: str) -> str:
    guide = db.scalar(
        select(EvaluationCycleGuide).where(
            EvaluationCycleGuide.cycle_id == cycle.id,
            EvaluationCycleGuide.evaluation_type == evaluation_type,
        )
    )
    return guide.content_markdown_snapshot if guide else ""


def require_cycle_team_context(db: Session, cycle: EvaluationCycle, team_node_id: int) -> EvaluationOrgNodeSnapshot:
    team = db.get(EvaluationOrgNodeSnapshot, team_node_id)
    if team is None or team.cycle_id != cycle.id or team.node_type_snapshot != OrganizationNodeType.team.value:
        raise HTTPException(status_code=404, detail="Team context not found")
    return team


def peer_assignments_for_reviewer(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
) -> list[ReviewAssignment]:
    return db.scalars(
        select(ReviewAssignment)
        .where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == PEER,
            ReviewAssignment.reviewer_participant_id == participant.id,
        )
        .order_by(ReviewAssignment.sort_order, ReviewAssignment.id)
    ).all()


def peer_assignments_for_team(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    team: EvaluationOrgNodeSnapshot,
) -> list[ReviewAssignment]:
    assignments = db.scalars(
        select(ReviewAssignment)
        .where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == PEER,
            ReviewAssignment.reviewer_participant_id == participant.id,
            ReviewAssignment.context_team_snapshot_id == team.id,
        )
        .order_by(ReviewAssignment.sort_order, ReviewAssignment.id)
    ).all()
    if not assignments:
        raise HTTPException(status_code=403, detail="Team review is not available for this user")
    return assignments


def serialize_peer_contexts(assignments: list[ReviewAssignment]) -> list[dict]:
    contexts: list[dict] = []
    seen_team_ids: set[int] = set()
    for assignment in assignments:
        team = assignment.context_team
        if team is None or team.id in seen_team_ids:
            continue
        seen_team_ids.add(team.id)
        contexts.append(
            {
                "team_node_id": team.id,
                "title": ">".join(snapshot_node_path_segments(team)),
                "role_label": "동료평가",
            }
        )
    return contexts


def serialize_snapshot_team_node(team: EvaluationOrgNodeSnapshot) -> dict:
    return {
        "id": team.id,
        "title": ">".join(snapshot_node_path_segments(team)),
    }


def serialize_assignment_target(assignment: ReviewAssignment) -> dict:
    target = assignment.target
    return {
        "user_id": target.id if target else None,
        "display_name": target.display_name_snapshot if target else None,
        "email": target.email_snapshot if target else None,
        "job_title": target.job_title_snapshot if target else None,
        "role_label": assignment.display_role_label_snapshot,
        "affiliation": ">".join(snapshot_node_path_segments(assignment.context_team)) if assignment.context_team else "",
    }


def snapshot_node_path_segments(node: EvaluationOrgNodeSnapshot | None) -> list[str]:
    segments: list[str] = []
    cursor = node
    while cursor is not None:
        segments.append(cursor.name_snapshot)
        cursor = cursor.parent
    return list(reversed(segments))


def serialize_question(question: EvaluationQuestion, effective_weight_percent: float | None) -> dict:
    return {
        "id": question.id,
        "evaluation_type": question.evaluation_type,
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
        "title": question.title_snapshot,
        "description": question.description_snapshot,
        "weight": question.weight_snapshot,
        "effective_weight_percent": effective_weight_percent,
        "sort_order": question.sort_order_snapshot,
        "is_active": True,
    }


def serialize_questions_with_effective_weights(questions: list[EvaluationQuestion]) -> list[dict]:
    total_weight_by_type = {
        evaluation_type: sum(question.weight or 0 for question in questions if question.evaluation_type == evaluation_type)
        for evaluation_type in WEIGHTED_EVALUATION_TYPES
    }
    result: list[dict] = []
    for question in questions:
        effective_weight = None
        total_weight = total_weight_by_type.get(question.evaluation_type, 0)
        if question.evaluation_type in WEIGHTED_EVALUATION_TYPES and total_weight > 0 and question.weight:
            effective_weight = round(question.weight / total_weight * 100, 2)
        result.append(serialize_question(question, effective_weight))
    return result


def serialize_cycle_questions_with_effective_weights(questions: list[EvaluationCycleQuestion]) -> list[dict]:
    total_weight_by_type = {
        evaluation_type: sum(question.weight_snapshot or 0 for question in questions if question.evaluation_type == evaluation_type)
        for evaluation_type in WEIGHTED_EVALUATION_TYPES
    }
    result: list[dict] = []
    for question in questions:
        effective_weight = None
        total_weight = total_weight_by_type.get(question.evaluation_type, 0)
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
    answer = db.scalar(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.assignment_id == assignment.id,
            SelfReviewAnswer.cycle_question_id == question.id,
        )
    )
    if answer is None:
        answer = SelfReviewAnswer(assignment_id=assignment.id, cycle_question_id=question.id, answer_text=answer_text)
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
        db.add(ReviewScore(assignment_id=assignment.id, cycle_question_id=question_id, score=score_value))
    else:
        score.score = score_value
