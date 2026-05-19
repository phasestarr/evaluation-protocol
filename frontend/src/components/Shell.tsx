import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, Shield } from "lucide-react";
import type { CurrentUser } from "../types";

type NavItem = {
  to: string;
  label: string;
  requiresLeader?: boolean;
  requiresAdmin?: boolean;
};

const navItems: NavItem[] = [
  { to: "/", label: "홈" },
  { to: "/self-review", label: "자기평가" },
  { to: "/team-review", label: "팀 평가" },
  { to: "/direct-report-review", label: "하위 평가", requiresLeader: true },
  { to: "/admin", label: "관리자", requiresAdmin: true }
];

export function Shell({ user, onLogout, children }: { user: CurrentUser | null; onLogout: () => Promise<void>; children: ReactNode }) {
  const navigate = useNavigate();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="topbar-brand" to="/">
          <Shield size={22} />
          <span>Evaluation Protocol</span>
        </Link>
        <nav className="topbar-nav">
          {navItems.map((item) => {
            if (item.requiresLeader && !user?.has_leader_membership) return null;
            if (item.requiresAdmin && user?.system_role !== "admin") return null;
            return (
              <Link key={item.to} to={item.to}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <button
          className="icon-button"
          type="button"
          title="로그아웃"
          onClick={async () => {
            await onLogout();
            navigate("/login");
          }}
        >
          <LogOut size={19} />
        </button>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
