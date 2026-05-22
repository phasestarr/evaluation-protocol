import { type FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ClipboardList, FileText, ListChecks, Trash2 } from "lucide-react";
import {
  createEvaluationQuestion,
  deleteEvaluationQuestion,
  fetchAdminQuestions,
  fetchEvaluationGuide,
  fetchEvaluationState,
  fetchManagerDetailQuestionTeams,
  saveEvaluationGuide,
} from "../../../shared/api/admin";
import { CompletionBadge } from "../../../shared/ui/ActionCard/ActionCard";
import { MarkdownBlock } from "../../../shared/ui/MarkdownBlock/MarkdownBlock";
import { MultilineText } from "../../../shared/ui/MultilineText/MultilineText";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type {
  AdminQuestionsResponse,
  CurrentUser,
  EvaluationQuestion,
  EvaluationSystemStateResponse,
  EvaluationType,
  ManagerDetailQuestionTeam,
} from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import "../../../shared/ui/EvaluationQuestionTable/EvaluationQuestionTable.css";
import "../../peer-evaluation/PeerEvaluationPage.css";
import "./AdminQuestionManagementPage.css";

const questionPageMeta: Record<
  Extract<EvaluationType, "self" | "peer" | "manager_detail">,
  { title: string; eyebrow: string; weighted: boolean; icon: typeof FileText }
> = {
  self: { title: "자기평가 문항 관리", eyebrow: "Self", weighted: false, icon: FileText },
  peer: { title: "동료평가 문항 관리", eyebrow: "Peer", weighted: true, icon: ListChecks },
  manager_detail: { title: "팀원평가 문항 관리", eyebrow: "Manager Detail", weighted: true, icon: ClipboardList },
};

export function AdminQuestionManagementPage({
  user,
  evaluationType,
  organizationNodeId = null,
  contextTitle,
  showGuide = true,
}: {
  user: CurrentUser | null;
  evaluationType: EvaluationType;
  organizationNodeId?: number | null;
  contextTitle?: string;
  showGuide?: boolean;
}) {
  const meta = questionPageMeta[evaluationType];
  const [data, setData] = useState<AdminQuestionsResponse | null>(null);
  const [guide, setGuide] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [weight, setWeight] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);
  const descriptionRef = useAutoResizeTextArea(description);
  const questions = useMemo(
    () =>
      (data?.questions ?? []).filter(
        (question) =>
          question.evaluation_type === evaluationType &&
          (question.organization_node_id ?? null) === organizationNodeId,
      ),
    [data?.questions, evaluationType, organizationNodeId],
  );

  useEffect(() => {
    if (user?.system_role === "admin") {
      void loadQuestions(setData, setMessage);
      fetchEvaluationState()
        .then(setState)
        .catch((error) => setMessage(error instanceof Error ? error.message : "평가 상태를 불러오지 못했습니다."));
      if (showGuide) {
        fetchEvaluationGuide(evaluationType)
          .then((result) => setGuide(result.content))
          .catch((error) => setMessage(error instanceof Error ? error.message : "안내문을 불러오지 못했습니다."));
      }
    }
  }, [evaluationType, showGuide, user?.system_role]);

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
      <PageHeader
        icon={meta.icon}
        eyebrow={meta.eyebrow}
        title={contextTitle ? `${contextTitle} 문항 관리` : meta.title}
        description={
          showGuide
            ? "안내문과 문항을 관리합니다. 안내문은 사용자 평가 화면에 표시됩니다."
            : "이 팀에 적용할 팀원평가 문항을 관리합니다."
        }
      />
      <StatusMessage message={message} />
      {showGuide && <GuideEditor guide={guide} setGuide={setGuide} saveGuide={saveGuide} locked={isLocked} />}
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
              className="question-description-input"
              value={description}
              placeholder="설명"
              rows={1}
              onChange={(event) => setDescription(event.target.value)}
              required
              disabled={isLocked}
              ref={descriptionRef}
            />
          </form>
        </div>
        <QuestionTable questions={questions} weighted={meta.weighted} locked={isLocked} onDelete={removeQuestion} />
      </section>
    </section>
  );
}

export function AdminTeamMemberQuestionTeamsPage({ user }: { user: CurrentUser | null }) {
  const [teams, setTeams] = useState<ManagerDetailQuestionTeam[]>([]);
  const [guide, setGuide] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [state, setState] = useState<EvaluationSystemStateResponse | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchManagerDetailQuestionTeams()
        .then((result) => setTeams(result.teams))
        .catch((error) => setMessage(error instanceof Error ? error.message : "팀 목록을 불러오지 못했습니다."));
      fetchEvaluationState()
        .then(setState)
        .catch((error) => setMessage(error instanceof Error ? error.message : "평가 상태를 불러오지 못했습니다."));
      fetchEvaluationGuide("manager_detail")
        .then((result) => setGuide(result.content))
        .catch((error) => setMessage(error instanceof Error ? error.message : "안내문을 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  const isLocked = state?.status === "running";

  async function saveGuide() {
    setMessage(null);
    try {
      await saveEvaluationGuide("manager_detail", guide);
      setMessage("안내문이 저장되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "안내문을 저장하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <PageHeader
        icon={ClipboardList}
        eyebrow="Manager Detail"
        title="팀원평가 문항 관리"
        description="공통 안내문과 조직도상 Team별 팀원평가 문항을 관리합니다."
      />
      <StatusMessage message={message} />
      <GuideEditor guide={guide} setGuide={setGuide} saveGuide={saveGuide} locked={isLocked} />
      <div className="action-grid">
        {teams.map((team) => (
          <Link className="team-context-row" key={team.id} to={`/admin/questions/manager-detail/${team.id}`}>
            <div>
              <strong>{team.path}</strong>
              <span>{team.question_count}개 문항</span>
            </div>
            <CompletionBadge status={team.complete ? "complete" : "incomplete"} />
          </Link>
        ))}
      </div>
      {teams.length === 0 && <p className="empty-copy">등록된 조직 Team이 없습니다.</p>}
    </section>
  );
}

export function AdminTeamMemberQuestionManagementPage({ user }: { user: CurrentUser | null }) {
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

  if (!Number.isFinite(numericTeamNodeId)) {
    return <AccessDeniedPage />;
  }

  const team = teams.find((item) => item.id === numericTeamNodeId);

  if (message && teams.length === 0) {
    return (
      <section className="dashboard">
        <StatusMessage message={message} />
      </section>
    );
  }

  return (
    <AdminQuestionManagementPage
      user={user}
      evaluationType="manager_detail"
      organizationNodeId={numericTeamNodeId}
      contextTitle={team?.path}
      showGuide={false}
    />
  );
}

function GuideEditor({
  guide,
  setGuide,
  saveGuide,
  locked,
}: {
  guide: string;
  setGuide: (guide: string) => void;
  saveGuide: () => void;
  locked: boolean;
}) {
  const guideRef = useAutoResizeTextArea(guide);

  return (
    <section className="surface-panel">
      <div className="panel-title-row">
        <h2>화면 안내문</h2>
        <button className="inline-button" type="button" onClick={saveGuide} disabled={locked}>
          저장
        </button>
      </div>
      <textarea
        className="guide-editor"
        value={guide}
        placeholder="Markdown 형식으로 안내문을 입력하세요."
        onChange={(event) => setGuide(event.target.value)}
        disabled={locked}
        rows={1}
        ref={guideRef}
      />
      <MarkdownBlock content={guide} />
    </section>
  );
}

function useAutoResizeTextArea(value: string) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    element.style.height = "0px";
    element.style.height = `${element.scrollHeight}px`;
  }, [value]);

  return ref;
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
        <colgroup>
          <col className="question-table-col-title" />
          <col className="question-table-col-description" />
          {weighted && <col className="question-table-col-weight" />}
          {weighted && <col className="question-table-col-effective" />}
          <col className="question-table-col-management" />
        </colgroup>
        <thead>
          <tr>
            <th className="question-table-heading-title">항목</th>
            <th className="question-table-heading-description">설명</th>
            {weighted && <th className="question-table-heading-weight">가중치</th>}
            {weighted && <th className="question-table-heading-effective">유효가중치</th>}
            <th className="question-table-heading-management">관리</th>
          </tr>
        </thead>
        <tbody>
          {questions.map((question) => (
            <tr key={question.id}>
              <td className="question-table-cell-title">
                <strong>{question.title}</strong>
              </td>
              <td className="question-table-cell-description">
                <MultilineText text={question.description} />
              </td>
              {weighted && <td className="question-table-cell-weight">{question.weight}</td>}
              {weighted && <td className="question-table-cell-effective">{question.effective_weight_percent ?? 0}%</td>}
              <td className="question-table-cell-management">
                <button
                  className="ghost-icon-button"
                  type="button"
                  title="삭제"
                  onClick={() => onDelete(question.id)}
                  disabled={locked}
                >
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
