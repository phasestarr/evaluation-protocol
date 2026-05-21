import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileUp, GitBranch, Table2 } from "lucide-react";
import { fetchEvaluationState, importOrganizationCsv } from "../../../shared/api/admin";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, EvaluationSystemStateResponse } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";

export function AdminOrganizationImportPage({ user }: { user: CurrentUser | null }) {
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchEvaluationState()
        .then(setState)
        .catch((error) => setMessage(error instanceof Error ? error.message : "평가 상태를 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  const isLocked = state?.status === "running";

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (importing) return;
    if (isLocked) {
      setMessage("평가가 진행 중일 때는 CSV를 반영할 수 없습니다.");
      return;
    }
    if (!file) {
      setMessage("CSV 파일을 선택해 주세요.");
      return;
    }
    setImporting(true);
    setMessage(null);
    try {
      await importOrganizationCsv(file);
      setMessage("CSV 검증과 조직 반영이 완료되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CSV를 반영하지 못했습니다.");
    } finally {
      setImporting(false);
      setFile(null);
      setFileInputKey((value) => value + 1);
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Organization</p>
        <h1>조직 관리</h1>
        <p>CSV 파일로 사용자 화이트리스트와 조직 트리를 한 번에 반영합니다.</p>
      </div>
      <StatusMessage message={message} />
      {isLocked && <StatusMessage message="평가가 진행 중이므로 CSV 업로드와 검증이 잠겨 있습니다." />}
      <form className="surface-panel import-panel" onSubmit={submitImport}>
        <div>
          <h2>CSV 업로드</h2>
          <p className="muted-copy">COMPANY 행부터 읽고, LEADER/MEMBER 속성으로 조직 역할을 배정합니다.</p>
        </div>
        <label className={`file-drop ${isLocked || importing ? "disabled" : ""}`}>
          <FileUp size={24} />
          <span>{file ? file.name : "CSV 파일 선택"}</span>
          <input
            key={fileInputKey}
            accept=".csv,text/csv"
            type="file"
            disabled={isLocked || importing}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="inline-button" type="submit" disabled={importing || isLocked}>
          {importing ? "반영 중" : "검증 및 반영"}
        </button>
      </form>
      <div className="action-grid two">
        <Link className="action-card" to="/admin/org/users">
          <div className="action-icon">
            <Table2 size={24} />
          </div>
          <div>
            <h3>사용자 확인</h3>
            <p>CSV 사용자 목록 확인</p>
          </div>
        </Link>
        <Link className="action-card" to="/admin/org/tree-view">
          <div className="action-icon">
            <GitBranch size={24} />
          </div>
          <div>
            <h3>조직 트리 확인</h3>
            <p>반영된 조직 트리 확인</p>
          </div>
        </Link>
      </div>
    </section>
  );
}
