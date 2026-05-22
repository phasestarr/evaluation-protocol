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
