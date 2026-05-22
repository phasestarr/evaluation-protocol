from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import get_settings
from app.db.postgres.session import engine

BASELINE_REVISION = "20260518_000001"
BASELINE_TABLES = {
    "evaluation_cycle_guides",
    "evaluation_cycle_questions",
    "evaluation_cycles",
    "evaluation_guides",
    "evaluation_membership_snapshots",
    "evaluation_org_node_snapshots",
    "evaluation_participants",
    "evaluation_peer_team_member_snapshots",
    "evaluation_peer_team_snapshots",
    "evaluation_questions",
    "evaluation_system_state",
    "oauth_transactions",
    "organization_import_users",
    "peer_review_team_members",
    "peer_review_teams",
    "organization_nodes",
    "organization_memberships",
    "review_assignments",
    "review_scores",
    "self_review_answers",
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
    if "alembic_version" not in existing_tables and BASELINE_TABLES.issubset(existing_tables):
        command.stamp(config, BASELINE_REVISION)

    command.upgrade(config, "head")
