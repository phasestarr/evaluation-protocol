from pydantic import BaseModel


class SelfReviewAnswerIn(BaseModel):
    answer_text: str


class ReviewScoreIn(BaseModel):
    target_user_id: int
    question_id: int
    score: int


class ReviewScoresIn(BaseModel):
    scores: list[ReviewScoreIn]
