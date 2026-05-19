from pydantic import BaseModel

class CurrentUserOut(BaseModel):
    email: str
    display_name: str | None = None
    job_title: str | None = None
    system_role: str
    has_leader_membership: bool
    organization_affiliation: str


class AuthStatusOut(BaseModel):
    authenticated: bool
    user: CurrentUserOut | None = None
