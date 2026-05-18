import { BarChart3, GitBranch, UserPlus } from "lucide-react";
import { ActionCard } from "../components/ActionCard";
import type { CurrentUser } from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

export function AdminHomePage({ user }: { user: CurrentUser | null }) {
  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Admin</p>
        <h1>관리자 페이지</h1>
        <p>화이트리스트, 조직 트리, 평가 결과 열람 영역입니다.</p>
      </div>
      <div className="admin-layout">
        <div className="surface-panel">
          <h2>관리 기능</h2>
          <div className="action-grid three">
            <ActionCard to="/admin/users" title="사용자 추가" description="화이트리스트와 권한 관리" icon={UserPlus} />
            <ActionCard to="/admin/org" title="조직 트리" description="company, head, team 관리" icon={GitBranch} />
            <ActionCard to="/admin/results" title="결과 열람" description="평가 결과 확인" icon={BarChart3} />
          </div>
        </div>
        <div className="surface-panel">
          <h2>조직 구조</h2>
          <div className="tree-preview">
            <div>Company</div>
            <div>Head</div>
            <div>Team</div>
            <div>Staff / Manager</div>
          </div>
        </div>
      </div>
    </section>
  );
}
