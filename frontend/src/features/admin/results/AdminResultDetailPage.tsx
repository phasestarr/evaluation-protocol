import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BarChart3, ClipboardList, FileText, UsersRound } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { cellKey } from "../../../shared/lib/weightedScoring";
import { fetchResultParticipant } from "../../../shared/api/admin";
import { EvaluationQuestionTable } from "../../../shared/ui/EvaluationQuestionTable/EvaluationQuestionTable";
import { MarkdownBlock } from "../../../shared/ui/MarkdownBlock/MarkdownBlock";
import { MultilineText } from "../../../shared/ui/MultilineText/MultilineText";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, EvaluationQuestion, ResultParticipantResponse, ResultReviewSection, ResultReviewerRow } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import "../../peer-evaluation/PeerEvaluationPage.css";
import "./AdminResultsPage.css";

export function AdminResultDetailPage({ user }: { user: CurrentUser | null }) {
  const { cycleId, participantId } = useParams();
  const numericCycleId = Number(cycleId);
  const numericParticipantId = Number(participantId);
  const [data, setData] = useState<ResultParticipantResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const displayName = useMemo(
    () => (data ? [data.user.title, data.user.name].filter(Boolean).join(" ") : "평가 결과"),
    [data],
  );

  useEffect(() => {
    if (user?.system_role !== "admin" || !Number.isFinite(numericCycleId) || !Number.isFinite(numericParticipantId)) return;
    fetchResultParticipant(numericCycleId, numericParticipantId)
      .then(setData)
      .catch((error) => setMessage(error instanceof Error ? error.message : "평가 결과를 불러오지 못했습니다."));
  }, [numericCycleId, numericParticipantId, user?.system_role]);

  if (user?.system_role !== "admin" || !Number.isFinite(numericCycleId) || !Number.isFinite(numericParticipantId)) {
    return <AccessDeniedPage />;
  }

  return (
    <section className="dashboard">
      <PageHeader
        icon={BarChart3}
        eyebrow="Results"
        title={displayName}
        description={data ? `${data.cycle.name} / ${data.cycle.snapshot_date}` : "평가 결과를 불러오는 중입니다."}
        aside={(
          <Link className="secondary-inline-button" to={`/admin/results/${numericCycleId}`}>
            <ArrowLeft size={16} />
            사용자 목록
          </Link>
        )}
      />
      <StatusMessage message={message} />

      <section className="surface-panel">
        <div className="panel-title-row">
          <h2>자기평가</h2>
          <FileText size={18} />
        </div>
        <MarkdownBlock content={data?.self_review.guide_content || "안내문이 없습니다."} />
        <div className="result-answer-list">
          {data?.self_review.items.map((item) => (
            <section className="result-answer-card" key={item.question.id}>
              <EvaluationQuestionTable questions={[item.question]} weighted={false} framed />
              <div className="result-answer-copy">{item.answer_text || "답변 없음"}</div>
            </section>
          ))}
        </div>
        {data && data.self_review.items.length === 0 && <p className="empty-copy">자기평가 문항이 없습니다.</p>}
      </section>

      <section className="result-page-stack">
        <div className="surface-panel">
          <div className="panel-title-row">
            <h2>동료평가</h2>
            <UsersRound size={18} />
          </div>
          <div className="result-section-stack">
            {data?.peer_reviews.map((section) => (
              <PeerReviewSection key={`peer:${section.team.id}`} section={section} />
            ))}
          </div>
          {data && data.peer_reviews.length === 0 && <p className="empty-copy">동료평가 결과가 없습니다.</p>}
        </div>

        <div className="surface-panel">
          <div className="panel-title-row">
            <h2>팀원평가</h2>
            <ClipboardList size={18} />
          </div>
          <div className="result-section-stack">
            {data?.manager_detail_reviews.map((section) => (
              <ManagerDetailReviewSection key={`manager:${section.team.id}`} section={section} />
            ))}
          </div>
          {data && data.manager_detail_reviews.length === 0 && <p className="empty-copy">팀원평가 결과가 없습니다.</p>}
        </div>
      </section>
    </section>
  );
}

function PeerReviewSection({ section }: { section: ResultReviewSection }) {
  return (
    <section className="surface-panel result-section-card">
      <div>
        <h3>{section.team.title}</h3>
      </div>
      <MarkdownBlock content={section.guide_content || "안내문이 없습니다."} />
      <EvaluationQuestionTable questions={section.questions} weighted framed />
      <div className="surface-panel evaluation-table-panel">
        <div className="evaluation-table-wrap">
          <table className="evaluation-table">
            <thead>
              <tr>
                <th>평가자</th>
                {section.questions.map((question) => (
                  <th key={question.id}>
                    <strong>{question.title}</strong>
                    <span>{question.effective_weight_percent ?? 0}%</span>
                  </th>
                ))}
                <th>총점</th>
              </tr>
            </thead>
            <tbody>
              {section.reviewers.map((reviewer) => (
                <tr key={reviewer.user_id}>
                  <td>
                    <ReviewerLabel reviewer={reviewer} />
                  </td>
                  {section.questions.map((question) => (
                    <td key={question.id}>{section.scores[cellKey(reviewer.user_id, question.id)] ?? "-"}</td>
                  ))}
                  <td className="score-total">{weightedScoreTotal(section.questions, reviewer.user_id, section.scores).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {section.reviewers.length === 0 && <p className="empty-copy">표시할 평가자가 없습니다.</p>}
      </div>
    </section>
  );
}

function ManagerDetailReviewSection({ section }: { section: ResultReviewSection }) {
  return (
    <section className="surface-panel result-section-card">
      <div>
        <h3>{section.team.title}</h3>
      </div>
      <MarkdownBlock content={section.guide_content || "안내문이 없습니다."} />
      <EvaluationQuestionTable questions={section.questions} weighted framed />
      <div className="surface-panel evaluation-table-panel">
        <div className="evaluation-table-wrap">
          <table className="evaluation-table result-question-matrix">
            <thead>
              <tr>
                <th className="result-question-column">문항</th>
                {section.reviewers.map((reviewer) => (
                  <th key={reviewer.user_id} className="result-reviewer-column">
                    <ReviewerLabel reviewer={reviewer} contextTitle={section.team.title} />
                  </th>
                ))}
                <th className="result-average-column">평균점수</th>
              </tr>
            </thead>
            <tbody>
              {section.questions.map((question) => (
                <tr key={question.id}>
                  <td className="result-question-meta">
                    <strong>{question.title}</strong>
                    {question.description && (
                      <span>
                        <MultilineText text={question.description} />
                      </span>
                    )}
                    <small>유효가중치 {question.effective_weight_percent ?? 0}%</small>
                  </td>
                  {section.reviewers.map((reviewer) => (
                    <td key={reviewer.user_id} className="result-score-cell">
                      {section.scores[cellKey(reviewer.user_id, question.id)] ?? "-"}
                    </td>
                  ))}
                  <td className="score-total result-average-cell">
                    {averageQuestionScore(section.reviewers, question.id, section.scores)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {section.reviewers.length === 0 && <p className="empty-copy">표시할 평가자가 없습니다.</p>}
      </div>
    </section>
  );
}

function ReviewerLabel({ reviewer, contextTitle }: { reviewer: ResultReviewerRow; contextTitle?: string }) {
  const roleLabel = displayReviewerRoleLabel(reviewer, contextTitle);
  return (
    <div className="result-reviewer-label">
      <strong>{[reviewer.job_title, reviewer.display_name || reviewer.email].filter(Boolean).join(" ")}</strong>
      {roleLabel ? <span>{roleLabel}</span> : null}
    </div>
  );
}

function weightedScoreTotal(
  questions: EvaluationQuestion[],
  reviewerUserId: number,
  scores: Record<string, number>,
) {
  const totalWeight = questions.reduce((sum, question) => sum + (question.weight ?? 0), 0);
  if (totalWeight <= 0) return 0;
  return questions.reduce((sum, question) => {
    const score = scores[cellKey(reviewerUserId, question.id)] ?? 0;
    return sum + score * ((question.weight ?? 0) / totalWeight);
  }, 0);
}

function averageQuestionScore(
  reviewers: ResultReviewerRow[],
  questionId: number,
  scores: Record<string, number>,
) {
  const values = reviewers
    .map((reviewer) => scores[cellKey(reviewer.user_id, questionId)])
    .filter((value): value is number => typeof value === "number");
  if (values.length === 0) {
    return "-";
  }
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  return average.toFixed(2);
}

function displayReviewerRoleLabel(reviewer: ResultReviewerRow, contextTitle?: string) {
  const roleLabel = reviewer.role_label.trim();
  if (!roleLabel) {
    return "";
  }

  if (roleLabel === "본부" && contextTitle) {
    const headPath = contextTitle.split(" > ").slice(0, -1).join(" > ");
    const matchedHeadLine = reviewer.affiliation
      .split("\n")
      .find((line) => headPath && line.startsWith(`${headPath} > `));
    if (matchedHeadLine?.endsWith("> LEADER")) {
      return "본부장";
    }
    if (matchedHeadLine?.endsWith("> MEMBER")) {
      return "팀원";
    }
  }

  return roleLabel
    .split(",")
    .map((token) => token.trim())
    .filter(Boolean)
    .map((token) => {
      if (token === "LEADER") return "팀장";
      if (token === "MEMBER") return "팀원";
      return token;
    })
    .join(", ");
}
