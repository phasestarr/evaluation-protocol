from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import (
    build_authorize_url,
    build_microsoft_redirect_uri,
    create_oauth_transaction,
    ensure_aware_utc,
    exchange_code_for_token,
    find_pending_transaction,
    get_or_create_user_from_microsoft_profile,
    issue_user_session,
    resolve_microsoft_profile,
    revoke_session_key,
)
from app.config import get_settings
from app.db.postgres.models import OAuthStatus
from app.db.postgres.session import get_db
from app.schemas import AuthStatusOut
from app.services.authz import get_current_user_from_request, is_login_allowed
from app.services.users import serialize_user

router = APIRouter()
settings = get_settings()


@router.get("/api/v1/auth/microsoft/start")
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


@router.get("/api/v1/auth/callback/microsoft")
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
        return redirect_with_error(f"접근 권한이 없는 계정입니다: {email}")

    user = get_or_create_user_from_microsoft_profile(db, email, profile["display_name"])
    raw_session_key, session = issue_user_session(db, user, settings.session_ttl_minutes)

    transaction.status = OAuthStatus.completed
    transaction.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)

    response = RedirectResponse(normalize_local_redirect(transaction.redirect_after), status_code=302)
    set_session_cookie(response, raw_session_key, ensure_aware_utc(session.expires_at))
    return response


@router.get("/api/auth/me", response_model=AuthStatusOut)
def me(request: Request, db: Session = Depends(get_db)) -> AuthStatusOut:
    user = get_current_user_from_request(request, db)
    if not user:
        return AuthStatusOut(authenticated=False)
    return AuthStatusOut(authenticated=True, user=serialize_user(user))


@router.post("/api/auth/logout")
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


def redirect_with_error(message: str) -> RedirectResponse:
    separator = "&" if "?" in settings.frontend_failure_url else "?"
    url = f"{settings.frontend_failure_url}{separator}auth_error={quote(message)}"
    return RedirectResponse(url, status_code=302)


def normalize_local_redirect(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//"):
        return settings.frontend_success_url
    return value


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
