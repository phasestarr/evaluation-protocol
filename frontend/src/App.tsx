import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BarChart3 } from "lucide-react";
import { fetchAuthStatus, logout } from "./api";
import { Shell } from "./components/Shell";
import { AdminHomePage } from "./pages/AdminHomePage";
import { AdminOrgPage, AdminOrgTreePage, AdminOrgUsersPage } from "./pages/AdminOrgPage";
import { AdminPage } from "./pages/AdminPage";
import { AdminPeerTeamsPage } from "./pages/AdminPeerTeamsPage";
import {
  AdminManagerDetailQuestionsDetailPage,
  AdminManagerDetailQuestionsPage,
  AdminQuestionsPage,
} from "./pages/AdminQuestionsPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ManagerDetailReviewDetailPage } from "./pages/ManagerDetailReviewDetailPage";
import { ManagerDetailReviewPage } from "./pages/ManagerDetailReviewPage";
import { SelfReviewPage } from "./pages/SelfReviewPage";
import { SplashPage } from "./pages/SplashPage";
import { PeerReviewDetailPage } from "./pages/PeerReviewDetailPage";
import { PeerReviewPage } from "./pages/PeerReviewPage";
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
                <Route path="/self-review" element={<SelfReviewPage />} />
                <Route path="/peer-review" element={<PeerReviewPage />} />
                <Route path="/peer-review/:teamNodeId" element={<PeerReviewDetailPage />} />
                <Route path="/manager-detail-review" element={<ManagerDetailReviewPage />} />
                <Route path="/manager-detail-review/:teamNodeId" element={<ManagerDetailReviewDetailPage />} />
                <Route path="/admin" element={<AdminHomePage user={auth.user} />} />
                <Route path="/admin/users" element={<AdminUsersPage user={auth.user} />} />
                <Route path="/admin/org" element={<AdminOrgPage user={auth.user} />} />
                <Route path="/admin/org/users" element={<AdminOrgUsersPage user={auth.user} />} />
                <Route path="/admin/org/tree-view" element={<AdminOrgTreePage user={auth.user} />} />
                <Route path="/admin/peer-teams" element={<AdminPeerTeamsPage user={auth.user} />} />
                <Route path="/admin/questions/self" element={<AdminQuestionsPage user={auth.user} evaluationType="self" />} />
                <Route path="/admin/questions/peer" element={<AdminQuestionsPage user={auth.user} evaluationType="peer" />} />
                <Route path="/admin/questions/manager-detail" element={<AdminManagerDetailQuestionsPage user={auth.user} />} />
                <Route path="/admin/questions/manager-detail/:teamNodeId" element={<AdminManagerDetailQuestionsDetailPage user={auth.user} />} />
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
