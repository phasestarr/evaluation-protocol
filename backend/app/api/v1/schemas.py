from pydantic import BaseModel


class WhitelistCreateIn(BaseModel):
    email: str
    job_title: str | None = None
    display_name: str | None = None
    system_role: str = "user"


class OrganizationNodeCreateIn(BaseModel):
    name: str
    node_type: str
    parent_id: int | None = None


class OrganizationMembershipCreateIn(BaseModel):
    email: str | None = None
    user_id: int | None = None
    organization_node_id: int
    membership_role: str = "member"


class EvaluationQuestionCreateIn(BaseModel):
    evaluation_type: str
    title: str
    description: str | None = None
    weight: int | None = None
    organization_node_id: int | None = None


class EvaluationGuideIn(BaseModel):
    content: str


class SelfReviewAnswerIn(BaseModel):
    answer_text: str


class ReviewScoreIn(BaseModel):
    target_user_id: int
    question_id: int
    score: int


class ReviewScoresIn(BaseModel):
    scores: list[ReviewScoreIn]


class StartCycleIn(BaseModel):
    name: str
