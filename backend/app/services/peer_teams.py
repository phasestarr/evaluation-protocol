from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.postgres.models import OrganizationImportUser, PeerReviewTeam, PeerReviewTeamMember, User
from app.services.org_import import csv_error, parse_csv_block


@dataclass(frozen=True)
class ParsedPeerTeam:
    line_number: int
    name: str
    member_names: list[str]
    sort_order: int


def import_peer_teams_csv(db: Session, content: bytes) -> dict:
    teams = parse_peer_teams_csv(db, content)
    apply_peer_teams_import(db, teams)
    return {"teams": list_peer_teams(db)}


def parse_peer_teams_csv(db: Session, content: bytes) -> list[ParsedPeerTeam]:
    rows = parse_csv_block(content)
    known_names = {
        row.name: row
        for row in db.scalars(select(OrganizationImportUser).order_by(OrganizationImportUser.sort_order, OrganizationImportUser.id)).all()
    }
    teams: list[ParsedPeerTeam] = []
    seen_team_names: set[str] = set()

    for index, (line_number, raw_row) in enumerate(rows, start=1):
        values = [value.strip() for value in raw_row]
        if len(values) < 2:
            raise csv_error(line_number, "team row requires team_name and count")
        team_name = values[0]
        if not team_name:
            raise csv_error(line_number, "team_name is required")
        if team_name in seen_team_names:
            raise csv_error(line_number, f"Duplicate peer team: {team_name}")
        seen_team_names.add(team_name)

        try:
            expected_count = int(values[1])
        except ValueError as exc:
            raise csv_error(line_number, "count must be an integer") from exc
        if expected_count < 0:
            raise csv_error(line_number, "count must be zero or greater")

        member_names = [value for value in values[2:] if value]
        if len(member_names) != expected_count:
            raise csv_error(line_number, f"count is {expected_count}, but {len(member_names)} members were provided")
        seen_member_names: set[str] = set()
        for member_name in member_names:
            if member_name in seen_member_names:
                raise csv_error(line_number, f"Duplicate member in team: {member_name}")
            seen_member_names.add(member_name)
            if member_name not in known_names:
                raise csv_error(line_number, f"Unknown user name in organization import users: {member_name}")
        teams.append(ParsedPeerTeam(line_number=line_number, name=team_name, member_names=member_names, sort_order=index))

    return teams


def apply_peer_teams_import(db: Session, teams: list[ParsedPeerTeam]) -> None:
    try:
        imported_users = db.scalars(
            select(OrganizationImportUser).order_by(OrganizationImportUser.sort_order, OrganizationImportUser.id)
        ).all()
        user_by_name = {row.name: row for row in imported_users}

        db.execute(delete(PeerReviewTeam))
        db.flush()

        for team in teams:
            db_team = PeerReviewTeam(name=team.name, sort_order=team.sort_order)
            db.add(db_team)
            db.flush()
            for member_index, member_name in enumerate(team.member_names, start=1):
                imported_user = user_by_name.get(member_name)
                if imported_user is None:
                    raise csv_error(team.line_number, f"Unknown user name in organization import users: {member_name}")
                db.add(
                    PeerReviewTeamMember(
                        team_id=db_team.id,
                        user_id=imported_user.user_id,
                        sort_order=member_index,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise


def list_peer_teams(db: Session) -> list[dict]:
    teams = db.scalars(select(PeerReviewTeam).order_by(PeerReviewTeam.sort_order, PeerReviewTeam.id)).all()
    return [serialize_peer_team(team) for team in teams]


def serialize_peer_team(team: PeerReviewTeam) -> dict:
    members = sorted(team.members, key=lambda member: (member.sort_order, member.id))
    return {
        "id": team.id,
        "name": team.name,
        "count": len(members),
        "members": [serialize_peer_team_member(member) for member in members],
    }


def serialize_peer_team_member(member: PeerReviewTeamMember) -> dict:
    user: User | None = member.user
    return {
        "id": member.id,
        "user_id": member.user_id,
        "name": user.display_name if user else "",
        "email": user.email if user else "",
        "job_title": user.job_title if user else "",
    }
