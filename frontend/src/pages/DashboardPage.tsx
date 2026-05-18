import { useMemo } from "react";
import { CheckSquare, Shield, UserRound, UsersRound } from "lucide-react";
import { ActionCard } from "../components/ActionCard";
import { InfoBlock } from "../components/InfoBlock";
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
        to: "/team-review",
        title: "같은 팀 및 본부장 평가",
        description: user.organization_role === "manager" ? "본인을 제외한 동료 및 상위 평가" : "팀원, 팀장, 본부장 평가",
        icon: UsersRound
      }
    ];

    if (user.organization_role === "manager") {
      base.push({
        to: "/direct-report-review",
        title: "하위 팀원 세부평가",
        description: "소속 팀원의 세부 평가",
        icon: CheckSquare
      });
    }
    return base;
  }, [user.organization_role]);

  return (
    <section className="dashboard">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1>{user.display_name || user.email}</h1>
          <p>{user.organization_node?.name || "소속 부서 미지정"}</p>
        </div>
        <div className="role-stack">
          <span className="role-pill">{user.system_role === "admin" ? "admin" : "user"}</span>
          <span className="role-pill">{user.organization_role}</span>
        </div>
      </div>

      <div className="meta-grid">
        <InfoBlock label="메일" value={user.email} />
        <InfoBlock label="시스템 권한" value={user.system_role === "admin" ? "관리자" : "일반 사용자"} />
        <InfoBlock label="조직 역할" value={user.organization_role === "manager" ? "관리자/리더" : "직원"} />
        <InfoBlock label="조직 노드" value={user.organization_node?.node_type || "미지정"} />
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
