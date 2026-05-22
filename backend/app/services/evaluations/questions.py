from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import EVALUATION_TYPES, MANAGER_DETAIL, WEIGHTED_EVALUATION_TYPES
from app.db.postgres.models import EvaluationCycleQuestion, EvaluationGuide, EvaluationQuestion, OrganizationNode, OrganizationNodeType
from app.services.text import normalize_optional_text


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
