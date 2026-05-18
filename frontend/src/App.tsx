import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BarChart3, CheckSquare, UserRound, UsersRound } from "lucide-react";
import { fetchAuthStatus, logout } from "./api";
import { Shell } from "./components/Shell";
import { AccessDeniedPage } from "./pages/AccessDeniedPage";
import { AdminHomePage } from "./pages/AdminHomePage";
import { AdminOrgPage } from "./pages/AdminOrgPage";
import { AdminPage } from "./pages/AdminPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { SplashPage } from "./pages/SplashPage";
import { WorkflowPage } from "./pages/WorkflowPage";
import type { AuthStatus } from "./types";

type AuthState = AuthStatus & {
  loading: boolean;
};

export default function App() {
  const [auth, setAuth] = useState<AuthState>({ loading: true, authenticated: false, user: null });

  useEffect(() => {
    fetchAuthStatus()
      .then((data) => setAuth({ loading: false, ...data }))
      .catch(() => setAuth({ loading: false, authenticated: false, user: null }));
  }, []);

  if (auth.loading) {
    return <SplashPage />;
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage authenticated={auth.authenticated} />} />
      <Route
        path="/*"
        element={
          <RequireAuth authenticated={auth.authenticated}>
            <Shell user={auth.user} onLogout={handleLogout(setAuth)}>
              <Routes>
                <Route path="/" element={auth.user ? <DashboardPage user={auth.user} /> : <Navigate to="/login" replace />} />
                <Route path="/self-review" element={<WorkflowPage icon={UserRound} title="자기평가" />} />
                <Route path="/team-review" element={<WorkflowPage icon={UsersRound} title="같은 팀 및 본부장 평가" />} />
                <Route
                  path="/direct-report-review"
                  element={
                    auth.user?.organization_role === "manager" ? (
                      <WorkflowPage icon={CheckSquare} title="하위 팀원 세부평가" />
                    ) : (
                      <AccessDeniedPage />
                    )
                  }
                />
                <Route path="/admin" element={<AdminHomePage user={auth.user} />} />
                <Route path="/admin/users" element={<AdminUsersPage user={auth.user} />} />
                <Route path="/admin/org" element={<AdminOrgPage user={auth.user} />} />
                <Route path="/admin/results" element={<AdminPage icon={BarChart3} title="평가 결과 열람" />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Shell>
          </RequireAuth>
        }
      />
    </Routes>
  );
}

function RequireAuth({ authenticated, children }: { authenticated: boolean; children: ReactNode }) {
  const location = useLocation();
  if (!authenticated) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return children;
}

function handleLogout(setAuth: Dispatch<SetStateAction<AuthState>>) {
  return async () => {
    await logout();
    setAuth({ loading: false, authenticated: false, user: null });
  };
}
