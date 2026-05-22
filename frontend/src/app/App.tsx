import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { fetchAuthStatus, logout } from "../shared/api/auth";
import { AppShell } from "../shared/ui/AppShell/AppShell";
import { SplashScreen } from "../shared/ui/SplashScreen/SplashScreen";
import { AccessDeniedPage } from "../features/access/AccessDeniedPage";
import { AdminDashboardPage } from "../features/admin/AdminDashboardPage";
import { AdminPeerTeamsPage } from "../features/admin/peer-teams/AdminPeerTeamsPage";
import {
  AdminOrganizationImportPage,
  AdminOrganizationTreePage,
  AdminOrganizationUsersPage,
} from "../features/admin/organization";
import {
  AdminPeerQuestionManagementPage,
  AdminSelfQuestionManagementPage,
  AdminTeamMemberQuestionManagementPage,
  AdminTeamMemberQuestionTeamsPage,
} from "../features/admin/questions";
import { AdminResultDetailPage } from "../features/admin/results/AdminResultDetailPage";
import { AdminResultUsersPage } from "../features/admin/results/AdminResultUsersPage";
import { AdminResultsPage } from "../features/admin/results/AdminResultsPage";
import { AdminUsersPage } from "../features/admin/users/AdminUsersPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { LoginPage } from "../features/auth/LoginPage";
import { TeamMemberEvaluationFormPage } from "../features/team-member-evaluation/TeamMemberEvaluationFormPage";
import { TeamMemberEvaluationListPage } from "../features/team-member-evaluation/TeamMemberEvaluationListPage";
import { SelfEvaluationPage } from "../features/self-evaluation/SelfEvaluationPage";
import { PeerEvaluationFormPage } from "../features/peer-evaluation/PeerEvaluationFormPage";
import { PeerEvaluationListPage } from "../features/peer-evaluation/PeerEvaluationListPage";
import type { AuthStatus } from "../shared/types";

type AuthState = AuthStatus & {
  loading: boolean;
};

export default function App() {
  const [auth, setAuth] = useState<AuthState>({ loading: true, authenticated: false, user: null });
  const location = useLocation();

  useEffect(() => {
    fetchAuthStatus()
      .then((data) => setAuth({ loading: false, ...data }))
      .catch(() => setAuth({ loading: false, authenticated: false, user: null }));
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.pathname, location.search]);

  if (auth.loading) {
    return <SplashScreen />;
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage authenticated={auth.authenticated} />} />
      <Route
        path="/*"
        element={(
          <RequireAuth authenticated={auth.authenticated}>
            <AppShell user={auth.user} onLogout={handleLogout(setAuth)}>
              <Routes>
                <Route path="/" element={auth.user ? <DashboardPage user={auth.user} /> : <Navigate to="/login" replace />} />
                <Route path="/self-review" element={<SelfEvaluationPage />} />
                <Route path="/peer-review" element={<PeerEvaluationListPage />} />
                <Route path="/peer-review/:teamNodeId" element={<PeerEvaluationFormPage />} />
                <Route
                  path="/manager-detail-review"
                  element={auth.user?.has_manager_detail_access ? <TeamMemberEvaluationListPage /> : <AccessDeniedPage />}
                />
                <Route path="/manager-detail-review/:teamNodeId" element={<Navigate to="/manager-detail-review" replace />} />
                <Route
                  path="/manager-detail-review/:teamNodeId/:targetUserId"
                  element={auth.user?.has_manager_detail_access ? <TeamMemberEvaluationFormPage /> : <AccessDeniedPage />}
                />
                <Route path="/admin" element={<AdminDashboardPage user={auth.user} />} />
                <Route path="/admin/users" element={<AdminUsersPage user={auth.user} />} />
                <Route path="/admin/org" element={<AdminOrganizationImportPage user={auth.user} />} />
                <Route path="/admin/org/users" element={<AdminOrganizationUsersPage user={auth.user} />} />
                <Route path="/admin/org/tree-view" element={<AdminOrganizationTreePage user={auth.user} />} />
                <Route path="/admin/peer-teams" element={<AdminPeerTeamsPage user={auth.user} />} />
                <Route path="/admin/questions/self" element={<AdminSelfQuestionManagementPage user={auth.user} />} />
                <Route path="/admin/questions/peer" element={<AdminPeerQuestionManagementPage user={auth.user} />} />
                <Route path="/admin/questions/manager-detail" element={<AdminTeamMemberQuestionTeamsPage user={auth.user} />} />
                <Route path="/admin/questions/manager-detail/:teamNodeId" element={<AdminTeamMemberQuestionManagementPage user={auth.user} />} />
                <Route path="/admin/results" element={<AdminResultsPage user={auth.user} />} />
                <Route path="/admin/results/:cycleId" element={<AdminResultUsersPage user={auth.user} />} />
                <Route path="/admin/results/:cycleId/users/:participantId" element={<AdminResultDetailPage user={auth.user} />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppShell>
          </RequireAuth>
        )}
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
