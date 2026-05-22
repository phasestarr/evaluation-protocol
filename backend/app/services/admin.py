from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import MANAGER_DETAIL
from app.db.postgres.models import EvaluationQuestion, OrganizationMembership, OrganizationNode, OrganizationNodeType, SystemRole, User, UserWhitelist
from app.services.auth import is_initialization_email
from app.services.evaluations.questions import evaluation_guide_content
from app.services.organization import organization_tree
from app.services.org_import import list_imported_users
from app.services.text import normalize_email, normalize_optional_text
from app.services.users import serialize_admin_user, visible_users

settings = get_settings()


def list_admin_users_payload(db: Session) -> dict[str, list[dict]]:
    whitelist = list_whitelist_entries(db)
    return {
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
        "users": [serialize_admin_user(row) for row in visible_users(db)],
    }


def add_whitelist_user(
    db: Session,
    email_value: str,
    display_name_value: str | None,
    job_title_value: str | None,
    system_role_value: str,
) -> dict:
    email = normalize_email(email_value)
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if is_initialization_email(email, settings.initialization_email_normalized):
        raise HTTPException(status_code=400, detail="Initialization account is managed by env")

    row = db.scalar(select(UserWhitelist).where(UserWhitelist.email == email))
    if row is None:
        row = UserWhitelist(email=email)
        db.add(row)

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()

    display_name = normalize_optional_text(display_name_value)
    job_title = normalize_optional_text(job_title_value)
    if display_name is not None:
        user.display_name = display_name
    if job_title is not None:
        user.job_title = job_title
    user.system_role = parse_system_role(system_role_value)
    db.commit()
    db.refresh(row)
    db.refresh(user)
    return {"whitelist": {"id": row.id, "email": row.email}, "user": serialize_admin_user(user)}


def delete_whitelist_user(db: Session, email_value: str) -> None:
    normalized_email = normalize_email(email_value)
    if is_initialization_email(normalized_email, settings.initialization_email_normalized):
        raise HTTPException(status_code=400, detail="Initialization account cannot be deleted")

    row = db.scalar(select(UserWhitelist).where(UserWhitelist.email == normalized_email))
    if row is not None:
        db.delete(row)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is not None:
        db.delete(user)
    db.commit()


def admin_org_tree_payload(db: Session) -> dict:
    nodes, memberships = organization_tree(db)
    whitelist = list_whitelist_entries(db)
    return {
        "nodes": [serialize_org_node(node, memberships) for node in nodes],
        "users": [serialize_admin_user(user) for user in visible_users(db)],
        "imported_people": list_imported_users(db),
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
    }


def list_manager_detail_question_teams_payload(db: Session) -> list[dict]:
    nodes, _ = organization_tree(db)
    node_by_id = {node.id: node for node in nodes}
    question_counts: dict[int, int] = {}
    guide_complete = bool(evaluation_guide_content(db, MANAGER_DETAIL).strip())
    questions = db.scalars(
        select(EvaluationQuestion).where(
            EvaluationQuestion.evaluation_type == MANAGER_DETAIL,
            EvaluationQuestion.is_active.is_(True),
        )
    ).all()
    for question in questions:
        if question.organization_node_id is not None:
            question_counts[question.organization_node_id] = question_counts.get(question.organization_node_id, 0) + 1

    teams = [node for node in nodes if node.node_type == OrganizationNodeType.team]
    return [
        {
            "id": team.id,
            "name": team.name,
            "parent_id": team.parent_id,
            "path": organization_node_path(team, node_by_id),
            "question_count": question_counts.get(team.id, 0),
            "complete": guide_complete and manager_detail_team_questions_complete(team.id, questions),
        }
        for team in teams
    ]


def parse_system_role(value: str) -> SystemRole:
    try:
        return SystemRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid system role") from exc


def list_whitelist_entries(db: Session) -> list[UserWhitelist]:
    return db.scalars(
        select(UserWhitelist)
        .where(UserWhitelist.email != settings.initialization_email_normalized)
        .order_by(UserWhitelist.email)
    ).all()


def serialize_org_node(node: OrganizationNode, memberships: list[OrganizationMembership]) -> dict:
    return {
        "id": node.id,
        "name": node.name,
        "node_type": node.node_type.value,
        "parent_id": node.parent_id,
        "memberships": [
            serialize_membership(membership)
            for membership in memberships
            if membership.organization_node_id == node.id
        ],
    }


def serialize_membership(membership: OrganizationMembership) -> dict:
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "email": membership.user.email if membership.user else None,
        "display_name": membership.user.display_name if membership.user else None,
        "job_title": membership.user.job_title if membership.user else None,
        "organization_node_id": membership.organization_node_id,
        "membership_role": membership.membership_role.value,
    }


def manager_detail_team_questions_complete(team_id: int, questions: list[EvaluationQuestion]) -> bool:
    team_questions = [
        question
        for question in questions
        if question.organization_node_id == team_id and question.is_active
    ]
    return bool(team_questions)


def organization_node_path(node: OrganizationNode, node_by_id: dict[int, OrganizationNode]) -> str:
    names = [node.name]
    parent_id = node.parent_id
    while parent_id is not None:
        parent = node_by_id.get(parent_id)
        if parent is None:
            break
        names.append(parent.name)
        parent_id = parent.parent_id
    return " > ".join(reversed(names))
