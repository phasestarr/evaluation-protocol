import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { UsersRound } from "lucide-react";
import { fetchPeerReviewContexts } from "../../shared/api/evaluations";
import { CompletionBadge } from "../../shared/ui/ActionCard/ActionCard";
import { PageHeader } from "../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../shared/ui/StatusMessage/StatusMessage";
import type { PeerReviewContext } from "../../shared/types";
import "./PeerEvaluationPage.css";

export function PeerEvaluationListPage() {
  const [contexts, setContexts] = useState<PeerReviewContext[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchPeerReviewContexts()
      .then((result) => setContexts(result.contexts))
      .catch((error) => setMessage(error instanceof Error ? error.message : "동료평가 목록을 불러오지 못했습니다."));
  }, []);

  return (
    <section className="dashboard">
      <PageHeader icon={UsersRound} eyebrow="Peer Review" title="동료평가" description="평가할 팀을 선택해 주세요." />
      <StatusMessage message={message} />
      <div className="action-grid">
        {contexts.map((context) => (
          <Link className="team-context-row" key={context.team_node_id} to={`/peer-review/${context.team_node_id}`}>
            <div>
              <strong>{context.title}</strong>
              <span>{context.role_label}</span>
            </div>
            <CompletionBadge status={context.complete ? "complete" : "incomplete"} />
          </Link>
        ))}
      </div>
      {contexts.length === 0 && <p className="empty-copy">평가 가능한 팀 소속이 없습니다.</p>}
    </section>
  );
}
