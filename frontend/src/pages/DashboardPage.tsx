import { useMemo } from "react";
import { CheckSquare, Shield, UserRound, UsersRound } from "lucide-react";
import { ActionCard } from "../components/ActionCard";
import { InfoBlock } from "../components/InfoBlock";
import { systemRoleLabel } from "../labels";
import type { Action, CurrentUser } from "../types";

export function DashboardPage({ user }: { user: CurrentUser }) {
  const evaluationActions = useMemo<Action[]>(() => {
    const base: Action[] = [
      {
        to: "/self-review",
        title: "자기평가",
        description: "본인 평가 입력",
        icon: UserRound
      },
      {
        to: "/peer-review",
        title: "동료평가",
        description: "동료평가 입력",
        icon: UsersRound
      }
    ];

    if (user.has_leader_membership) {
      base.push({
        to: "/manager-detail-review",
        title: "팀원평가",
        description: "소속 팀원 평가",
        icon: CheckSquare
      });
    }
    return base;
  }, [user.has_leader_membership]);

  return (
    <section className="dashboard">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1>{user.display_name || user.email}</h1>
          <p>{user.organization_affiliation || "소속 부서 미지정"}</p>
        </div>
        <div className="role-stack">
          <span className="role-pill">{systemRoleLabel(user.system_role)}</span>
        </div>
      </div>

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
              tone: "admin"
            }
          ]}
        />
      )}
    </section>
  );
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
