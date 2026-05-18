from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import get_settings
from app.db.postgres.session import engine

CURRENT_REVISION = "20260518_000005"
MANAGED_TABLES = {
    "oauth_transactions",
    "organization_nodes",
    "organization_memberships",
    "user_sessions",
    "user_whitelist",
    "users",
}


def run_database_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

    existing_tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in existing_tables and MANAGED_TABLES.issubset(existing_tables):
        command.stamp(config, CURRENT_REVISION)
        return

    command.upgrade(config, "head")
