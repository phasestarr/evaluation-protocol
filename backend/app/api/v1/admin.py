from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.contracts.admin import (
    EvaluationGuideIn,
    EvaluationQuestionCreateIn,
    StartCycleIn,
    WhitelistCreateIn,
)
from app.db.postgres.session import get_db
from app.services.admin import (
    add_whitelist_user,
    admin_org_tree_payload,
    delete_whitelist_user,
    list_admin_users_payload,
    list_manager_detail_question_teams_payload,
)
from app.services.authz import require_admin, require_admin_idle
from app.services.evaluations.cycles import (
    get_system_state,
    serialize_system_state,
    start_evaluation_cycle,
    stop_evaluation_cycle,
)
from app.services.evaluations.questions import (
    create_question,
    delete_question,
    evaluation_guide_content,
    list_questions,
    parse_evaluation_type,
    save_evaluation_guide,
    serialize_question,
    serialize_questions_with_effective_weights,
)
from app.services.evaluations.readiness import admin_readiness
from app.services.org_import import import_organization_csv, list_imported_users
from app.services.peer_teams import import_peer_teams_csv, list_peer_teams

router = APIRouter(prefix="/api/v1/admin")


@router.get("/evaluation-state")
def admin_evaluation_state(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return serialize_system_state(get_system_state(db))


@router.get("/readiness")
def admin_evaluation_readiness(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return admin_readiness(db)


@router.post("/evaluation-state/start")
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


@router.post("/evaluation-state/stop")
def admin_stop_evaluation_cycle(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    stop_evaluation_cycle(db)
    return serialize_system_state(get_system_state(db))


@router.get("/users")
def admin_users(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    return list_admin_users_payload(db)


@router.post("/whitelist")
def admin_add_whitelist(payload: WhitelistCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    return add_whitelist_user(db, payload.email, payload.display_name, payload.job_title, payload.system_role)


@router.delete("/whitelist/{email}")
def admin_delete_whitelist(email: str, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    delete_whitelist_user(db, email)
    return {"ok": True}


@router.get("/org/tree")
def admin_org_tree(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return admin_org_tree_payload(db)


@router.post("/org/import-csv")
def admin_import_org_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")
    result = import_organization_csv(db, file.file.read())
    result["tree"] = admin_org_tree_payload(db)
    return result


@router.get("/peer-teams")
def admin_peer_teams(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    return {"teams": list_peer_teams(db)}


@router.post("/peer-teams/import-csv")
def admin_import_peer_teams_csv(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    require_admin_idle(request, db)
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")
    return import_peer_teams_csv(db, file.file.read())


@router.get("/questions")
def admin_questions(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    return {"questions": serialize_questions_with_effective_weights(list_questions(db))}


@router.get("/questions/manager-detail/teams")
def admin_manager_detail_question_teams(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    return {"teams": list_manager_detail_question_teams_payload(db)}


@router.post("/questions")
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


@router.delete("/questions/{question_id}")
def admin_delete_question(question_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin_idle(request, db)
    delete_question(db, question_id)
    return {"ok": True}


@router.get("/evaluation-guides/{evaluation_type}")
def admin_evaluation_guide(evaluation_type: str, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    require_admin(request, db)
    parsed_type = parse_evaluation_type(evaluation_type)
    return {"evaluation_type": parsed_type, "content": evaluation_guide_content(db, parsed_type)}


@router.put("/evaluation-guides/{evaluation_type}")
def save_admin_evaluation_guide(
    evaluation_type: str,
    payload: EvaluationGuideIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    require_admin_idle(request, db)
    save_evaluation_guide(db, evaluation_type, payload.content)
    return {"ok": True}
