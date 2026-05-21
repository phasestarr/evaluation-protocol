import { type FormEvent, useEffect, useState } from "react";
import { BarChart3, ClipboardList, FileText, GitBranch, ListChecks, Play, Square, UsersRound } from "lucide-react";
import { fetchAdminReadiness, fetchEvaluationState, startEvaluationCycle, stopEvaluationCycle } from "../api";
import { ActionCard } from "../components/ActionCard";
import { StatusMessage } from "../components/StatusMessage";
import type { AdminReadinessResponse, CompletionStatus, CurrentUser, EvaluationSystemStateResponse } from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

export function AdminHomePage({ user }: { user: CurrentUser | null }) {
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);
  const [readiness, setReadiness] = useState<AdminReadinessResponse | null>(null);
  const [cycleName, setCycleName] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      void loadAdminState(setState, setReadiness, setMessage);
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  const isRunning = state?.status === "running";
  const readinessItems = readiness?.items;
  const canStart = Boolean(readiness?.ready && cycleName.trim());

  async function startCycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!window.confirm("평가를 시작하시겠습니까? 시작하면 현재 사용자, 조직 트리, 문항, 안내문이 스냅샷으로 고정됩니다.")) {
      return;
    }
    setMessage(null);
    try {
      setState(await startEvaluationCycle(cycleName));
      await loadAdminState(setState, setReadiness, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "평가를 시작하지 못했습니다.");
    }
  }

  async function stopCycle() {
    if (!window.confirm("평가를 종료하시겠습니까? 종료하면 현재 스냅샷이 닫히고 이후 평가는 새로 시작해야 합니다.")) {
      return;
    }
    setMessage(null);
    try {
      setState(await stopEvaluationCycle());
      await loadAdminState(setState, setReadiness, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "평가를 종료하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Admin</p>
        <h1>관리자 페이지</h1>
        <p>사용자, 조직, 문항, 평가 결과를 관리합니다.</p>
      </div>
      <StatusMessage message={message} />
      <div className="admin-layout">
        <div className="surface-panel">
          <h2>관리 기능</h2>
          <div className="action-grid two">
            <ActionCard
              to="/admin/org"
              title="조직 관리"
              description={readinessItems?.organization.detail || "CSV 기반 사용자 및 조직 설정"}
              icon={GitBranch}
              completion={completionFromReady(readinessItems?.organization.complete)}
            />
            <ActionCard
              to="/admin/peer-teams"
              title="동료평가 팀 관리"
              description={readinessItems?.peer_teams.detail || "동료평가 팀 설정"}
              icon={UsersRound}
              completion={completionFromReady(readinessItems?.peer_teams.complete)}
            />
          </div>
        </div>
        <div className="surface-panel">
          <h2>문항 관리</h2>
          <div className="action-grid three">
            <ActionCard
              to="/admin/questions/self"
              title="자기평가 문항 관리"
              description={readinessItems?.self_questions.detail || "주관식 자기평가 문항"}
              icon={FileText}
              completion={completionFromReady(readinessItems?.self_questions.complete)}
            />
            <ActionCard
              to="/admin/questions/peer"
              title="동료평가 문항 관리"
              description={readinessItems?.peer_questions.detail || "동료평가 점수 문항"}
              icon={ListChecks}
              completion={completionFromReady(readinessItems?.peer_questions.complete)}
            />
            <ActionCard
              to="/admin/questions/manager-detail"
              title="팀원평가 문항 관리"
              description={readinessItems?.manager_detail_questions.detail || "팀별 팀원평가 점수 문항"}
              icon={ClipboardList}
              completion={completionFromReady(readinessItems?.manager_detail_questions.complete)}
            />
          </div>
        </div>
        <div className="surface-panel">
          <div className="panel-title-row">
            <h2>평가 상태</h2>
            <span className={isRunning ? "running" : undefined}>{isRunning ? "Running" : "Idle"}</span>
          </div>
          {isRunning ? (
            <div className="evaluation-state-row">
              <div>
                <strong>{state?.current_cycle?.name}</strong>
                <p>{state?.current_cycle?.snapshot_date} 기준 스냅샷으로 평가가 진행 중입니다.</p>
              </div>
              <button className="danger-inline-button" type="button" onClick={stopCycle}>
                <Square size={16} />
                종료
              </button>
            </div>
          ) : (
            <form className="evaluation-state-row" onSubmit={startCycle}>
              <div>
                <strong>평가 시작</strong>
                <p>시작 즉시 현재 사용자, 조직 트리, 문항, 안내문을 스냅샷으로 고정합니다.</p>
              </div>
              <input
                value={cycleName}
                placeholder="평가 이름"
                onChange={(event) => setCycleName(event.target.value)}
                required
              />
              <button className="inline-button" type="submit" disabled={!canStart}>
                <Play size={16} />
                시작
              </button>
            </form>
          )}
        </div>
        <div className="surface-panel">
          <h2>결과 열람</h2>
          <div className="action-grid single">
            <ActionCard to="/admin/results" title="결과 열람" description="스냅샷별 평가 결과 확인" icon={BarChart3} />
          </div>
        </div>
      </div>
    </section>
  );
}

async function loadAdminState(
  setState: (state: EvaluationSystemStateResponse) => void,
  setReadiness: (readiness: AdminReadinessResponse) => void,
  setMessage: (message: string | null) => void,
) {
  try {
    const [state, readiness] = await Promise.all([fetchEvaluationState(), fetchAdminReadiness()]);
    setState(state);
    setReadiness(readiness);
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "관리 상태를 불러오지 못했습니다.");
  }
}

function completionFromReady(value: boolean | undefined): CompletionStatus {
  return value ? "complete" : "incomplete";
}
