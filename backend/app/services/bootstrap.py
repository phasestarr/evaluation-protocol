import asyncio

from app.auth import (
    cleanup_expired_sessions,
    cleanup_oauth_transactions,
    seed_initialization_user,
)
from app.config import get_settings
from app.db.postgres.migrations import run_database_migrations
from app.db.postgres.session import SessionLocal
from app.services.evaluation import seed_evaluation_system_state
from app.services.organization import seed_root_organization

settings = get_settings()


def initialize_runtime_state() -> None:
    run_database_migrations()
    with SessionLocal() as db:
        seed_initialization_user(db, settings.initialization_email_normalized)
        seed_root_organization(db)
        seed_evaluation_system_state(db)
        cleanup_expired_sessions(db)
        cleanup_oauth_transactions(db)


async def session_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(settings.session_cleanup_interval_minutes * 60)
        with SessionLocal() as db:
            cleanup_expired_sessions(db)
            cleanup_oauth_transactions(db)
