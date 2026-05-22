import { useEffect, useState } from "react";
import { BarChart3, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchResultCycles } from "../../../shared/api/admin";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, ResultCycleSummary } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import "./AdminResultsPage.css";

export function AdminResultsPage({ user }: { user: CurrentUser | null }) {
  const [cycles, setCycles] = useState<ResultCycleSummary[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchResultCycles()
        .then((result) => setCycles(result.cycles))
        .catch((error) => setMessage(error instanceof Error ? error.message : "스냅샷 목록을 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="dashboard">
      <PageHeader
        icon={BarChart3}
        eyebrow="Results"
        title="평가 결과 열람"
        description="스냅샷을 선택한 뒤 사용자 단위로 자기평가, 동료평가, 팀원평가 결과를 확인합니다."
      />
      <StatusMessage message={message} />
      <div className="result-cycle-list">
        {cycles.map((cycle) => (
          <Link className="result-cycle-row" key={cycle.id} to={`/admin/results/${cycle.id}`}>
            <div className="result-cycle-row-main">
              <strong>{cycle.name}</strong>
              <div className="result-cycle-row-meta">
                <span className="result-chip">{cycle.snapshot_date}</span>
                <span className={`result-chip ${cycle.status}`}>{cycle.status === "running" ? "Running" : "Closed"}</span>
                <span className="result-chip">{cycle.participant_count}명</span>
              </div>
            </div>
            <ChevronRight size={20} />
          </Link>
        ))}
      </div>
      {cycles.length === 0 && <p className="empty-copy">아직 생성된 평가 스냅샷이 없습니다.</p>}
    </section>
  );
}
