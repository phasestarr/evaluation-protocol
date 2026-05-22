from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import MANAGER_DETAIL, PEER, SELF
from app.db.postgres.models import EvaluationQuestion, OrganizationImportUser, OrganizationNode, OrganizationNodeType, PeerReviewTeam, PeerReviewTeamMember
from app.services.evaluations.questions import evaluation_guide_content


def admin_readiness(db: Session) -> dict:
    org_user_count = db.scalar(select(func.count()).select_from(OrganizationImportUser)) or 0
    non_root_node_count = db.scalar(
        select(func.count())
        .select_from(OrganizationNode)
        .where(OrganizationNode.node_type != OrganizationNodeType.company)
    ) or 0
    peer_team_count = db.scalar(select(func.count()).select_from(PeerReviewTeam)) or 0
    peer_team_member_count = db.scalar(select(func.count()).select_from(PeerReviewTeamMember)) or 0
    self_question_stats = active_question_stats(db, SELF)
    peer_question_stats = active_question_stats(db, PEER)
    manager_guide_complete = evaluation_guide_exists(db, MANAGER_DETAIL)

    teams = db.scalars(
        select(OrganizationNode)
        .where(OrganizationNode.node_type == OrganizationNodeType.team)
        .order_by(OrganizationNode.id)
    ).all()
    manager_question_stats = {
        team.id: active_question_stats(db, MANAGER_DETAIL, team.id)
        for team in teams
    }
    manager_team_items = [
        {
            "id": team.id,
            "name": team.name,
            "complete": manager_question_stats[team.id]["complete"],
            "question_count": manager_question_stats[team.id]["total_count"],
            "complete_question_count": manager_question_stats[team.id]["complete_count"],
        }
        for team in teams
    ]

    items = {
        "organization": {
            "complete": org_user_count > 0 and non_root_node_count > 0,
            "label": "조직 관리",
            "detail": f"사용자 {org_user_count}명, 조직 노드 {non_root_node_count}개",
        },
        "peer_teams": {
            "complete": peer_team_count > 0 and peer_team_member_count > 0,
            "label": "동료평가 팀 관리",
            "detail": f"팀 {peer_team_count}개, 멤버 {peer_team_member_count}명",
        },
        "self_questions": {
            "complete": self_question_stats["complete"],
            "label": "자기평가 문항 관리",
            "detail": question_readiness_detail(self_question_stats),
        },
        "peer_questions": {
            "complete": peer_question_stats["complete"],
            "label": "동료평가 문항 관리",
            "detail": question_readiness_detail(peer_question_stats),
        },
        "manager_detail_questions": {
            "complete": bool(manager_team_items) and all(item["complete"] for item in manager_team_items),
            "label": "팀원평가 문항 관리",
            "detail": (
                f"{'안내문 완료' if manager_guide_complete else '안내문 미완료'}, "
                f"완료 {sum(1 for item in manager_team_items if item['complete'])}/{len(manager_team_items)}팀"
            ),
            "teams": manager_team_items,
        },
    }
    return {
        "ready": all(item["complete"] for item in items.values()),
        "items": items,
    }


def active_question_stats(db: Session, evaluation_type: str, organization_node_id: int | None = None) -> dict:
    query = select(EvaluationQuestion).where(
        EvaluationQuestion.evaluation_type == evaluation_type,
        EvaluationQuestion.is_active.is_(True),
    )
    if evaluation_type == MANAGER_DETAIL:
        query = query.where(EvaluationQuestion.organization_node_id == organization_node_id)
    questions = db.scalars(query).all()
    total_count = len(questions)
    guide_complete = evaluation_guide_exists(db, evaluation_type)
    return {
        "complete": guide_complete and total_count > 0,
        "complete_count": total_count if guide_complete and total_count > 0 else 0,
        "guide_complete": guide_complete,
        "total_count": total_count,
    }


def evaluation_guide_exists(db: Session, evaluation_type: str) -> bool:
    return bool(evaluation_guide_content(db, evaluation_type).strip())


def question_readiness_detail(stats: dict) -> str:
    guide_label = "안내문 완료" if stats["guide_complete"] else "안내문 미완료"
    return f"{guide_label}, 문항 {stats['total_count']}개"
