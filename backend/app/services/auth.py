import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.postgres.models import OAuthStatus, OAuthTransaction, SystemRole, User, UserSession, UserWhitelist


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_oauth_transaction(db: Session, redirect_after: str = "/") -> OAuthTransaction:
    transaction = OAuthTransaction(
        state=secrets.token_urlsafe(48),
        nonce=secrets.token_urlsafe(32),
        redirect_after=redirect_after,
        expires_at=now_utc() + timedelta(minutes=10),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def build_microsoft_redirect_uri(settings: Settings, request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    forwarded_host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    ).split(",")[0].strip()
    forwarded_port = (request.headers.get("x-forwarded-port") or "").split(",")[0].strip()

    host = forwarded_host
    if host and ":" not in host and forwarded_port:
        is_default_port = (forwarded_proto == "https" and forwarded_port == "443") or (
            forwarded_proto == "http" and forwarded_port == "80"
        )
        if not is_default_port:
            host = f"{host}:{forwarded_port}"

    return f"{forwarded_proto}://{host}{settings.microsoft_redirect_path}"


def build_authorize_url(settings: Settings, transaction: OAuthTransaction, redirect_uri: str) -> str:
    query = urlencode(
        {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "scope": settings.microsoft_scope_value,
            "state": transaction.state,
            "nonce": transaction.nonce,
            "prompt": "select_account",
        }
    )
    return f"{settings.microsoft_authorize_url}?{query}"


async def exchange_code_for_token(settings: Settings, code: str, redirect_uri: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            settings.microsoft_token_url,
            data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": settings.microsoft_scope_value,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    response.raise_for_status()
    return response.json()


async def resolve_microsoft_profile(token_payload: dict[str, Any]) -> dict[str, str | None]:
    id_token_claims = decode_jwt_payload(token_payload.get("id_token"))
    email = first_present(id_token_claims, "email", "preferred_username", "upn", "unique_name")
    display_name = first_present(id_token_claims, "name")

    access_token = token_payload.get("access_token")
    if access_token:
        graph_profile = await fetch_graph_profile(access_token)
        email = first_present(graph_profile, "mail", "userPrincipalName") or email
        display_name = first_present(graph_profile, "displayName") or display_name

    return {
        "email": email.lower() if email else None,
        "display_name": display_name,
    }


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    except (ValueError, json.JSONDecodeError):
        return {}


async def fetch_graph_profile(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName,displayName",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        return {}
    return response.json()


def first_present(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def find_pending_transaction(db: Session, state: str) -> OAuthTransaction | None:
    return db.scalar(
        select(OAuthTransaction).where(
            OAuthTransaction.state == state,
            OAuthTransaction.status == OAuthStatus.pending,
        )
    )


def is_email_whitelisted(db: Session, email: str) -> bool:
    return db.scalar(select(UserWhitelist).where(UserWhitelist.email == email.lower())) is not None


def is_initialization_email(email: str | None, initialization_email: str) -> bool:
    if not email:
        return False
    return email.strip().lower() == initialization_email.strip().lower()


def seed_initialization_user(db: Session, initialization_email: str) -> None:
    normalized_email = initialization_email.strip().lower()
    if not normalized_email:
        return

    whitelist_entry = db.scalar(select(UserWhitelist).where(UserWhitelist.email == normalized_email))
    if whitelist_entry is not None:
        db.delete(whitelist_entry)

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        user = User(
            email=normalized_email,
            system_role=SystemRole.admin,
        )
        db.add(user)
    else:
        user.system_role = SystemRole.admin
    db.commit()


def get_or_create_user_from_microsoft_profile(db: Session, email: str, display_name: str | None) -> User:
    normalized_email = email.lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        user = User(email=normalized_email, display_name=display_name)
        db.add(user)
        db.flush()
        return user

    if display_name and user.display_name != display_name:
        user.display_name = display_name
    return user


def issue_user_session(db: Session, user: User, ttl_minutes: int) -> tuple[str, UserSession]:
    raw_session_key = f"s1_{secrets.token_urlsafe(48)}"
    session = UserSession(
        user_id=user.id,
        session_key_hash=hash_session_key(raw_session_key),
        expires_at=now_utc() + timedelta(minutes=ttl_minutes),
        last_seen_at=now_utc(),
    )
    db.add(session)
    db.flush()
    return raw_session_key, session


def get_user_by_session_key(db: Session, raw_session_key: str | None) -> User | None:
    if not raw_session_key:
        return None
    session = db.scalar(
        select(UserSession).where(
            UserSession.session_key_hash == hash_session_key(raw_session_key),
            UserSession.revoked_at.is_(None),
        )
    )
    if session is None:
        return None

    expires_at = ensure_aware_utc(session.expires_at)
    if expires_at <= now_utc():
        session.revoked_at = now_utc()
        db.commit()
        return None

    session.last_seen_at = now_utc()
    db.commit()
    return session.user


def revoke_session_key(db: Session, raw_session_key: str | None) -> None:
    if not raw_session_key:
        return
    session = db.scalar(
        select(UserSession).where(
            UserSession.session_key_hash == hash_session_key(raw_session_key),
            UserSession.revoked_at.is_(None),
        )
    )
    if session is not None:
        session.revoked_at = now_utc()
        db.commit()


def cleanup_expired_sessions(db: Session) -> int:
    result = db.execute(
        delete(UserSession).where(
            (UserSession.expires_at <= now_utc())
            | (UserSession.revoked_at.is_not(None))
        )
    )
    db.commit()
    return result.rowcount or 0


def cleanup_oauth_transactions(db: Session) -> int:
    result = db.execute(
        delete(OAuthTransaction).where(
            (OAuthTransaction.expires_at <= now_utc())
            | (OAuthTransaction.status != OAuthStatus.pending)
            | (OAuthTransaction.completed_at.is_not(None))
        )
    )
    db.commit()
    return result.rowcount or 0


def hash_session_key(raw_session_key: str) -> str:
    return hashlib.sha256(raw_session_key.encode("utf-8")).hexdigest()


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
