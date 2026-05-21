import { FormEvent, useEffect, useMemo, useState } from "react";
import { Trash2, UserPlus } from "lucide-react";
import { addWhitelistEmail, deleteWhitelistEmail, fetchAdminUsers, fetchEvaluationState } from "../api";
import { StatusMessage } from "../components/StatusMessage";
import { systemRoleLabel } from "../labels";
import type { AdminUsersResponse, CurrentUser, EvaluationSystemStateResponse, SystemRole } from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

export function AdminUsersPage({ user }: { user: CurrentUser | null }) {
  const [data, setData] = useState<AdminUsersResponse | null>(null);
  const [email, setEmail] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [systemRole, setSystemRole] = useState<SystemRole>("user");
  const [message, setMessage] = useState<string | null>(null);
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);
  const sortedWhitelist = useMemo(
    () => [...(data?.whitelist ?? [])].sort((a, b) => a.email.localeCompare(b.email)),
    [data?.whitelist],
  );
  const sortedUsers = useMemo(
    () =>
      [...(data?.users ?? [])].sort((a, b) =>
        (a.display_name || a.email).localeCompare(b.display_name || b.email, "ko"),
      ),
    [data?.users],
  );

  useEffect(() => {
    if (user?.system_role === "admin") {
      loadUsers(setData, setMessage);
      fetchEvaluationState()
        .then(setState)
        .catch((error) => setMessage(error instanceof Error ? error.message : "평가 상태를 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  const isLocked = state?.status === "running";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      await addWhitelistEmail({
        email,
        job_title: jobTitle,
        display_name: displayName,
        system_role: systemRole
      });
      setEmail("");
      setJobTitle("");
      setDisplayName("");
      setSystemRole("user");
      await loadUsers(setData, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to add email");
    }
  }

  async function removeWhitelistEmail(targetEmail: string) {
    setMessage(null);
    try {
      await deleteWhitelistEmail(targetEmail);
      await loadUsers(setData, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to delete email");
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Admin</p>
        <h1>사용자 추가</h1>
        <p>Microsoft OAuth 로그인 허용 대상과 실제 로그인된 사용자를 분리해서 관리합니다.</p>
      </div>

      <div className="admin-two-column">
        <section className="surface-panel">
          <div className="panel-title-row">
            <h2>화이트리스트</h2>
            <span>{data?.whitelist.length ?? 0}</span>
          </div>
          <form className="admin-form vertical" onSubmit={submit}>
            <input
              type="email"
              value={email}
              placeholder="name@example.com"
              onChange={(event) => setEmail(event.target.value)}
              required
              disabled={isLocked}
            />
            <input
              value={jobTitle}
              placeholder="직급"
              onChange={(event) => setJobTitle(event.target.value)}
              required
              disabled={isLocked}
            />
            <input
              value={displayName}
              placeholder="이름"
              onChange={(event) => setDisplayName(event.target.value)}
              required
              disabled={isLocked}
            />
            <div className="role-select-grid">
              <select value={systemRole} onChange={(event) => setSystemRole(event.target.value as SystemRole)} disabled={isLocked}>
                <option value="admin">관리자</option>
                <option value="user">직원</option>
              </select>
            </div>
            <button className="inline-button" type="submit" disabled={isLocked}>
              <UserPlus size={17} />
              추가
            </button>
          </form>
          <StatusMessage message={message} />
          <div className="list-stack">
            {sortedWhitelist.map((entry) => (
              <div className="list-row" key={entry.id}>
                <strong>{entry.email}</strong>
                <button className="ghost-icon-button" type="button" title="삭제" onClick={() => removeWhitelistEmail(entry.email)} disabled={isLocked}>
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            {data && sortedWhitelist.length === 0 && <p className="empty-copy">허용된 이메일이 없습니다.</p>}
          </div>
        </section>

        <section className="surface-panel">
          <div className="panel-title-row">
            <h2>시스템 사용자</h2>
            <span>{data?.users.length ?? 0}</span>
          </div>
          <div className="list-stack">
            {sortedUsers.map((row) => (
              <div className="user-row" key={row.id}>
                <div>
                  <strong>{row.display_name || row.email}</strong>
                  <span>{[row.job_title, row.email].filter(Boolean).join(" · ")}</span>
                </div>
                <div className="role-stack compact">
                  <span className="role-pill">{systemRoleLabel(row.system_role)}</span>
                </div>
              </div>
            ))}
            {data && sortedUsers.length === 0 && <p className="empty-copy">아직 로그인 또는 조직 배정된 사용자가 없습니다.</p>}
          </div>
        </section>
      </div>
    </section>
  );
}

async function loadUsers(
  setData: (data: AdminUsersResponse) => void,
  setMessage: (message: string | null) => void,
) {
  try {
    setData(await fetchAdminUsers());
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "Failed to load users");
  }
}
