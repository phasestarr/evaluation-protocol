from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas import (
    EvaluationGuideIn,
    EvaluationQuestionCreateIn,
    OrganizationMembershipCreateIn,
    OrganizationNodeCreateIn,
    StartCycleIn,
    WhitelistCreateIn,
)
from app.auth import is_initialization_email
from app.config import get_settings
from app.constants import MANAGER_DETAIL
from app.db.postgres.models import EvaluationQuestion, OrganizationNode, OrganizationNodeType, SystemRole, User, UserWhitelist
from app.db.postgres.session import get_db
from app.services.authz import require_admin, require_admin_idle
from app.services.evaluation import (
    admin_readiness,
    create_question,
    delete_question,
    evaluation_guide_content,
    get_system_state,
    list_questions,
    parse_evaluation_type,
    save_evaluation_guide,
    serialize_question,
    serialize_questions_with_effective_weights,
    serialize_system_state,
    start_evaluation_cycle,
    stop_evaluation_cycle,
)
from app.services.organization import (
    create_membership,
    create_org_node,
    delete_membership,
    delete_org_node,
    organization_tree,
    serialize_membership,
    serialize_org_node,
)
from app.services.org_import import import_organization_csv, list_imported_users
from app.services.peer_teams import import_peer_teams_csv, list_peer_teams
from app.services.text import normalize_email, normalize_optional_text
from app.services.users import serialize_admin_user, visible_users

router = APIRouter()
settings = get_settings()


@router.get("/api/admin/evaluation-state")
def admin_evaluation_state(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return serialize_system_state(get_system_state(db))


@router.get("/api/admin/readiness")
def admin_evaluation_readiness(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return admin_readiness(db)


@router.post("/api/admin/evaluation-state/start")
def admin_start_evaluation_cycle(payload: StartCycleIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    readiness = admin_readiness(db)
    if not readiness["ready"]:
        raise HTTPException(status_code=409, detail="Evaluation setup is incomplete")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Evaluation name is required")
    cycle = start_evaluation_cycle(db, name)
    return serialize_system_state(get_system_state(db), cycle)


@router.post("/api/admin/evaluation-state/stop")
def admin_stop_evaluation_cycle(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    stop_evaluation_cycle(db)
    return serialize_system_state(get_system_state(db))


@router.get("/api/admin/users")
def admin_users(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    whitelist = db.scalars(
        select(UserWhitelist)
        .where(UserWhitelist.email != settings.initialization_email_normalized)
        .order_by(UserWhitelist.email)
    ).all()
    return {
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
        "users": [serialize_admin_user(row) for row in visible_users(db)],
    }


@router.post("/api/admin/whitelist")
def admin_add_whitelist(payload: WhitelistCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    email = normalize_email(payload.email)
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

    display_name = normalize_optional_text(payload.display_name)
    job_title = normalize_optional_text(payload.job_title)
    if display_name is not None:
        user.display_name = display_name
    if job_title is not None:
        user.job_title = job_title
    user.system_role = parse_system_role(payload.system_role)
    db.commit()
    db.refresh(row)
    db.refresh(user)
    return {"whitelist": {"id": row.id, "email": row.email}, "user": serialize_admin_user(user)}


@router.delete("/api/admin/whitelist/{email}")
def admin_delete_whitelist(email: str, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    normalized_email = normalize_email(email)
    if is_initialization_email(normalized_email, settings.initialization_email_normalized):
        raise HTTPException(status_code=400, detail="Initialization account cannot be deleted")

    row = db.scalar(select(UserWhitelist).where(UserWhitelist.email == normalized_email))
    if row is not None:
        db.delete(row)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is not None:
        db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/api/admin/users/search")
def admin_search_users(request: Request, q: str = Query(default=""), db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    query = q.strip()
    if len(query) < 1:
        return {"users": []}

    like = f"%{query}%"
    users = db.scalars(
        select(User)
        .where(
            (User.email != settings.initialization_email_normalized)
            & (
                (User.email.ilike(like))
                | (User.display_name.ilike(like))
                | (User.job_title.ilike(like))
            )
        )
        .order_by(User.display_name, User.email)
        .limit(20)
    ).all()
    return {"users": [serialize_admin_user(user) for user in users]}


@router.get("/api/admin/org/tree")
def admin_org_tree(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return serialize_admin_org_tree(db)


def serialize_admin_org_tree(db: Session) -> dict:
    nodes, memberships = organization_tree(db)
    whitelist = db.scalars(
        select(UserWhitelist)
        .where(UserWhitelist.email != settings.initialization_email_normalized)
        .order_by(UserWhitelist.email)
    ).all()
    return {
        "nodes": [serialize_org_node(node, memberships) for node in nodes],
        "users": [serialize_admin_user(user) for user in visible_users(db)],
        "imported_people": list_imported_users(db),
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
    }


@router.post("/api/admin/org/import-csv")
def admin_import_org_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")
    result = import_organization_csv(db, file.file.read())
    result["tree"] = serialize_admin_org_tree(db)
    return result


@router.get("/api/admin/peer-teams")
def admin_peer_teams(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return {"teams": list_peer_teams(db)}


@router.post("/api/admin/peer-teams/import-csv")
def admin_import_peer_teams_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")
    return import_peer_teams_csv(db, file.file.read())


@router.post("/api/admin/org/nodes")
def admin_create_org_node(payload: OrganizationNodeCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    node = create_org_node(db, payload.name, payload.node_type, payload.parent_id)
    return serialize_org_node(node, [])


@router.delete("/api/admin/org/nodes/{node_id}")
def admin_delete_org_node(node_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    delete_org_node(db, node_id)
    return {"ok": True}


@router.post("/api/admin/org/memberships")
def admin_create_org_membership(
    payload: OrganizationMembershipCreateIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    require_admin_idle(request, db)
    membership = create_membership(
        db,
        payload.organization_node_id,
        payload.membership_role,
        payload.user_id,
        payload.email,
    )
    return serialize_membership(membership)


@router.delete("/api/admin/org/memberships/{membership_id}")
def admin_delete_org_membership(membership_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    delete_membership(db, membership_id)
    return {"ok": True}


@router.get("/api/admin/questions")
def admin_questions(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    return {"questions": serialize_questions_with_effective_weights(list_questions(db))}


@router.get("/api/admin/questions/manager-detail/teams")
def admin_manager_detail_question_teams(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    return {"teams": serialize_manager_detail_question_teams(db)}


@router.post("/api/admin/questions")
def admin_create_question(payload: EvaluationQuestionCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    question = create_question(
        db,
        payload.evaluation_type,
        payload.title,
        payload.description,
        payload.weight,
        payload.organization_node_id,
    )
    return serialize_question(question, effective_weight_percent=None)


@router.delete("/api/admin/questions/{question_id}")
def admin_delete_question(question_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    delete_question(db, question_id)
    return {"ok": True}


@router.get("/api/admin/evaluation-guides/{evaluation_type}")
def admin_evaluation_guide(evaluation_type: str, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    require_admin(request, db)
    parsed_type = parse_evaluation_type(evaluation_type)
    return {"evaluation_type": parsed_type, "content": evaluation_guide_content(db, parsed_type)}


@router.put("/api/admin/evaluation-guides/{evaluation_type}")
def save_admin_evaluation_guide(
    evaluation_type: str,
    payload: EvaluationGuideIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    require_admin_idle(request, db)
    save_evaluation_guide(db, evaluation_type, payload.content)
    return {"ok": True}


def parse_system_role(value: str) -> SystemRole:
    try:
        return SystemRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid system role") from exc


def serialize_manager_detail_question_teams(db: Session) -> list[dict]:
    nodes, _ = organization_tree(db)
    node_by_id = {node.id: node for node in nodes}
    question_counts: dict[int, int] = {}
    questions = db.scalars(
        select(EvaluationQuestion).where(EvaluationQuestion.evaluation_type == MANAGER_DETAIL)
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
        }
        for team in teams
    ]


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
