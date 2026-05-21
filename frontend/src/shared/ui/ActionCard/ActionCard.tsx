import { Link } from "react-router-dom";
import type { Action } from "../../types";
import "./ActionCard.css";

export function ActionCard({ to, title, description, icon: Icon, tone = "default", completion }: Action) {
  return (
    <Link className={`action-card ${tone}`} to={to}>
      <div className="action-icon">
        <Icon size={24} />
      </div>
      <div>
        <div className="action-card-title-row">
          <h3>{title}</h3>
          {completion && <CompletionBadge status={completion} />}
        </div>
        <p>{description}</p>
      </div>
    </Link>
  );
}

export function CompletionBadge({ status }: { status: "complete" | "incomplete" }) {
  return <span className={`completion-badge ${status}`}>{status === "complete" ? "완료" : "미완료"}</span>;
}
