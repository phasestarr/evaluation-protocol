from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import MANAGER_DETAIL, PEER, SELF
from app.db.postgres.models import (
    EvaluationCycle,
    EvaluationImportUserSnapshot,
    EvaluationOrgNodeSnapshot,
    EvaluationParticipant,
    ReviewAssignment,
    ReviewScore,
    SelfReviewAnswer,
)
from app.services.evaluations.cycles import cycle_guide_content, cycle_questions, serialize_cycle
from app.services.evaluations.questions import serialize_cycle_question, serialize_cycle_questions_with_effective_weights
from app.services.evaluations.reviews import participant_affiliation, snapshot_org_path, target_role_label


def list_result_cycles_payload(db: Session) -> dict[str, list[dict]]:
    cycles = db.scalars(select(EvaluationCycle).order_by(EvaluationCycle.id.desc())).all()
    return {"cycles": [serialize_cycle_summary(cycle) for cycle in cycles]}


def cycle_result_users_payload(db: Session, cycle_id: int) -> dict:
    cycle = require_cycle(db, cycle_id)
    return {
        "cycle": serialize_cycle_summary(cycle),
        "users": cycle_result_user_rows(db, cycle),
    }


def participant_result_payload(db: Session, cycle_id: int, participant_id: int) -> dict:
    cycle = require_cycle(db, cycle_id)
    participant = db.scalar(
        select(EvaluationParticipant).where(
            EvaluationParticipant.cycle_id == cycle.id,
            EvaluationParticipant.id == participant_id,
        )
    )
    if participant is None:
        raise HTTPException(status_code=404, detail="Snapshot user not found")
    user_row = db.scalar(
        select(EvaluationImportUserSnapshot).where(
            EvaluationImportUserSnapshot.cycle_id == cycle.id,
            EvaluationImportUserSnapshot.participant_id == participant.id,
        )
    )
    if user_row is None:
        raise HTTPException(status_code=404, detail="Snapshot user row not found")
    return {
        "cycle": serialize_cycle_summary(cycle),
        "user": serialize_snapshot_user_row(user_row),
        "self_review": self_review_result_payload(db, cycle, participant),
        "peer_reviews": peer_review_result_sections(db, cycle, participant),
        "manager_detail_reviews": manager_detail_result_sections(db, cycle, participant),
    }


def require_cycle(db: Session, cycle_id: int) -> EvaluationCycle:
    cycle = db.get(EvaluationCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return cycle


def serialize_cycle_summary(cycle: EvaluationCycle) -> dict:
    data = serialize_cycle(cycle)
    data["participant_count"] = len(cycle.participants)
    return data


def cycle_result_user_rows(db: Session, cycle: EvaluationCycle) -> list[dict]:
    rows = db.scalars(
        select(EvaluationImportUserSnapshot)
        .where(EvaluationImportUserSnapshot.cycle_id == cycle.id)
        .order_by(EvaluationImportUserSnapshot.sort_order_snapshot, EvaluationImportUserSnapshot.id)
    ).all()
    return [serialize_snapshot_user_row(row) for row in rows]


def serialize_snapshot_user_row(row: EvaluationImportUserSnapshot) -> dict:
    return {
        "participant_id": row.participant_id,
        "line_number": row.sort_order_snapshot,
        "attributes": row.attributes_snapshot,
        "name": row.name_snapshot,
        "title": row.title_snapshot,
        "office_phone": row.office_phone_snapshot,
        "mobile": row.mobile_snapshot,
        "email": row.email_snapshot,
        "note": row.note_snapshot,
        "system_role": row.system_role_snapshot,
    }


def self_review_result_payload(db: Session, cycle: EvaluationCycle, participant: EvaluationParticipant) -> dict:
    questions = cycle_questions(db, cycle, SELF)
    assignment = db.scalar(
        select(ReviewAssignment).where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == SELF,
            ReviewAssignment.reviewer_participant_id == participant.id,
        )
    )
    answers_by_question_id: dict[int, str] = {}
    if assignment is not None and questions:
        answers = db.scalars(
            select(SelfReviewAnswer).where(
                SelfReviewAnswer.assignment_id == assignment.id,
                SelfReviewAnswer.cycle_question_id.in_([question.id for question in questions]),
            )
        ).all()
        answers_by_question_id = {answer.cycle_question_id: answer.answer_text for answer in answers}
    return {
        "guide_content": cycle_guide_content(db, cycle, SELF),
        "items": [
            {
                "question": serialize_cycle_question(question, effective_weight_percent=None),
                "answer_text": answers_by_question_id.get(question.id, ""),
            }
            for question in questions
        ],
    }


def peer_review_result_sections(db: Session, cycle: EvaluationCycle, participant: EvaluationParticipant) -> list[dict]:
    assignments = db.scalars(
        select(ReviewAssignment)
        .where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == PEER,
            ReviewAssignment.target_participant_id == participant.id,
            ReviewAssignment.context_peer_team_snapshot_id.is_not(None),
        )
        .order_by(ReviewAssignment.sort_order, ReviewAssignment.id)
    ).all()
    if not assignments:
        return []
    assignments_by_team: dict[int, list[ReviewAssignment]] = defaultdict(list)
    for assignment in assignments:
        if assignment.context_peer_team_snapshot_id is not None:
            assignments_by_team[assignment.context_peer_team_snapshot_id].append(assignment)

    sections: list[dict] = []
    for _, team_assignments in assignments_by_team.items():
        questions = cycle_questions(db, cycle, PEER)
        sections.extend(grouped_review_sections(db, cycle, team_assignments, questions, PEER))
    return sections


def manager_detail_result_sections(db: Session, cycle: EvaluationCycle, participant: EvaluationParticipant) -> list[dict]:
    assignments = db.scalars(
        select(ReviewAssignment)
        .where(
            ReviewAssignment.cycle_id == cycle.id,
            ReviewAssignment.review_type == MANAGER_DETAIL,
            ReviewAssignment.target_participant_id == participant.id,
            ReviewAssignment.context_team_snapshot_id.is_not(None),
        )
        .order_by(ReviewAssignment.sort_order, ReviewAssignment.id)
    ).all()
    if not assignments:
        return []
    assignments_by_team: dict[int, list[ReviewAssignment]] = defaultdict(list)
    for assignment in assignments:
        if assignment.context_team_snapshot_id is not None:
            assignments_by_team[assignment.context_team_snapshot_id].append(assignment)

    sections: list[dict] = []
    for team_snapshot_id, team_assignments in assignments_by_team.items():
        questions = cycle_questions(db, cycle, MANAGER_DETAIL, team_snapshot_id)
        sections.extend(grouped_review_sections(db, cycle, team_assignments, questions, MANAGER_DETAIL))
    return sections


def grouped_review_sections(
    db: Session,
    cycle: EvaluationCycle,
    assignments: list[ReviewAssignment],
    questions: list,
    review_type: str,
) -> list[dict]:
    if not assignments:
        return []
    assignment_ids = [assignment.id for assignment in assignments]
    question_ids = [question.id for question in questions]
    reviewer_id_by_assignment_id = {
        assignment.id: assignment.reviewer_participant_id
        for assignment in assignments
    }
    scores = db.scalars(
        select(ReviewScore).where(
            ReviewScore.assignment_id.in_(assignment_ids),
            ReviewScore.cycle_question_id.in_(question_ids),
        )
    ).all() if assignment_ids and question_ids else []
    score_by_cell = {
        f"{reviewer_id_by_assignment_id[score.assignment_id]}:{score.cycle_question_id}": score.score
        for score in scores
        if score.assignment_id in reviewer_id_by_assignment_id
    }

    first_assignment = assignments[0]
    if review_type == PEER:
        title = first_assignment.context_peer_team.name_snapshot if first_assignment.context_peer_team is not None else "동료평가"
    else:
        title = snapshot_org_path(first_assignment.context_team) if first_assignment.context_team is not None else "팀원평가"

    return [
        {
            "team": {
                "id": first_assignment.context_peer_team_snapshot_id if review_type == PEER else first_assignment.context_team_snapshot_id,
                "title": title,
            },
            "guide_content": cycle_guide_content(db, cycle, review_type),
            "questions": serialize_cycle_questions_with_effective_weights(questions),
            "reviewers": [
                serialize_result_reviewer(
                    assignment.reviewer,
                    assignment.display_role_label_snapshot if review_type == MANAGER_DETAIL else None,
                    db,
                )
                for assignment in assignments
            ],
            "scores": score_by_cell,
        }
    ]


def serialize_result_reviewer(
    participant: EvaluationParticipant | None,
    review_label: str | None,
    db: Session,
) -> dict:
    if participant is None:
        return {
            "user_id": 0,
            "display_name": "알 수 없음",
            "email": None,
            "job_title": None,
            "role_label": review_label or "",
            "affiliation": "소속 부서 미지정",
        }
    return {
        "user_id": participant.id,
        "display_name": participant.display_name_snapshot,
        "email": participant.email_snapshot,
        "job_title": participant.job_title_snapshot,
        "role_label": review_label or target_role_label(participant),
        "affiliation": participant_affiliation(participant, db),
    }
