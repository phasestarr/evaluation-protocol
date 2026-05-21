import { type FormEvent, useEffect, useState } from "react";
import { FileUp } from "lucide-react";
import { fetchPeerTeams, importPeerTeamsCsv } from "../api";
import { StatusMessage } from "../components/StatusMessage";
import type { CurrentUser, PeerTeam } from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

export function AdminPeerTeamsPage({ user }: { user: CurrentUser | null }) {
  const [file, setFile] = useState<File | null>(null);
  const [teams, setTeams] = useState<PeerTeam[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchPeerTeams()
        .then((result) => setTeams(result.teams))
        .catch((error) => setMessage(error instanceof Error ? error.message : "동료평가 팀을 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage("CSV 파일을 선택해 주세요.");
      return;
    }
    setImporting(true);
    setMessage(null);
    try {
      const result = await importPeerTeamsCsv(file);
      setTeams(result.teams);
      setMessage("동료평가 팀 CSV 검증과 반영이 완료되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "동료평가 팀 CSV를 반영하지 못했습니다.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Peer Teams</p>
        <h1>동료평가 팀 관리</h1>
        <p>CSV 파일로 동료평가 팀과 대상자를 반영합니다.</p>
      </div>
      <StatusMessage message={message} />
      <form className="surface-panel import-panel" onSubmit={submitImport}>
        <div>
          <h2>CSV 업로드</h2>
          <p className="muted-copy">BEGIN과 END 사이의 팀명, count, members를 검증해 저장합니다.</p>
        </div>
        <label className="file-drop">
          <FileUp size={24} />
          <span>{file ? file.name : "CSV 파일 선택"}</span>
          <input
            accept=".csv,text/csv"
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="inline-button" type="submit" disabled={importing}>
          {importing ? "반영 중" : "검증 및 반영"}
        </button>
      </form>
      <PeerTeamsTable teams={teams} />
    </section>
  );
}

function PeerTeamsTable({ teams }: { teams: PeerTeam[] }) {
  return (
    <div className="surface-panel evaluation-table-panel">
      <div className="evaluation-table-wrap">
        <table className="evaluation-table">
          <thead>
            <tr>
              <th>team_name</th>
              <th>count</th>
              <th>members</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => (
              <tr key={team.id}>
                <td>{team.name}</td>
                <td>{team.count}</td>
                <td>{team.members.map((member) => member.name).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {teams.length === 0 && <p className="empty-copy">등록된 동료평가 팀이 없습니다.</p>}
    </div>
  );
}
