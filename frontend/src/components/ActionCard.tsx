import { Link } from "react-router-dom";
import type { Action } from "../types";

export function ActionCard({ to, title, description, icon: Icon, tone = "default" }: Action) {
  return (
    <Link className={`action-card ${tone}`} to={to}>
      <div className="action-icon">
        <Icon size={24} />
      </div>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </Link>
  );
}
