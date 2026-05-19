from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas import ReviewScoresIn, SelfReviewAnswerIn
from app.constants import PEER, SELF
from app.db.postgres.models import EvaluationCycleQuestion, ReviewScore, SelfReviewAnswer
from app.db.postgres.session import get_db
from app.services.authz import require_user
from app.services.evaluation import (
    cycle_guide_content,
    cycle_questions,
    peer_assignments_for_reviewer,
    peer_assignments_for_team,
    require_cycle_participant,
    require_cycle_team_context,
    require_running_cycle,
    save_review_score,
    save_self_answer,
    self_assignment,
    serialize_assignment_target,
    serialize_cycle_question,
    serialize_cycle_questions_with_effective_weights,
    serialize_peer_contexts,
    serialize_snapshot_team_node,
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


@router.get("/api/evaluations/peer-contexts")
def peer_review_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    assignments = peer_assignments_for_reviewer(db, cycle, participant)
    return {"contexts": serialize_peer_contexts(assignments)}


@router.get("/api/evaluations/peer/{team_node_id}")
def peer_review(team_node_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    team = require_cycle_team_context(db, cycle, team_node_id)
    assignments = peer_assignments_for_team(db, cycle, participant, team)
    questions = cycle_questions(db, cycle, PEER)
    scores = db.scalars(
        select(ReviewScore).where(
            ReviewScore.assignment_id.in_([assignment.id for assignment in assignments] or [-1]),
            ReviewScore.cycle_question_id.in_([question.id for question in questions] or [-1]),
        )
    ).all()
    assignment_by_id = {assignment.id: assignment for assignment in assignments}
    score_by_cell = {
        f"{assignment_by_id[score.assignment_id].target_participant_id}:{score.cycle_question_id}": score.score
        for score in scores
        if score.assignment_id in assignment_by_id
    }
    return {
        "team": serialize_snapshot_team_node(team),
        "guide_content": cycle_guide_content(db, cycle, PEER),
        "questions": serialize_cycle_questions_with_effective_weights(questions),
        "targets": [serialize_assignment_target(assignment) for assignment in assignments],
        "scores": score_by_cell,
    }


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
    team = require_cycle_team_context(db, cycle, team_node_id)
    allowed_question_ids = {question.id for question in cycle_questions(db, cycle, PEER)}
    assignments = peer_assignments_for_team(db, cycle, participant, team)
    assignment_by_target_id = {assignment.target_participant_id: assignment for assignment in assignments}

    for row in payload.scores:
        if row.question_id not in allowed_question_ids:
            raise HTTPException(status_code=400, detail="Invalid question")
        assignment = assignment_by_target_id.get(row.target_user_id)
        if assignment is None:
            raise HTTPException(status_code=400, detail="Invalid target")
        if row.score < 0 or row.score > 100:
            raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
        save_review_score(db, assignment, row.question_id, row.score)

    db.commit()
    return {"ok": True}
