from pydantic import BaseModel


class WhitelistCreateIn(BaseModel):
    email: str
    job_title: str | None = None
    display_name: str | None = None
    system_role: str = "user"


class EvaluationQuestionCreateIn(BaseModel):
    evaluation_type: str
    title: str
    description: str | None = None
    weight: int | None = None
    organization_node_id: int | None = None


class EvaluationGuideIn(BaseModel):
    content: str


class StartCycleIn(BaseModel):
    name: str


class UserSystemRoleUpdateIn(BaseModel):
    system_role: str
