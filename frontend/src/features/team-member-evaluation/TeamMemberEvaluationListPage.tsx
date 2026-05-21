import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchManagerDetailReviewContexts } from "../../shared/api/evaluations";
import { CompletionBadge } from "../../shared/ui/ActionCard/ActionCard";
import { StatusMessage } from "../../shared/ui/StatusMessage/StatusMessage";
import type { PeerReviewContext } from "../../shared/types";
import "../peer-evaluation/PeerEvaluationPage.css";

export function TeamMemberEvaluationListPage() {
  const [contexts, setContexts] = useState<PeerReviewContext[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchManagerDetailReviewContexts()
      .then((result) => setContexts(result.contexts))
      .catch((error) => setMessage(error instanceof Error ? error.message : "팀원평가 목록을 불러오지 못했습니다."));
  }, []);

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Manager Detail</p>
        <h1>팀원평가</h1>
        <p>평가할 대상자를 선택해 주세요.</p>
      </div>
      <StatusMessage message={message} />
      <div className="action-grid">
        {contexts.map((context) => (
          <Link
            className="team-context-row"
            key={`${context.team_node_id}:${context.target_user_id}`}
            to={`/manager-detail-review/${context.team_node_id}/${context.target_user_id}`}
          >
            <div>
              <strong>{context.title}</strong>
              <span>{context.role_label}</span>
            </div>
            <CompletionBadge status={context.complete ? "complete" : "incomplete"} />
          </Link>
        ))}
      </div>
      {contexts.length === 0 && <p className="empty-copy">평가 가능한 팀원평가 항목이 없습니다.</p>}
    </section>
  );
}
