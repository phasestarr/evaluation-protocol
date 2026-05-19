from pydantic import BaseModel


class OrganizationNodeOut(BaseModel):
    id: int
    name: str
    node_type: str


class CurrentUserOut(BaseModel):
    email: str
    display_name: str | None = None
    job_title: str | None = None
    system_role: str
    has_leader_membership: bool
    organization_affiliation: str
    organization_node: OrganizationNodeOut | None = None


class AuthStatusOut(BaseModel):
    authenticated: bool
    user: CurrentUserOut | None = None
