import { fetchJson } from "./client";
import type {
  EvaluationProgressResponse,
  ManagerDetailContextsResponse,
  ManagerDetailReviewResponse,
  PeerReviewContextsResponse,
  PeerReviewResponse,
  SelfReviewResponse,
} from "../types";

export async function fetchSelfReview(): Promise<SelfReviewResponse> {
  return fetchJson<SelfReviewResponse>("/api/v1/evaluations/self");
}

export async function fetchEvaluationProgress(): Promise<EvaluationProgressResponse> {
  return fetchJson<EvaluationProgressResponse>("/api/v1/evaluations/progress");
}

export async function saveSelfReviewAnswer(questionId: number, answerText: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/evaluations/self/answers/${questionId}`, {
    method: "PUT",
    body: JSON.stringify({ answer_text: answerText }),
  });
}

export async function fetchPeerReviewContexts(): Promise<PeerReviewContextsResponse> {
  return fetchJson<PeerReviewContextsResponse>("/api/v1/evaluations/peer-contexts");
}

export async function fetchPeerReview(teamNodeId: number): Promise<PeerReviewResponse> {
  return fetchJson<PeerReviewResponse>(`/api/v1/evaluations/peer/${teamNodeId}`);
}

export async function savePeerReviewScores(
  teamNodeId: number,
  scores: Array<{ target_user_id: number; question_id: number; score: number }>,
): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/evaluations/peer/${teamNodeId}/scores`, {
    method: "PUT",
    body: JSON.stringify({ scores }),
  });
}

export async function fetchManagerDetailReviewContexts(): Promise<ManagerDetailContextsResponse> {
  return fetchJson<ManagerDetailContextsResponse>("/api/v1/evaluations/manager-detail-contexts");
}

export async function fetchManagerDetailReview(
  teamNodeId: number,
  targetUserId: number,
): Promise<ManagerDetailReviewResponse> {
  return fetchJson<ManagerDetailReviewResponse>(
    `/api/v1/evaluations/manager-detail/${teamNodeId}/targets/${targetUserId}`,
  );
}

export async function saveManagerDetailReviewScores(
  teamNodeId: number,
  scores: Array<{ target_user_id: number; question_id: number; score: number }>,
): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/evaluations/manager-detail/${teamNodeId}/scores`, {
    method: "PUT",
    body: JSON.stringify({ scores }),
  });
}
