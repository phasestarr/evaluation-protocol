import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPeerReview, savePeerReviewScores } from "../api";
import { MarkdownBlock } from "../components/MarkdownBlock";
import type { EvaluationQuestion, PeerReviewResponse, PeerReviewTarget } from "../types";

export function PeerReviewDetailPage() {
  const { teamNodeId } = useParams();
  const numericTeamNodeId = Number(teamNodeId);
  const [data, setData] = useState<PeerReviewResponse | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const questions = useMemo(() => data?.questions ?? [], [data?.questions]);
  const targets = useMemo(() => data?.targets ?? [], [data?.targets]);

  useEffect(() => {
    if (!Number.isFinite(numericTeamNodeId)) return;
    fetchPeerReview(numericTeamNodeId)
      .then((result) => {
        setData(result);
        setDrafts(Object.fromEntries(Object.entries(result.scores).map(([key, value]) => [key, String(value)])));
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "동료평가를 불러오지 못했습니다."));
  }, [numericTeamNodeId]);

  async function saveScores() {
    const scores: Array<{ target_user_id: number; question_id: number; score: number }> = [];
    for (const target of targets) {
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
    }
    setMessage(null);
    try {
      await savePeerReviewScores(numericTeamNodeId, scores);
      setMessage("저장되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "동료평가를 저장하지 못했습니다.");
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Peer Review</p>
        <h1>{data?.team.title || "동료평가"}</h1>
        <MarkdownBlock content={data?.guide_content || "문항 설명이 등록되지 않았습니다. 관리자에게 문의해주세요."} />
      </div>
      <div className="toolbar-row">
        <Link className="secondary-inline-button" to="/peer-review">
          목록
        </Link>
        <button className="inline-button" type="button" onClick={saveScores}>
          저장
        </button>
      </div>
      {message && <div className="admin-message">{message}</div>}
      <div className="surface-panel evaluation-table-panel">
        <div className="evaluation-table-wrap">
          <table className="evaluation-table">
            <thead>
              <tr>
                <th>대상자</th>
                {questions.map((question) => (
                  <th key={question.id}>
                    <strong>{question.title}</strong>
                    <span>{question.effective_weight_percent ?? 0}%</span>
                  </th>
                ))}
                <th>총점</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((target) => (
                <tr key={target.user_id}>
                  <td>
                    <TargetLabel target={target} />
                  </td>
                  {questions.map((question) => (
                    <td key={question.id}>
                      <input
                        inputMode="numeric"
                        max={100}
                        min={0}
                        type="number"
                        value={drafts[cellKey(target.user_id, question.id)] ?? ""}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [cellKey(target.user_id, question.id)]: event.target.value,
                          }))
                        }
                      />
                    </td>
                  ))}
                  <td className="score-total">{weightedTotal(target, questions, drafts).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && questions.length === 0 && <p className="empty-copy">등록된 동료평가 문항이 없습니다.</p>}
        {data && targets.length === 0 && <p className="empty-copy">평가 대상자가 없습니다.</p>}
      </div>
    </section>
  );
}

function TargetLabel({ target }: { target: PeerReviewTarget }) {
  return (
    <div className="target-label">
      <strong>{[target.job_title, target.display_name || target.email].filter(Boolean).join(" ")}</strong>
      <span>
        {target.affiliation} · {target.role_label}
      </span>
    </div>
  );
}

function weightedTotal(
  target: PeerReviewTarget,
  questions: EvaluationQuestion[],
  drafts: Record<string, string>,
) {
  return questions.reduce((total, question) => {
    const raw = drafts[cellKey(target.user_id, question.id)];
    const score = raw ? Number(raw) : 0;
    const effectiveWeight = question.effective_weight_percent ?? 0;
    if (!Number.isFinite(score)) return total;
    return total + score * (effectiveWeight / 100);
  }, 0);
}

function cellKey(targetUserId: number, questionId: number) {
  return `${targetUserId}:${questionId}`;
}
