import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Trash2 } from "lucide-react";
import {
  createEvaluationQuestion,
  deleteEvaluationQuestion,
  fetchAdminQuestions,
  fetchEvaluationState,
  fetchEvaluationGuide,
  fetchManagerDetailQuestionTeams,
  saveEvaluationGuide,
} from "../api";
import { CompletionBadge } from "../components/ActionCard";
import { MarkdownBlock } from "../components/MarkdownBlock";
import { StatusMessage } from "../components/StatusMessage";
import type {
  AdminQuestionsResponse,
  EvaluationQuestion,
  EvaluationSystemStateResponse,
  EvaluationType,
  ManagerDetailQuestionTeam,
} from "../types";
import type { CurrentUser } from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

const questionPageMeta: Record<EvaluationType, { title: string; eyebrow: string; weighted: boolean }> = {
  self: { title: "자기평가 문항 관리", eyebrow: "Self", weighted: false },
  peer: { title: "동료평가 문항 관리", eyebrow: "Peer", weighted: true },
  manager_detail: { title: "팀원평가 문항 관리", eyebrow: "Manager Detail", weighted: true },
};

export function AdminQuestionsPage({
  user,
  evaluationType,
  organizationNodeId = null,
  contextTitle,
}: {
  user: CurrentUser | null;
  evaluationType: EvaluationType;
  organizationNodeId?: number | null;
  contextTitle?: string;
}) {
  const meta = questionPageMeta[evaluationType];
  const [data, setData] = useState<AdminQuestionsResponse | null>(null);
  const [guide, setGuide] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [weight, setWeight] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);
  const questions = useMemo(
    () =>
      (data?.questions ?? []).filter(
        (question) =>
          question.evaluation_type === evaluationType
          && (question.organization_node_id ?? null) === organizationNodeId,
      ),
    [data?.questions, evaluationType, organizationNodeId],
  );

  useEffect(() => {
    if (user?.system_role === "admin") {
      loadQuestions(setData, setMessage);
      fetchEvaluationState()
        .then(setState)
        .catch((error) => setMessage(error instanceof Error ? error.message : "평가 상태를 불러오지 못했습니다."));
      fetchEvaluationGuide(evaluationType)
        .then((result) => setGuide(result.content))
        .catch((error) => setMessage(error instanceof Error ? error.message : "안내문을 불러오지 못했습니다."));
    }
  }, [evaluationType, user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  const isLocked = state?.status === "running";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    try {
      await createEvaluationQuestion({
        evaluation_type: evaluationType,
        title,
        description,
        weight: meta.weighted ? Number(weight) : null,
        organization_node_id: organizationNodeId,
      });
      setTitle("");
      setDescription("");
      setWeight("");
      await loadQuestions(setData, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "문항을 추가하지 못했습니다.");
    }
  }

  async function saveGuide() {
    setMessage(null);
    try {
      await saveEvaluationGuide(evaluationType, guide);
      setMessage("안내문이 저장되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "안내문을 저장하지 못했습니다.");
    }
  }

  async function removeQuestion(questionId: number) {
    setMessage(null);
    try {
      await deleteEvaluationQuestion(questionId);
      await loadQuestions(setData, setMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "문항을 삭제하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">{meta.eyebrow}</p>
        <h1>{contextTitle ? `${contextTitle} 문항 관리` : meta.title}</h1>
        <p>안내문과 문항을 관리합니다. 안내문은 사용자 평가 화면에 표시됩니다.</p>
      </div>
      <StatusMessage message={message} />
      <section className="surface-panel">
        <div className="panel-title-row">
          <h2>화면 안내문</h2>
          <button className="inline-button" type="button" onClick={saveGuide} disabled={isLocked}>
            저장
          </button>
        </div>
        <textarea
          className="guide-editor"
          value={guide}
          placeholder="Markdown 형식으로 안내문을 입력하세요."
          onChange={(event) => setGuide(event.target.value)}
          disabled={isLocked}
        />
        <MarkdownBlock content={guide} />
      </section>
      <section className="surface-panel">
        <div className="panel-title-row">
          <h2>문항 추가</h2>
          <span>{questions.length}</span>
        </div>
        <div className="question-create-bubble">
          <form className={`question-table-form ${meta.weighted ? "weighted" : ""}`} onSubmit={submit}>
            <input value={title} placeholder="항목" onChange={(event) => setTitle(event.target.value)} required disabled={isLocked} />
            {meta.weighted && (
              <input
                min={1}
                type="number"
                value={weight}
                placeholder="가중치"
                onChange={(event) => setWeight(event.target.value)}
                required
                disabled={isLocked}
              />
            )}
            <button className="inline-button" type="submit" disabled={isLocked}>
              추가
            </button>
            <textarea
              value={description}
              placeholder="설명"
              rows={1}
              onChange={(event) => setDescription(event.target.value)}
              disabled={isLocked}
            />
          </form>
        </div>
        <QuestionTable questions={questions} weighted={meta.weighted} locked={isLocked} onDelete={removeQuestion} />
      </section>
    </section>
  );
}

export function AdminManagerDetailQuestionsPage({ user }: { user: CurrentUser | null }) {
  const [teams, setTeams] = useState<ManagerDetailQuestionTeam[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchManagerDetailQuestionTeams()
        .then((result) => setTeams(result.teams))
        .catch((error) => setMessage(error instanceof Error ? error.message : "팀 목록을 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Manager Detail</p>
        <h1>팀원평가 문항 관리</h1>
        <p>조직도상 Team마다 별도의 팀원평가 문항을 관리합니다.</p>
      </div>
      <StatusMessage message={message} />
      <div className="action-grid">
        {teams.map((team) => (
          <Link className="team-context-row" key={team.id} to={`/admin/questions/manager-detail/${team.id}`}>
            <div>
              <strong>{team.path}</strong>
              <span>{team.question_count}개 문항</span>
            </div>
            <CompletionBadge status={team.question_count > 0 ? "complete" : "incomplete"} />
          </Link>
        ))}
      </div>
      {teams.length === 0 && <p className="empty-copy">등록된 조직 Team이 없습니다.</p>}
    </section>
  );
}

export function AdminManagerDetailQuestionsDetailPage({ user }: { user: CurrentUser | null }) {
  const { teamNodeId } = useParams();
  const numericTeamNodeId = Number(teamNodeId);
  const [teams, setTeams] = useState<ManagerDetailQuestionTeam[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchManagerDetailQuestionTeams()
        .then((result) => setTeams(result.teams))
        .catch((error) => setMessage(error instanceof Error ? error.message : "팀 목록을 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  const team = teams.find((item) => item.id === numericTeamNodeId);
  if (!Number.isFinite(numericTeamNodeId)) {
    return <AccessDeniedPage />;
  }
  if (message && teams.length === 0) {
    return (
      <section className="dashboard">
        <StatusMessage message={message} />
      </section>
    );
  }
  return (
    <AdminQuestionsPage
      user={user}
      evaluationType="manager_detail"
      organizationNodeId={numericTeamNodeId}
      contextTitle={team?.path}
    />
  );
}

function QuestionTable({
  questions,
  weighted,
  locked,
  onDelete,
}: {
  questions: EvaluationQuestion[];
  weighted: boolean;
  locked: boolean;
  onDelete: (questionId: number) => void;
}) {
  return (
    <div className="question-table-wrap">
      <table className="question-table">
        <thead>
          <tr>
            <th>항목</th>
            <th>설명</th>
            {weighted && <th>가중치</th>}
            {weighted && <th>유효가중치</th>}
            <th>관리</th>
          </tr>
        </thead>
        <tbody>
          {questions.map((question) => (
            <tr key={question.id}>
              <td>{question.title}</td>
              <td>{question.description}</td>
              {weighted && <td>{question.weight}</td>}
              {weighted && <td>{question.effective_weight_percent ?? 0}%</td>}
              <td>
                <button className="ghost-icon-button" type="button" title="삭제" onClick={() => onDelete(question.id)} disabled={locked}>
                  <Trash2 size={16} />
                </button>
              </td>
            </tr>
          ))}
          {questions.length === 0 && (
            <tr>
              <td colSpan={weighted ? 5 : 3}>등록된 문항이 없습니다.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

async function loadQuestions(
  setData: (data: AdminQuestionsResponse) => void,
  setMessage: (message: string | null) => void,
) {
  try {
    setData(await fetchAdminQuestions());
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "문항을 불러오지 못했습니다.");
  }
}
