import { useEffect, useMemo, useState } from "react";
import { CheckSquare, LayoutDashboard, Shield, UserRound, UsersRound } from "lucide-react";
import { fetchEvaluationProgress } from "../../shared/api/evaluations";
import { systemRoleLabel } from "../../shared/labels/systemRoles";
import { ActionCard } from "../../shared/ui/ActionCard/ActionCard";
import { InfoBlock } from "../../shared/ui/InfoBlock/InfoBlock";
import { PageHeader } from "../../shared/ui/PageHeader/PageHeader";
import type { Action, CompletionStatus, CurrentUser, EvaluationProgressResponse } from "../../shared/types";
import "./DashboardPage.css";

export function DashboardPage({ user }: { user: CurrentUser }) {
  const [progress, setProgress] = useState<EvaluationProgressResponse | null>(null);

  useEffect(() => {
    fetchEvaluationProgress()
      .then(setProgress)
      .catch(() => setProgress(null));
  }, []);

  const evaluationActions = useMemo<Action[]>(() => {
    const base: Action[] = [
      {
        to: "/self-review",
        title: "자기평가",
        description: "본인 평가 입력",
        icon: UserRound,
        completion: completionFromProgress(progress?.self.complete),
      },
      {
        to: "/peer-review",
        title: "동료평가",
        description: progress?.peer ? `완료 ${progress.peer.completed_count}/${progress.peer.total_count}팀` : "동료평가 입력",
        icon: UsersRound,
        completion: completionFromProgress(progress?.peer.complete),
      },
    ];

    if (user.has_manager_detail_access) {
      base.push({
        to: "/manager-detail-review",
        title: "팀원평가",
        description: progress?.manager_detail
          ? `완료 ${progress.manager_detail.completed_count}/${progress.manager_detail.total_count}명`
          : "소속 팀원 평가",
        icon: CheckSquare,
        completion: completionFromProgress(progress?.manager_detail.complete),
      });
    }

    return base;
  }, [progress, user.has_manager_detail_access]);

  return (
    <section className="dashboard">
      <PageHeader
        icon={LayoutDashboard}
        className="dashboard-hero"
        eyebrow="Dashboard"
        title={user.display_name || user.email}
        description={user.organization_affiliation || "소속 부서 미지정"}
        aside={(
          <div className="role-stack">
            <span className="role-pill">{systemRoleLabel(user.system_role)}</span>
          </div>
        )}
      />

      <div className="meta-grid">
        <InfoBlock label="메일" value={user.email} />
        <InfoBlock label="직급" value={user.job_title || "미지정"} />
        <InfoBlock label="시스템 권한" value={systemRoleLabel(user.system_role)} />
      </div>

      <WorkSection title="평가" actions={evaluationActions} />

      {user.system_role === "admin" && (
        <WorkSection
          title="관리"
          actions={[
            {
              to: "/admin",
              title: "관리자 페이지",
              description: "사용자, 조직, 결과 관리",
              icon: Shield,
              tone: "admin",
            },
          ]}
        />
      )}
    </section>
  );
}

function completionFromProgress(value: boolean | undefined): CompletionStatus | undefined {
  if (value === undefined) return undefined;
  return value ? "complete" : "incomplete";
}

function WorkSection({ title, actions }: { title: string; actions: Action[] }) {
  return (
    <section className="work-section">
      <h2>{title}</h2>
      <div className="action-grid">
        {actions.map((action) => (
          <ActionCard key={action.to} {...action} />
        ))}
      </div>
    </section>
  );
}
