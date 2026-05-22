from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.contracts.evaluations import ReviewScoresIn, SelfReviewAnswerIn
from app.constants import MANAGER_DETAIL
from app.db.postgres.session import get_db
from app.services.authz import require_user
from app.services.evaluations.cycles import (
    require_cycle_participant,
    require_running_cycle,
)
from app.services.evaluations.reviews import (
    evaluation_progress_payload,
    manager_detail_contexts_payload,
    manager_detail_review_payload,
    peer_review_contexts_payload,
    peer_review_payload,
    save_manager_detail_scores_for_participant,
    save_peer_review_scores_for_participant,
    save_self_review_answer_for_participant,
    self_review_payload,
)

router = APIRouter(prefix="/api/v1/evaluations")


@router.get("/self")
def self_review(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return self_review_payload(db, cycle, participant)


@router.put("/self/answers/{question_id}")
def save_self_review_answer(
    question_id: int,
    payload: SelfReviewAnswerIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    answer_text = payload.answer_text.strip()
    if len(answer_text) > 1000:
        raise HTTPException(status_code=400, detail="Answer must be 1000 characters or fewer")
    save_self_review_answer_for_participant(db, cycle, participant, question_id, answer_text)
    return {"ok": True}


@router.get("/progress")
def evaluation_progress(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return evaluation_progress_payload(db, cycle, participant)


@router.get("/peer-contexts")
def peer_review_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return peer_review_contexts_payload(db, cycle, participant)


@router.get("/peer/{team_node_id}")
def peer_review(team_node_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return peer_review_payload(db, cycle, participant, team_node_id)


@router.put("/peer/{team_node_id}/scores")
def save_peer_review_scores(
    team_node_id: int,
    payload: ReviewScoresIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    save_peer_review_scores_for_participant(
        db,
        cycle,
        participant,
        team_node_id,
        [(score.target_user_id, score.question_id, score.score) for score in payload.scores],
    )
    return {"ok": True}


@router.get("/manager-detail-contexts")
def manager_detail_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return manager_detail_contexts_payload(db, cycle, participant)


@router.get("/manager-detail/{team_node_id}/targets/{target_user_id}")
def manager_detail_target_review(
    team_node_id: int,
    target_user_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    return manager_detail_review_payload(db, cycle, participant, team_node_id, target_user_id)


@router.put("/manager-detail/{team_node_id}/scores")
def save_manager_detail_scores(
    team_node_id: int,
    payload: ReviewScoresIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    cycle = require_running_cycle(db)
    participant = require_cycle_participant(db, cycle, user)
    save_manager_detail_scores_for_participant(
        db,
        cycle,
        participant,
        team_node_id,
        [(score.target_user_id, score.question_id, score.score) for score in payload.scores],
    )
    return {"ok": True}
