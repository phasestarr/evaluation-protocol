import type { EvaluationQuestion, PeerReviewTarget } from "../types";

export function normalizeScoreDraft(value: string) {
  if (value === "") return "";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  if (numeric > 100) return "100";
  if (numeric < 0) return "0";
  return value;
}

export function weightedQuestionScore(
  target: PeerReviewTarget,
  question: EvaluationQuestion,
  drafts: Record<string, string>,
) {
  const raw = drafts[cellKey(target.user_id, question.id)];
  const score = raw ? Number(raw) : 0;
  const effectiveWeight = question.effective_weight_percent ?? 0;
  if (!Number.isFinite(score)) return 0;
  return score * (effectiveWeight / 100);
}

export function weightedTotal(
  target: PeerReviewTarget,
  questions: EvaluationQuestion[],
  drafts: Record<string, string>,
) {
  return questions.reduce((total, question) => total + weightedQuestionScore(target, question, drafts), 0);
}

export function averageTotal(
  targets: PeerReviewTarget[],
  questions: EvaluationQuestion[],
  drafts: Record<string, string>,
) {
  if (targets.length === 0) return 0;
  return targets.reduce((sum, target) => sum + weightedTotal(target, questions, drafts), 0) / targets.length;
}

export function cellKey(targetUserId: number, questionId: number) {
  return `${targetUserId}:${questionId}`;
}
