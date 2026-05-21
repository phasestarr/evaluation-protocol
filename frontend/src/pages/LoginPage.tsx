import { Navigate, useLocation } from "react-router-dom";
import { Shield } from "lucide-react";

const loginEyebrow = import.meta.env.VITE_LOGIN_EYEBROW || "Evaluation Protocol";

export function LoginPage({ authenticated }: { authenticated: boolean }) {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const error = searchParams.get("auth_error");
  const next = searchParams.get("next") || "/";

  if (authenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="brand-mark">
          <Shield size={26} />
        </div>
        <p className="eyebrow">{loginEyebrow}</p>
        <h1>인사평가 시스템</h1>
        <p className="login-copy">사내 Microsoft 계정으로 로그인합니다.</p>
        {error && <div className="auth-error">{error}</div>}
        <a className="primary-button" href={`/api/v1/auth/microsoft/start?redirect_after=${encodeURIComponent(next)}`}>
          Microsoft로 로그인
        </a>
      </section>
    </main>
  );
}
