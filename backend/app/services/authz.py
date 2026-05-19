from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import get_user_by_session_key, is_email_whitelisted, is_initialization_email
from app.config import get_settings
from app.constants import SYSTEM_IDLE
from app.db.postgres.models import SystemRole, User
from app.services.evaluation import get_system_state

settings = get_settings()


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


def require_admin_idle(request: Request, db: Session) -> User:
    user = require_admin(request, db)
    if get_system_state(db).status != SYSTEM_IDLE:
        raise HTTPException(status_code=409, detail="Evaluation is running; administration is locked")
    return user


def is_login_allowed(db: Session, email: str) -> bool:
    return is_initialization_email(email, settings.initialization_email_normalized) or is_email_whitelisted(db, email)
