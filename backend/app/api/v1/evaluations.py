from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.schemas import ReviewScoresIn, SelfReviewAnswerIn
from app.constants import MANAGER_DETAIL, PEER, SELF
from app.db.postgres.models import (
    EvaluationCycle,
    EvaluationCycleQuestion,
    EvaluationOrgNodeSnapshot,
    EvaluationParticipant,
    EvaluationPeerTeamSnapshot,
    ReviewAssignment,
    ReviewScore,
    SelfReviewAnswer,
)
from app.db.postgres.session import get_db
from app.services.authz import require_user
from app.services.evaluation import (
    cycle_guide_content,
    cycle_questions,
    require_cycle_participant,
    require_running_cycle,
    save_review_score,
    save_self_answer,
    self_assignment,
    serialize_cycle_question,
    serialize_cycle_questions_with_effective_weights,
)

router = APIRouter()


@router.get("/api/evaluations/self")
def self_review(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    assignment = self_assignment(db, cycle, participant)
    questions = cycle_questions(db, cycle, SELF)
    answers = db.scalars(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.assignment_id == assignment.id,
            SelfReviewAnswer.cycle_question_id.in_([question.id for question in questions]),
        )
    ).all()
    answer_by_question_id = {answer.cycle_question_id: answer.answer_text for answer in answers}
    return {
        "guide_content": cycle_guide_content(db, cycle, SELF),
        "questions": [serialize_cycle_question(question, effective_weight_percent=None) for question in questions],
        "answers": answer_by_question_id,
    }


@router.put("/api/evaluations/self/answers/{question_id}")
def save_self_review_answer(
    question_id: int,
    payload: SelfReviewAnswerIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    assignment = self_assignment(db, cycle, participant)
    answer_text = payload.answer_text.strip()
    if len(answer_text) > 1000:
        raise HTTPException(status_code=400, detail="Answer must be 1000 characters or fewer")
    question = db.get(EvaluationCycleQuestion, question_id)
    if question is None or question.cycle_id != cycle.id or question.evaluation_type != SELF:
        raise HTTPException(status_code=404, detail="Self review question not found")

    save_self_answer(db, assignment, question, answer_text)
    return {"ok": True}


@router.get("/api/evaluations/progress")
def evaluation_progress(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    self_status = self_review_completion(db, cycle, participant)
    peer_contexts = review_contexts(db, cycle, participant, PEER)
    manager_contexts = review_contexts(db, cycle, participant, MANAGER_DETAIL)
    return {
        "self": self_status,
        "peer": summarize_context_completion(peer_contexts),
        "manager_detail": summarize_context_completion(manager_contexts),
    }


@router.get("/api/evaluations/peer-contexts")
def peer_review_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return {"contexts": review_contexts(db, cycle, participant, PEER)}


@router.get("/api/evaluations/peer/{team_node_id}")
def peer_review(team_node_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return review_payload(db, cycle, participant, PEER, team_node_id)


@router.put("/api/evaluations/peer/{team_node_id}/scores")
def save_peer_review_scores(
    team_node_id: int,
    payload: ReviewScoresIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    save_weighted_review_scores(db, cycle, participant, PEER, team_node_id, payload)
    return {"ok": True}


@router.get("/api/evaluations/manager-detail-contexts")
def manager_detail_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return {"contexts": review_contexts(db, cycle, participant, MANAGER_DETAIL)}


@router.get("/api/evaluations/manager-detail/{team_node_id}")
def manager_detail_review(team_node_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return review_payload(db, cycle, participant, MANAGER_DETAIL, team_node_id)


@router.put("/api/evaluations/manager-detail/{team_node_id}/scores")
def save_manager_detail_scores(
    team_node_id: int,
    payload: ReviewScoresIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    save_weighted_review_scores(db, cycle, participant, MANAGER_DETAIL, team_node_id, payload)
    return {"ok": True}


def review_contexts(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    review_type: str,
) -> list[dict]:
    assignments = db.scalars(
        select(ReviewAssignment)
        .where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == review_type,
            ReviewAssignment.reviewer_participant_id == participant.id,
        )
        .order_by(ReviewAssignment.sort_order, ReviewAssignment.id)
    ).all()
    context_by_id: dict[int, dict] = {}
    target_ids_by_context_id: dict[int, set[int]] = {}
    for assignment in assignments:
        context_id = review_context_id(assignment, review_type)
        if context_id is None:
            continue
        if context_id not in context_by_id:
            context_by_id[context_id] = {
                "team_node_id": context_id,
                "title": review_context_title(assignment, review_type),
                "role_label": "",
                "complete": False,
            }
            target_ids_by_context_id[context_id] = set()
        if assignment.target_participant_id is not None:
            target_ids_by_context_id[context_id].add(assignment.target_participant_id)

    result = []
    for context_id, context in context_by_id.items():
        target_count = len(target_ids_by_context_id.get(context_id, set()))
        context["role_label"] = f"{target_count}명"
        context["complete"] = weighted_review_completion(db, cycle, participant, review_type, context_id)["complete"]
        result.append(context)
    return result


def review_payload(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    review_type: str,
    context_id: int,
) -> dict:
    assignments = review_assignments_for_context(db, cycle, participant, review_type, context_id)
    if not assignments:
        raise HTTPException(status_code=404, detail="Review assignment not found")

    questions = cycle_questions(db, cycle, review_type, context_id if review_type == MANAGER_DETAIL else None)
    assignment_by_target_id = {
        assignment.target_participant_id: assignment
        for assignment in assignments
        if assignment.target_participant_id is not None and assignment.target is not None
    }
    assignment_ids = [assignment.id for assignment in assignment_by_target_id.values()]
    question_ids = [question.id for question in questions]
    scores = []
    if assignment_ids and question_ids:
        scores = db.scalars(
            select(ReviewScore).where(
                ReviewScore.assignment_id.in_(assignment_ids),
                ReviewScore.cycle_question_id.in_(question_ids),
            )
        ).all()
    target_id_by_assignment_id = {
        assignment.id: assignment.target_participant_id
        for assignment in assignment_by_target_id.values()
    }
    score_by_cell = {
        f"{target_id_by_assignment_id[score.assignment_id]}:{score.cycle_question_id}": score.score
        for score in scores
        if score.assignment_id in target_id_by_assignment_id
    }
    first_assignment = assignments[0]
    return {
        "team": {"id": context_id, "title": review_context_title(first_assignment, review_type)},
        "guide_content": cycle_guide_content(db, cycle, review_type),
        "questions": serialize_cycle_questions_with_effective_weights(questions),
        "targets": [
            serialize_review_target(assignment.target, target_role_label(assignment.target), db)
            for assignment in assignment_by_target_id.values()
            if assignment.target is not None
        ],
        "scores": score_by_cell,
    }


def save_weighted_review_scores(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    review_type: str,
    context_id: int,
    payload: ReviewScoresIn,
) -> None:
    assignments = review_assignments_for_context(db, cycle, participant, review_type, context_id)
    assignment_by_target_id = {
        assignment.target_participant_id: assignment
        for assignment in assignments
        if assignment.target_participant_id is not None
    }
    questions = cycle_questions(db, cycle, review_type, context_id if review_type == MANAGER_DETAIL else None)
    question_ids = {question.id for question in questions}
    for score in payload.scores:
        if not 0 <= score.score <= 100:
            raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
        assignment = assignment_by_target_id.get(score.target_user_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail="Review target not found")
        if score.question_id not in question_ids:
            raise HTTPException(status_code=404, detail="Review question not found")
        save_review_score(db, assignment, score.question_id, score.score)
    db.commit()


def self_review_completion(db: Session, cycle: EvaluationCycle, participant: EvaluationParticipant) -> dict:
    assignment = db.scalar(
        select(ReviewAssignment).where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == SELF,
            ReviewAssignment.reviewer_participant_id == participant.id,
        )
    )
    questions = cycle_questions(db, cycle, SELF)
    if assignment is None or not questions:
        return {"complete": False, "completed_count": 0, "total_count": len(questions)}
    question_ids = [question.id for question in questions]
    answers = db.scalars(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.assignment_id == assignment.id,
            SelfReviewAnswer.cycle_question_id.in_(question_ids),
        )
    ).all()
    answered_question_ids = {
        answer.cycle_question_id
        for answer in answers
        if answer.answer_text.strip()
    }
    return {
        "complete": len(answered_question_ids) == len(question_ids),
        "completed_count": len(answered_question_ids),
        "total_count": len(question_ids),
    }


def weighted_review_completion(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    review_type: str,
    context_id: int,
) -> dict:
    assignments = review_assignments_for_context(db, cycle, participant, review_type, context_id)
    questions = cycle_questions(db, cycle, review_type, context_id if review_type == MANAGER_DETAIL else None)
    assignment_ids = [
        assignment.id
        for assignment in assignments
        if assignment.target_participant_id is not None
    ]
    total_count = len(assignment_ids) * len(questions)
    if total_count == 0:
        return {"complete": False, "completed_count": 0, "total_count": total_count}
    completed_count = db.scalar(
        select(func.count())
        .select_from(ReviewScore)
        .where(
            ReviewScore.assignment_id.in_(assignment_ids),
            ReviewScore.cycle_question_id.in_([question.id for question in questions]),
        )
    ) or 0
    return {
        "complete": completed_count == total_count,
        "completed_count": completed_count,
        "total_count": total_count,
    }


def summarize_context_completion(contexts: list[dict]) -> dict:
    total_count = len(contexts)
    completed_count = sum(1 for context in contexts if context.get("complete"))
    return {
        "complete": total_count > 0 and completed_count == total_count,
        "completed_count": completed_count,
        "total_count": total_count,
        "contexts": contexts,
    }


def review_assignments_for_context(
    db: Session,
    cycle: EvaluationCycle,
    participant: EvaluationParticipant,
    review_type: str,
    context_id: int,
) -> list[ReviewAssignment]:
    query = select(ReviewAssignment).where(
        ReviewAssignment.cycle_id == cycle.id,
        ReviewAssignment.review_type == review_type,
        ReviewAssignment.reviewer_participant_id == participant.id,
    )
    if review_type == PEER:
        team = db.get(EvaluationPeerTeamSnapshot, context_id)
        if team is None or team.cycle_id != cycle.id:
            raise HTTPException(status_code=404, detail="Peer review team not found")
        query = query.where(ReviewAssignment.context_peer_team_snapshot_id == context_id)
    else:
        team = db.get(EvaluationOrgNodeSnapshot, context_id)
        if team is None or team.cycle_id != cycle.id:
            raise HTTPException(status_code=404, detail="Manager detail team not found")
        query = query.where(ReviewAssignment.context_team_snapshot_id == context_id)
    return db.scalars(query.order_by(ReviewAssignment.sort_order, ReviewAssignment.id)).all()


def review_context_id(assignment: ReviewAssignment, review_type: str) -> int | None:
    if review_type == PEER:
        return assignment.context_peer_team_snapshot_id
    return assignment.context_team_snapshot_id


def review_context_title(assignment: ReviewAssignment, review_type: str) -> str:
    if review_type == PEER:
        return assignment.context_peer_team.name_snapshot if assignment.context_peer_team else "동료평가"
    if assignment.context_team is None:
        return "팀원평가"
    return snapshot_org_path(assignment.context_team)


def serialize_review_target(participant: EvaluationParticipant, role_label: str, db: Session) -> dict:
    return {
        "user_id": participant.id,
        "display_name": participant.display_name_snapshot,
        "email": participant.email_snapshot,
        "job_title": participant.job_title_snapshot,
        "role_label": role_label,
        "affiliation": participant_affiliation(participant, db),
    }


def target_role_label(participant: EvaluationParticipant | None) -> str:
    if participant is None:
        return ""
    labels = []
    for membership in participant.memberships:
        if membership.membership_role_snapshot == "leader":
            labels.append("LEADER")
        elif membership.membership_role_snapshot == "member":
            labels.append("MEMBER")
    if not labels:
        return ""
    return ", ".join(sorted(set(labels)))


def participant_affiliation(participant: EvaluationParticipant, db: Session) -> str:
    memberships = sorted(participant.memberships, key=lambda item: (item.sort_order, item.id))
    if not memberships:
        return "소속 부서 미지정"
    lines = []
    for membership in memberships:
        node = db.get(EvaluationOrgNodeSnapshot, membership.org_node_snapshot_id)
        if node is None:
            continue
        role = "LEADER" if membership.membership_role_snapshot == "leader" else "MEMBER"
        lines.append(f"{snapshot_org_path(node)} > {role}")
    return "\n".join(lines) if lines else "소속 부서 미지정"


def snapshot_org_path(node: EvaluationOrgNodeSnapshot) -> str:
    names = [node.name_snapshot]
    parent = node.parent
    while parent is not None:
        names.append(parent.name_snapshot)
        parent = parent.parent
    return " > ".join(reversed(names))
