from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.postgres.models import (
    OrganizationMembership,
    OrganizationMembershipRole,
    OrganizationNode,
    OrganizationNodeType,
    User,
)
from app.services.authz import is_login_allowed
from app.services.text import normalize_email


def seed_root_organization(db: Session) -> None:
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


def organization_tree(db: Session) -> tuple[list[OrganizationNode], list[OrganizationMembership]]:
    seed_root_organization(db)
    nodes = db.scalars(select(OrganizationNode).order_by(OrganizationNode.id)).all()
    memberships = db.scalars(select(OrganizationMembership).order_by(OrganizationMembership.id)).all()
    return nodes, memberships


def create_org_node(db: Session, name: str, node_type_value: str, parent_id: int | None) -> OrganizationNode:
    node_type = parse_node_type(node_type_value)
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required")

    if node_type != OrganizationNodeType.company and parent_id is None:
        raise HTTPException(status_code=400, detail="Head and team nodes require a parent")

    parent = db.get(OrganizationNode, parent_id) if parent_id is not None else None
    if parent_id is not None and parent is None:
        raise HTTPException(status_code=404, detail="Parent node not found")
    if node_type == OrganizationNodeType.head and parent and parent.node_type != OrganizationNodeType.company:
        raise HTTPException(status_code=400, detail="Head nodes must be created under a company")
    if node_type == OrganizationNodeType.team and parent and parent.node_type != OrganizationNodeType.head:
        raise HTTPException(status_code=400, detail="Team nodes must be created under a head")

    node = OrganizationNode(name=clean_name, node_type=node_type, parent_id=parent_id)
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def delete_org_node(db: Session, node_id: int) -> None:
    node = db.get(OrganizationNode, node_id)
    if node is None:
        return
    if is_seed_root_node(node):
        raise HTTPException(status_code=400, detail="NEXTIN root node cannot be deleted")

    subtree_ids = collect_subtree_node_ids(db, node_id)
    db.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_node_id.in_(subtree_ids)))
    nodes = db.scalars(select(OrganizationNode).where(OrganizationNode.id.in_(subtree_ids))).all()
    for row in sorted(nodes, key=lambda item: item.id, reverse=True):
        db.delete(row)
    db.commit()


def create_membership(
    db: Session,
    organization_node_id: int,
    membership_role_value: str,
    user_id: int | None,
    email: str | None,
) -> OrganizationMembership:
    node = db.get(OrganizationNode, organization_node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Organization node not found")

    role = parse_membership_role(membership_role_value)
    user = resolve_membership_user(db, user_id, email)
    existing_membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_node_id == node.id,
            OrganizationMembership.membership_role == role,
        )
    )
    if existing_membership is not None:
        return existing_membership

    membership = OrganizationMembership(user_id=user.id, organization_node_id=node.id, membership_role=role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def delete_membership(db: Session, membership_id: int) -> None:
    membership = db.get(OrganizationMembership, membership_id)
    if membership is not None:
        db.delete(membership)
        db.commit()


def resolve_membership_user(db: Session, user_id: int | None, email_value: str | None) -> User:
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not is_login_allowed(db, user.email):
            raise HTTPException(status_code=400, detail="User must be whitelisted first")
        return user

    email = normalize_email(email_value or "")
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


def parse_node_type(value: str) -> OrganizationNodeType:
    try:
        return OrganizationNodeType(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid organization node type") from exc


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
