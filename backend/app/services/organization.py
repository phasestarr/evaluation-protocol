from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.postgres.models import (
    OrganizationMembership,
    OrganizationNode,
    OrganizationNodeType,
)


def seed_root_organization(db: Session) -> None:
    root = db.scalar(
        select(OrganizationNode).where(
            OrganizationNode.node_type == OrganizationNodeType.company,
            OrganizationNode.parent_id.is_(None),
        )
    )
    if root is None:
        db.add(OrganizationNode(name="Company", node_type=OrganizationNodeType.company))
        db.commit()


def organization_tree(db: Session) -> tuple[list[OrganizationNode], list[OrganizationMembership]]:
    seed_root_organization(db)
    nodes = db.scalars(select(OrganizationNode).order_by(OrganizationNode.id)).all()
    memberships = db.scalars(select(OrganizationMembership).order_by(OrganizationMembership.id)).all()
    return nodes, memberships


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
