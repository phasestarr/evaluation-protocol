import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchTeamReviewContexts } from "../api";
import type { TeamReviewContext } from "../types";

export function TeamReviewPage() {
  const [contexts, setContexts] = useState<TeamReviewContext[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchTeamReviewContexts()
      .then((result) => setContexts(result.contexts))
      .catch((error) => setMessage(error instanceof Error ? error.message : "같은 팀 평가 목록을 불러오지 못했습니다."));
  }, []);

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Team Review</p>
        <h1>같은 팀 평가</h1>
        <p>평가할 팀을 선택해 주세요.</p>
      </div>
      {message && <div className="admin-message">{message}</div>}
      <div className="action-grid">
        {contexts.map((context) => (
          <Link className="team-context-row" key={context.team_node_id} to={`/team-review/${context.team_node_id}`}>
            <div>
              <strong>{context.title}</strong>
              <span>{context.role_label}</span>
            </div>
          </Link>
        ))}
      </div>
      {contexts.length === 0 && <p className="empty-copy">평가 가능한 팀 소속이 없습니다.</p>}
    </section>
  );
}
