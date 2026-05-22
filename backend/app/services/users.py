from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.postgres.models import (
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
    User,
)

settings = get_settings()


def serialize_current_user(user: User) -> dict:
    return {
        "email": user.email,
        "display_name": user.display_name,
        "job_title": user.job_title,
        "system_role": user.system_role.value,
        "has_leader_membership": has_leader_membership(user),
        "has_manager_detail_access": has_manager_detail_access(user),
        "organization_affiliation": format_user_affiliation(user),
    }


def serialize_admin_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "job_title": user.job_title,
        "system_role": user.system_role.value,
    }


def has_leader_membership(user: User) -> bool:
    return any(membership.membership_role == OrganizationMembershipRole.leader for membership in user.memberships)


def has_manager_detail_access(user: User) -> bool:
    for membership in user.memberships:
        node = membership.organization_node
        if node is None:
            continue
        if node.node_type == OrganizationNodeType.head:
            return True
        if node.node_type == OrganizationNodeType.team and membership.membership_role == OrganizationMembershipRole.leader:
            return True
    return False


def format_user_affiliation(user: User) -> str:
    memberships = sorted(
        (membership for membership in user.memberships if membership.organization_node is not None),
        key=membership_affiliation_sort_key,
    )
    lines = [format_membership_affiliation(membership, user) for membership in memberships]
    peer_team_names = sorted(
        {
            membership.team.name
            for membership in user.peer_team_members
            if membership.team is not None
        }
    )
    if peer_team_names:
        if lines:
            lines.append("")
        lines.append(f"Teams : [{', '.join(peer_team_names)}]")
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
    return " > ".join([*segments, role_text])


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


def visible_users(db: Session) -> list[User]:
    from sqlalchemy import select

    return db.scalars(
        select(User)
        .where(User.email != settings.initialization_email_normalized)
        .order_by(User.email)
    ).all()
