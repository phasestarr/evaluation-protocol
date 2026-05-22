import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckSquare } from "lucide-react";
import { fetchManagerDetailReview, saveManagerDetailReviewScores } from "../../shared/api/evaluations";
import { cellKey, normalizeScoreDraft, weightedQuestionScore, weightedTotal } from "../../shared/lib/weightedScoring";
import { EvaluationQuestionTable } from "../../shared/ui/EvaluationQuestionTable/EvaluationQuestionTable";
import { MarkdownBlock } from "../../shared/ui/MarkdownBlock/MarkdownBlock";
import { MultilineText } from "../../shared/ui/MultilineText/MultilineText";
import { PageHeader } from "../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../shared/ui/StatusMessage/StatusMessage";
import type { ManagerDetailReviewResponse, PeerReviewTarget } from "../../shared/types";
import "./TeamMemberEvaluationPage.css";

export function TeamMemberEvaluationFormPage() {
  const { teamNodeId, targetUserId } = useParams();
  const numericTeamNodeId = Number(teamNodeId);
  const numericTargetUserId = Number(targetUserId);
  const [data, setData] = useState<ManagerDetailReviewResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const questions = useMemo(() => data?.questions ?? [], [data?.questions]);
  const targets = useMemo(() => data?.targets ?? [], [data?.targets]);
  const target = useMemo(
    () => targets.find((item) => item.user_id === numericTargetUserId) ?? null,
    [numericTargetUserId, targets],
  );

  useEffect(() => {
    if (!Number.isFinite(numericTeamNodeId) || !Number.isFinite(numericTargetUserId)) return;
    fetchManagerDetailReview(numericTeamNodeId, numericTargetUserId)
      .then((result) => {
        setData(result);
        setDrafts(Object.fromEntries(Object.entries(result.scores).map(([key, value]) => [key, String(value)])));
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "팀원평가를 불러오지 못했습니다."));
  }, [numericTargetUserId, numericTeamNodeId]);

  async function saveScores() {
    if (!target) {
      setMessage("평가 대상자를 찾을 수 없습니다.");
      return;
    }

    const scores: Array<{ target_user_id: number; question_id: number; score: number }> = [];
    for (const question of questions) {
      const value = drafts[cellKey(target.user_id, question.id)];
      if (value === undefined || value === "") continue;
      const score = Number(value);
      if (!Number.isInteger(score) || score < 0 || score > 100) {
        setMessage("점수는 0부터 100까지의 정수로 입력해 주세요.");
        return;
      }
      scores.push({ target_user_id: target.user_id, question_id: question.id, score });
    }

    setMessage(null);
    try {
      await saveManagerDetailReviewScores(numericTeamNodeId, scores);
      setMessage("저장되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "팀원평가를 저장하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <PageHeader
        icon={CheckSquare}
        descriptionPlacement="full-width"
        childrenPlacement="full-width"
        eyebrow="Manager Detail"
        title={target ? `${[target.job_title, target.display_name || target.email].filter(Boolean).join(" ")} 평가` : data?.team.title || "팀원평가"}
        description={<MarkdownBlock content={data?.guide_content || "문항 설명이 등록되지 않았습니다. 관리자에게 문의해주세요."} />}
      >
        <EvaluationQuestionTable questions={questions} weighted framed />
      </PageHeader>
      <StatusMessage message={message} />
      <div className="manager-detail-target-stack">
        {target && (
          <TargetEvaluationPanel drafts={drafts} questions={questions} setDrafts={setDrafts} target={target} />
        )}
        {data && questions.length === 0 && <p className="empty-copy">등록된 팀원평가 문항이 없습니다.</p>}
        {data && !target && <p className="empty-copy">평가 대상자가 없습니다.</p>}
      </div>
      <div className="toolbar-row">
        <Link className="secondary-inline-button" to="/manager-detail-review">
          목록
        </Link>
        <button className="inline-button" type="button" onClick={saveScores}>
          저장
        </button>
      </div>
    </section>
  );
}

function TargetLabel({ target }: { target: PeerReviewTarget }) {
  return (
    <div className="target-label">
      <strong>{[target.job_title, target.display_name || target.email].filter(Boolean).join(" ")}</strong>
      <span>{target.affiliation}</span>
    </div>
  );
}

function TargetEvaluationPanel({
  drafts,
  questions,
  setDrafts,
  target,
}: {
  drafts: Record<string, string>;
  questions: ManagerDetailReviewResponse["questions"];
  setDrafts: (value: (current: Record<string, string>) => Record<string, string>) => void;
  target: PeerReviewTarget;
}) {
  const total = weightedTotal(target, questions, drafts);
  return (
    <section className="surface-panel manager-detail-target-card">
      <div className="manager-detail-target-header">
        <TargetLabel target={target} />
        <span className="manager-detail-total-chip">{total.toFixed(2)} / 100</span>
      </div>
      <div className="manager-detail-question-wrap">
        <table className="manager-detail-question-table">
          <thead>
            <tr>
              <th>문항</th>
              <th>설명</th>
              <th>입력 점수</th>
              <th>유효가중치</th>
              <th>환산 점수</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((question) => (
              <tr key={question.id}>
                <td>
                  <strong>{question.title}</strong>
                </td>
                <td>
                  <MultilineText text={question.description} />
                </td>
                <td>
                  <input
                    inputMode="numeric"
                    max={100}
                    min={0}
                    step={1}
                    type="number"
                    value={drafts[cellKey(target.user_id, question.id)] ?? ""}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [cellKey(target.user_id, question.id)]: normalizeScoreDraft(event.target.value),
                      }))
                    }
                  />
                </td>
                <td>{question.effective_weight_percent ?? 0}%</td>
                <td>{weightedQuestionScore(target, question, drafts).toFixed(2)}</td>
              </tr>
            ))}
            <tr className="manager-detail-total-row">
              <th colSpan={4}>총합 / 100</th>
              <td>{total.toFixed(2)} / 100</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
