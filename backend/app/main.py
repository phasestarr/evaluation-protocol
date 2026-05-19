import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.auth import (
    build_microsoft_redirect_uri,
    build_authorize_url,
    cleanup_oauth_transactions,
    cleanup_expired_sessions,
    create_oauth_transaction,
    ensure_aware_utc,
    exchange_code_for_token,
    find_pending_transaction,
    get_or_create_user_from_microsoft_profile,
    get_user_by_session_key,
    is_email_whitelisted,
    is_initialization_email,
    issue_user_session,
    revoke_session_key,
    resolve_microsoft_profile,
    seed_initialization_user,
)
from app.config import get_settings
from app.db.postgres.migrations import run_database_migrations
from app.db.postgres.models import (
    EvaluationGuide,
    EvaluationQuestion,
    OAuthStatus,
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
    PeerReviewScore,
    SelfReviewAnswer,
    SystemRole,
    User,
    UserWhitelist,
)
from app.db.postgres.session import SessionLocal, get_db
from app.schemas import AuthStatusOut, CurrentUserOut, OrganizationNodeOut

settings = get_settings()
SELF_REVIEW = "self_review"
PEER_REVIEW = "peer_review"
DIRECT_REPORT_REVIEW = "direct_report_review"
EVALUATION_TYPES = {SELF_REVIEW, PEER_REVIEW, DIRECT_REPORT_REVIEW}
WEIGHTED_EVALUATION_TYPES = {PEER_REVIEW, DIRECT_REPORT_REVIEW}


class WhitelistCreateIn(BaseModel):
    email: str
    job_title: str | None = None
    display_name: str | None = None
    system_role: str = "user"


class OrganizationNodeCreateIn(BaseModel):
    name: str
    node_type: str
    parent_id: int | None = None


class OrganizationMembershipCreateIn(BaseModel):
    email: str | None = None
    user_id: int | None = None
    organization_node_id: int
    membership_role: str = "member"


class EvaluationQuestionCreateIn(BaseModel):
    evaluation_type: str
    title: str
    description: str | None = None
    weight: int | None = None


class EvaluationGuideIn(BaseModel):
    content: str


class SelfReviewAnswerIn(BaseModel):
    answer_text: str


class PeerReviewScoreIn(BaseModel):
    target_user_id: int
    question_id: int
    score: int


class PeerReviewScoresIn(BaseModel):
    scores: list[PeerReviewScoreIn]


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_database_migrations()
    with SessionLocal() as db:
        seed_initialization_user(db, settings.initialization_email_normalized)
        seed_root_organization(db)
        cleanup_expired_sessions(db)
        cleanup_oauth_transactions(db)
    cleanup_task = asyncio.create_task(session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Evaluation Protocol API", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/auth/microsoft/start")
def start_microsoft_login(
    request: Request,
    redirect_after: str = Query(default="/"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        return redirect_with_error("Microsoft OAuth 설정이 아직 완료되지 않았습니다.")

    transaction = create_oauth_transaction(db, redirect_after=normalize_local_redirect(redirect_after))
    redirect_uri = build_microsoft_redirect_uri(settings, request)
    return RedirectResponse(build_authorize_url(settings, transaction, redirect_uri), status_code=302)


@app.get("/api/v1/auth/callback/microsoft")
async def microsoft_callback(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return redirect_with_error(error_description or error)
    if not state or not code:
        return redirect_with_error("OAuth 응답에 필요한 state 또는 code가 없습니다.")

    transaction = find_pending_transaction(db, state)
    if not transaction:
        return redirect_with_error("로그인 요청을 확인할 수 없습니다. 다시 시도해 주세요.")
    expires_at = ensure_aware_utc(transaction.expires_at)
    if expires_at < datetime.now(UTC):
        transaction.status = OAuthStatus.expired
        transaction.failure_reason = "OAuth transaction expired"
        db.commit()
        return redirect_with_error("로그인 요청이 만료되었습니다. 다시 시도해 주세요.")

    try:
        redirect_uri = build_microsoft_redirect_uri(settings, request)
        token_payload = await exchange_code_for_token(settings, code, redirect_uri)
        profile = await resolve_microsoft_profile(token_payload)
    except Exception as exc:
        transaction.status = OAuthStatus.failed
        transaction.failure_reason = str(exc)
        db.commit()
        return redirect_with_error("Microsoft 로그인 처리 중 오류가 발생했습니다.")

    email = profile["email"]
    transaction.email = email
    if not email:
        transaction.status = OAuthStatus.denied
        transaction.failure_reason = "Email claim was missing"
        db.commit()
        return redirect_with_error("Microsoft 계정에서 메일 주소를 확인할 수 없습니다.")

    if not is_login_allowed(db, email):
        transaction.status = OAuthStatus.denied
        transaction.failure_reason = f"{email} is not whitelisted"
        db.commit()
        return redirect_with_error(f"{email} 계정은 이 시스템 접근 화이트리스트에 없습니다.")

    user = get_or_create_user_from_microsoft_profile(db, email, profile["display_name"])
    raw_session_key, session = issue_user_session(db, user, settings.session_ttl_minutes)

    transaction.status = OAuthStatus.completed
    transaction.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)

    response = RedirectResponse(normalize_local_redirect(transaction.redirect_after), status_code=302)
    set_session_cookie(response, raw_session_key, ensure_aware_utc(session.expires_at))
    return response


@app.get("/api/auth/me", response_model=AuthStatusOut)
def me(request: Request, db: Session = Depends(get_db)) -> AuthStatusOut:
    user = get_current_user_from_request(request, db)
    if not user:
        return AuthStatusOut(authenticated=False)
    return AuthStatusOut(authenticated=True, user=serialize_user(user))


@app.post("/api/auth/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    revoke_session_key(db, request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return {"ok": True}


@app.get("/api/admin/users")
def admin_users(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    whitelist = db.scalars(
        select(UserWhitelist)
        .where(UserWhitelist.email != settings.initialization_email_normalized)
        .order_by(UserWhitelist.email)
    ).all()
    users = db.scalars(
        select(User)
        .where(User.email != settings.initialization_email_normalized)
        .order_by(User.email)
    ).all()
    return {
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
        "users": [serialize_admin_user(row) for row in users],
    }


@app.post("/api/admin/whitelist")
def admin_add_whitelist(payload: WhitelistCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
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


@app.delete("/api/admin/whitelist/{email}")
def admin_delete_whitelist(email: str, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin(request, db)
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


@app.get("/api/admin/users/search")
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


@app.get("/api/admin/org/tree")
def admin_org_tree(request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    seed_root_organization(db)
    nodes = db.scalars(select(OrganizationNode).order_by(OrganizationNode.id)).all()
    memberships = db.scalars(select(OrganizationMembership).order_by(OrganizationMembership.id)).all()
    whitelist = db.scalars(
        select(UserWhitelist)
        .where(UserWhitelist.email != settings.initialization_email_normalized)
        .order_by(UserWhitelist.email)
    ).all()
    return {
        "nodes": [serialize_org_node(node, memberships) for node in nodes],
        "users": [
            serialize_admin_user(user)
            for user in db.scalars(
                select(User)
                .where(User.email != settings.initialization_email_normalized)
                .order_by(User.email)
            ).all()
        ],
        "whitelist": [
            {"id": row.id, "email": row.email, "created_at": row.created_at.isoformat() if row.created_at else None}
            for row in whitelist
        ],
    }


@app.post("/api/admin/org/nodes")
def admin_create_org_node(payload: OrganizationNodeCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    node_type = parse_node_type(payload.node_type)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    if node_type != OrganizationNodeType.company and payload.parent_id is None:
        raise HTTPException(status_code=400, detail="Head and team nodes require a parent")

    parent = db.get(OrganizationNode, payload.parent_id) if payload.parent_id is not None else None
    if payload.parent_id is not None and parent is None:
        raise HTTPException(status_code=404, detail="Parent node not found")
    if node_type == OrganizationNodeType.head and parent and parent.node_type != OrganizationNodeType.company:
        raise HTTPException(status_code=400, detail="Head nodes must be created under a company")
    if node_type == OrganizationNodeType.team and parent and parent.node_type != OrganizationNodeType.head:
        raise HTTPException(status_code=400, detail="Team nodes must be created under a head")

    node = OrganizationNode(name=name, node_type=node_type, parent_id=payload.parent_id)
    db.add(node)
    db.commit()
    db.refresh(node)
    return serialize_org_node(node, [])


@app.delete("/api/admin/org/nodes/{node_id}")
def admin_delete_org_node(node_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin(request, db)
    node = db.get(OrganizationNode, node_id)
    if node is None:
        return {"ok": True}
    if is_seed_root_node(node):
        raise HTTPException(status_code=400, detail="NEXTIN root node cannot be deleted")

    subtree_ids = collect_subtree_node_ids(db, node_id)
    db.execute(update(User).where(User.organization_node_id.in_(subtree_ids)).values(organization_node_id=None))
    db.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_node_id.in_(subtree_ids)))

    nodes = db.scalars(select(OrganizationNode).where(OrganizationNode.id.in_(subtree_ids))).all()
    for row in sorted(nodes, key=lambda item: item.id, reverse=True):
        db.delete(row)
    db.commit()
    return {"ok": True}


@app.post("/api/admin/org/memberships")
def admin_create_org_membership(
    payload: OrganizationMembershipCreateIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    require_admin(request, db)
    node = db.get(OrganizationNode, payload.organization_node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Organization node not found")

    role = parse_membership_role(payload.membership_role)
    user = resolve_membership_user(db, payload)

    if user.organization_node_id is None:
        user.organization_node_id = node.id

    existing_membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_node_id == node.id,
            OrganizationMembership.membership_role == role,
        )
    )
    if existing_membership is not None:
        return serialize_membership(existing_membership)

    membership = OrganizationMembership(user_id=user.id, organization_node_id=node.id, membership_role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return serialize_membership(membership)


@app.delete("/api/admin/org/memberships/{membership_id}")
def admin_delete_org_membership(membership_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin(request, db)
    membership = db.get(OrganizationMembership, membership_id)
    if membership is not None:
        db.delete(membership)
        db.commit()
    return {"ok": True}


@app.get("/api/admin/questions")
def admin_questions(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    require_admin(request, db)
    questions = db.scalars(
        select(EvaluationQuestion).order_by(EvaluationQuestion.evaluation_type, EvaluationQuestion.sort_order, EvaluationQuestion.id)
    ).all()
    return {"questions": serialize_questions_with_effective_weights(questions)}


@app.post("/api/admin/questions")
def admin_create_question(payload: EvaluationQuestionCreateIn, request: Request, db: Session = Depends(get_db)) -> dict:
    require_admin(request, db)
    evaluation_type = parse_evaluation_type(payload.evaluation_type)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Question title is required")

    weight = None
    if evaluation_type in WEIGHTED_EVALUATION_TYPES:
        if payload.weight is None or payload.weight <= 0:
            raise HTTPException(status_code=400, detail="Question weight must be greater than zero")
        weight = payload.weight

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
        description=normalize_optional_text(payload.description),
        weight=weight,
        sort_order=next_sort_order,
        is_active=True,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return serialize_question(question, effective_weight_percent=None)


@app.delete("/api/admin/questions/{question_id}")
def admin_delete_question(question_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    require_admin(request, db)
    question = db.get(EvaluationQuestion, question_id)
    if question is not None:
        db.delete(question)
        db.commit()
    return {"ok": True}


@app.get("/api/admin/evaluation-guides/{evaluation_type}")
def admin_evaluation_guide(evaluation_type: str, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    require_admin(request, db)
    parsed_type = parse_evaluation_type(evaluation_type)
    return {"evaluation_type": parsed_type, "content": evaluation_guide_content(db, parsed_type)}


@app.put("/api/admin/evaluation-guides/{evaluation_type}")
def save_admin_evaluation_guide(
    evaluation_type: str,
    payload: EvaluationGuideIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    require_admin(request, db)
    parsed_type = parse_evaluation_type(evaluation_type)
    guide = db.scalar(select(EvaluationGuide).where(EvaluationGuide.evaluation_type == parsed_type))
    if guide is None:
        guide = EvaluationGuide(evaluation_type=parsed_type, content=payload.content)
        db.add(guide)
    else:
        guide.content = payload.content
    db.commit()
    return {"ok": True}


@app.get("/api/evaluations/self")
def self_review(request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    questions = active_questions(db, SELF_REVIEW)
    answers = db.scalars(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.user_id == user.id,
            SelfReviewAnswer.question_id.in_([question.id for question in questions]),
        )
    ).all()
    answer_by_question_id = {answer.question_id: answer.answer_text for answer in answers}
    return {
        "guide_content": evaluation_guide_content(db, SELF_REVIEW),
        "questions": [serialize_question(question, effective_weight_percent=None) for question in questions],
        "answers": answer_by_question_id,
    }


@app.put("/api/evaluations/self/answers/{question_id}")
def save_self_review_answer(
    question_id: int,
    payload: SelfReviewAnswerIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    answer_text = payload.answer_text.strip()
    if len(answer_text) > 1000:
        raise HTTPException(status_code=400, detail="Answer must be 1000 characters or fewer")
    question = db.get(EvaluationQuestion, question_id)
    if question is None or question.evaluation_type != SELF_REVIEW or not question.is_active:
        raise HTTPException(status_code=404, detail="Self review question not found")

    answer = db.scalar(
        select(SelfReviewAnswer).where(
            SelfReviewAnswer.user_id == user.id,
            SelfReviewAnswer.question_id == question.id,
        )
    )
    if answer is None:
        answer = SelfReviewAnswer(user_id=user.id, question_id=question.id, answer_text=answer_text)
        db.add(answer)
    else:
        answer.answer_text = answer_text
    db.commit()
    return {"ok": True}


@app.get("/api/evaluations/team-contexts")
def team_review_contexts(request: Request, db: Session = Depends(get_db)) -> dict[str, list[dict]]:
    user = require_user(request, db)
    contexts = unique_team_memberships(user)
    return {"contexts": [serialize_team_context(membership) for membership in contexts]}


@app.get("/api/evaluations/team/{team_node_id}")
def team_review(team_node_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    user = require_user(request, db)
    team = require_reviewable_team(user, team_node_id, db)
    questions = active_questions(db, PEER_REVIEW)
    targets = team_review_targets(user, team, db)
    scores = db.scalars(
        select(PeerReviewScore).where(
            PeerReviewScore.reviewer_user_id == user.id,
            PeerReviewScore.team_node_id == team.id,
            PeerReviewScore.target_user_id.in_([target["user_id"] for target in targets] or [-1]),
            PeerReviewScore.question_id.in_([question.id for question in questions] or [-1]),
        )
    ).all()
    score_by_cell = {
        f"{score.target_user_id}:{score.question_id}": score.score
        for score in scores
    }
    return {
        "team": serialize_team_node(team),
        "guide_content": evaluation_guide_content(db, PEER_REVIEW),
        "questions": serialize_questions_with_effective_weights(questions),
        "targets": targets,
        "scores": score_by_cell,
    }


@app.put("/api/evaluations/team/{team_node_id}/scores")
def save_team_review_scores(
    team_node_id: int,
    payload: PeerReviewScoresIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = require_user(request, db)
    team = require_reviewable_team(user, team_node_id, db)
    allowed_question_ids = {question.id for question in active_questions(db, PEER_REVIEW)}
    allowed_target_ids = {target["user_id"] for target in team_review_targets(user, team, db)}

    for row in payload.scores:
        if row.question_id not in allowed_question_ids:
            raise HTTPException(status_code=400, detail="Invalid question")
        if row.target_user_id not in allowed_target_ids:
            raise HTTPException(status_code=400, detail="Invalid target")
        if row.score < 0 or row.score > 100:
            raise HTTPException(status_code=400, detail="Score must be between 0 and 100")

        score = db.scalar(
            select(PeerReviewScore).where(
                PeerReviewScore.reviewer_user_id == user.id,
                PeerReviewScore.team_node_id == team.id,
                PeerReviewScore.target_user_id == row.target_user_id,
                PeerReviewScore.question_id == row.question_id,
            )
        )
        if score is None:
            score = PeerReviewScore(
                reviewer_user_id=user.id,
                team_node_id=team.id,
                target_user_id=row.target_user_id,
                question_id=row.question_id,
                score=row.score,
            )
            db.add(score)
        else:
            score.score = row.score
    db.commit()
    return {"ok": True}


def get_current_user_from_request(request: Request, db: Session) -> User | None:
    return get_user_by_session_key(db, request.cookies.get(settings.session_cookie_name))


def require_admin(request: Request, db: Session) -> User:
    user = get_current_user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.system_role != SystemRole.admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_user(request: Request, db: Session) -> User:
    user = get_current_user_from_request(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def serialize_user(user: User) -> CurrentUserOut:
    organization_node = None
    if user.organization_node:
        organization_node = OrganizationNodeOut(
            id=user.organization_node.id,
            name=user.organization_node.name,
            node_type=user.organization_node.node_type.value,
        )
    return CurrentUserOut(
        email=user.email,
        display_name=user.display_name,
        job_title=user.job_title,
        system_role=user.system_role.value,
        has_leader_membership=has_leader_membership(user),
        organization_affiliation=format_user_affiliation(user),
        organization_node=organization_node,
    )


def serialize_admin_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "job_title": user.job_title,
        "system_role": user.system_role.value,
        "organization_node_id": user.organization_node_id,
    }


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


def evaluation_guide_content(db: Session, evaluation_type: str) -> str:
    guide = db.scalar(select(EvaluationGuide).where(EvaluationGuide.evaluation_type == evaluation_type))
    return guide.content if guide else ""


def active_questions(db: Session, evaluation_type: str) -> list[EvaluationQuestion]:
    return db.scalars(
        select(EvaluationQuestion)
        .where(
            EvaluationQuestion.evaluation_type == evaluation_type,
            EvaluationQuestion.is_active.is_(True),
        )
        .order_by(EvaluationQuestion.sort_order, EvaluationQuestion.id)
    ).all()


def serialize_team_context(membership: OrganizationMembership) -> dict:
    team = membership.organization_node
    return {
        "team_node_id": team.id,
        "title": ">".join(organization_path_segments(team)),
        "role_label": membership_role_display(membership),
    }


def serialize_team_node(team: OrganizationNode) -> dict:
    return {
        "id": team.id,
        "title": ">".join(organization_path_segments(team)),
    }


def unique_team_memberships(user: User) -> list[OrganizationMembership]:
    memberships = sorted(
        (
            membership
            for membership in user.memberships
            if membership.organization_node is not None
            and membership.organization_node.node_type == OrganizationNodeType.team
        ),
        key=membership_affiliation_sort_key,
    )
    seen_team_ids: set[int] = set()
    result: list[OrganizationMembership] = []
    for membership in memberships:
        if membership.organization_node_id in seen_team_ids:
            continue
        seen_team_ids.add(membership.organization_node_id)
        result.append(membership)
    return result


def require_reviewable_team(user: User, team_node_id: int, db: Session) -> OrganizationNode:
    team = db.get(OrganizationNode, team_node_id)
    if team is None or team.node_type != OrganizationNodeType.team:
        raise HTTPException(status_code=404, detail="Team not found")
    if all(membership.organization_node_id != team.id for membership in unique_team_memberships(user)):
        raise HTTPException(status_code=403, detail="Team review is not available for this user")
    return team


def team_review_targets(user: User, team: OrganizationNode, db: Session) -> list[dict]:
    node_ids = [team.id]
    if team.parent_id is not None:
        node_ids.insert(0, team.parent_id)

    memberships = db.scalars(
        select(OrganizationMembership)
        .where(OrganizationMembership.organization_node_id.in_(node_ids))
        .order_by(OrganizationMembership.id)
    ).all()
    memberships = sorted(memberships, key=membership_affiliation_sort_key)
    seen_user_ids: set[int] = set()
    targets: list[dict] = []
    for membership in memberships:
        if membership.user_id in seen_user_ids:
            continue
        seen_user_ids.add(membership.user_id)
        targets.append(
            {
                "user_id": membership.user_id,
                "display_name": membership.user.display_name if membership.user else None,
                "email": membership.user.email if membership.user else None,
                "job_title": membership.user.job_title if membership.user else None,
                "role_label": membership_role_display(membership),
                "affiliation": ">".join(organization_path_segments(membership.organization_node)),
            }
        )
    return targets


def membership_role_display(membership: OrganizationMembership) -> str:
    if membership.membership_role == OrganizationMembershipRole.member:
        return "팀원"
    node = membership.organization_node
    if node.node_type == OrganizationNodeType.head:
        return "본부장"
    if node.node_type == OrganizationNodeType.team:
        return "팀장"
    return "관리자"


def has_leader_membership(user: User) -> bool:
    return any(membership.membership_role == OrganizationMembershipRole.leader for membership in user.memberships)


def format_user_affiliation(user: User) -> str:
    memberships = sorted(
        (membership for membership in user.memberships if membership.organization_node is not None),
        key=membership_affiliation_sort_key,
    )
    lines = [format_membership_affiliation(membership, user) for membership in memberships]
    if not lines:
        return "소속 부서 미지정"
    return "\n".join(lines)


def membership_affiliation_sort_key(membership: OrganizationMembership) -> tuple[list[int], int, int]:
    role_priority = 0 if membership.membership_role == OrganizationMembershipRole.leader else 1
    return organization_path_ids(membership.organization_node), role_priority, membership.id


def format_membership_affiliation(membership: OrganizationMembership, user: User) -> str:
    node = membership.organization_node
    segments = organization_path_segments(node)
    display_name = user.display_name or user.email
    if membership.membership_role == OrganizationMembershipRole.leader:
        if node.node_type == OrganizationNodeType.head:
            role_text = "본부장"
        elif node.node_type == OrganizationNodeType.team:
            role_text = "팀장"
        else:
            role_text = "관리자"
        role_text = f"{role_text} {display_name}"
    else:
        role_text = f"팀원 {display_name}"
    return ">".join([*segments, role_text])


def organization_path_segments(node: OrganizationNode) -> list[str]:
    segments: list[str] = []
    cursor: OrganizationNode | None = node
    while cursor is not None:
        segments.append(cursor.name)
        cursor = cursor.parent
    return list(reversed(segments))


def organization_path_ids(node: OrganizationNode) -> list[int]:
    ids: list[int] = []
    cursor: OrganizationNode | None = node
    while cursor is not None:
        ids.append(cursor.id)
        cursor = cursor.parent
    return list(reversed(ids))


def redirect_with_error(message: str) -> RedirectResponse:
    separator = "&" if "?" in settings.frontend_failure_url else "?"
    url = f"{settings.frontend_failure_url}{separator}auth_error={quote(message)}"
    return RedirectResponse(url, status_code=302)


def normalize_local_redirect(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return settings.frontend_success_url
    return value


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def is_login_allowed(db: Session, email: str) -> bool:
    return is_initialization_email(email, settings.initialization_email_normalized) or is_email_whitelisted(db, email)


def resolve_membership_user(db: Session, payload: OrganizationMembershipCreateIn) -> User:
    if payload.user_id is not None:
        user = db.get(User, payload.user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not is_login_allowed(db, user.email):
            raise HTTPException(status_code=400, detail="User must be whitelisted first")
        return user

    email = normalize_email(payload.email or "")
    if not email:
        raise HTTPException(status_code=400, detail="User selection is required")

    if not is_login_allowed(db, email):
        raise HTTPException(status_code=400, detail="Email must be whitelisted first")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.flush()
    return user


def parse_node_type(value: str) -> OrganizationNodeType:
    try:
        return OrganizationNodeType(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid organization node type") from exc


def parse_system_role(value: str) -> SystemRole:
    try:
        return SystemRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid system role") from exc


def parse_evaluation_type(value: str) -> str:
    if value not in EVALUATION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid evaluation type")
    return value


def parse_membership_role(value: str) -> OrganizationMembershipRole:
    try:
        return OrganizationMembershipRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid membership role") from exc


def is_seed_root_node(node: OrganizationNode) -> bool:
    return node.node_type == OrganizationNodeType.company and node.parent_id is None and node.name == "NEXTIN"


def collect_subtree_node_ids(db: Session, root_id: int) -> list[int]:
    ids = [root_id]
    cursor = 0
    while cursor < len(ids):
        child_ids = db.scalars(select(OrganizationNode.id).where(OrganizationNode.parent_id == ids[cursor])).all()
        ids.extend(child_ids)
        cursor += 1
    return ids


def set_session_cookie(response: RedirectResponse, raw_session_key: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_session_key,
        expires=expires_at,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


async def session_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.session_cleanup_interval_minutes * 60)
        with SessionLocal() as db:
            cleanup_expired_sessions(db)
            cleanup_oauth_transactions(db)


def seed_root_organization(db: Session) -> None:
    from sqlalchemy import select

    root = db.scalar(
        select(OrganizationNode).where(
            OrganizationNode.node_type == OrganizationNodeType.company,
            OrganizationNode.parent_id.is_(None),
            OrganizationNode.name == "NEXTIN",
        )
    )
    if root is None:
        db.add(OrganizationNode(name="NEXTIN", node_type=OrganizationNodeType.company))
        db.commit()
