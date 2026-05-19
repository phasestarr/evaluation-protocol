import type {
  AdminOrgTreeResponse,
  AdminQuestionsResponse,
  AdminUserSearchResponse,
  AdminUsersResponse,
  AuthStatus,
  EvaluationSystemStateResponse,
  EvaluationType,
  MembershipRole,
  OrganizationNodeType,
  PeerReviewContextsResponse,
  PeerReviewResponse,
  SelfReviewResponse,
} from "./types";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = init?.body ? { "Content-Type": "application/json", ...(init.headers as Record<string, string> | undefined) } : init?.headers;
  const response = await fetch(url, {
    credentials: "include",
    headers,
    ...init
  });
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new Error(message);
  }
  return response.json();
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  return fetchJson<AuthStatus>("/api/auth/me");
}

export async function logout(): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
  });
}

export async function fetchAdminUsers(): Promise<AdminUsersResponse> {
  return fetchJson<AdminUsersResponse>("/api/admin/users");
}

export async function fetchEvaluationState(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state");
}

export async function startEvaluationCycle(name: string): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state/start", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export async function stopEvaluationCycle(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state/stop", {
    method: "POST"
  });
}

export async function addWhitelistEmail(input: {
  email: string;
  job_title: string;
  display_name: string;
  system_role: string;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/admin/whitelist", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function deleteWhitelistEmail(email: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/whitelist/${encodeURIComponent(email)}`, {
    method: "DELETE"
  });
}

export async function fetchAdminOrgTree(): Promise<AdminOrgTreeResponse> {
  return fetchJson<AdminOrgTreeResponse>("/api/admin/org/tree");
}

export async function searchAdminUsers(query: string): Promise<AdminUserSearchResponse> {
  return fetchJson<AdminUserSearchResponse>(`/api/admin/users/search?q=${encodeURIComponent(query)}`);
}

export async function createOrganizationNode(input: {
  name: string;
  node_type: OrganizationNodeType;
  parent_id: number | null;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/admin/org/nodes", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function deleteOrganizationNode(nodeId: number): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/org/nodes/${nodeId}`, {
    method: "DELETE"
  });
}

export async function createOrganizationMembership(input: {
  user_id: number;
  organization_node_id: number;
  membership_role: MembershipRole;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/admin/org/memberships", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function deleteOrganizationMembership(membershipId: number): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/org/memberships/${membershipId}`, {
    method: "DELETE"
  });
}

export async function fetchAdminQuestions(): Promise<AdminQuestionsResponse> {
  return fetchJson<AdminQuestionsResponse>("/api/admin/questions");
}

export async function createEvaluationQuestion(input: {
  evaluation_type: EvaluationType;
  title: string;
  description: string;
  weight: number | null;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/admin/questions", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function deleteEvaluationQuestion(questionId: number): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/questions/${questionId}`, {
    method: "DELETE"
  });
}

export async function fetchEvaluationGuide(evaluationType: EvaluationType): Promise<{ evaluation_type: EvaluationType; content: string }> {
  return fetchJson<{ evaluation_type: EvaluationType; content: string }>(`/api/admin/evaluation-guides/${evaluationType}`);
}

export async function saveEvaluationGuide(evaluationType: EvaluationType, content: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/evaluation-guides/${evaluationType}`, {
    method: "PUT",
    body: JSON.stringify({ content })
  });
}

export async function fetchSelfReview(): Promise<SelfReviewResponse> {
  return fetchJson<SelfReviewResponse>("/api/evaluations/self");
}

export async function saveSelfReviewAnswer(questionId: number, answerText: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/evaluations/self/answers/${questionId}`, {
    method: "PUT",
    body: JSON.stringify({ answer_text: answerText })
  });
}

export async function fetchPeerReviewContexts(): Promise<PeerReviewContextsResponse> {
  return fetchJson<PeerReviewContextsResponse>("/api/evaluations/peer-contexts");
}

export async function fetchPeerReview(teamNodeId: number): Promise<PeerReviewResponse> {
  return fetchJson<PeerReviewResponse>(`/api/evaluations/peer/${teamNodeId}`);
}

export async function savePeerReviewScores(
  teamNodeId: number,
  scores: Array<{ target_user_id: number; question_id: number; score: number }>,
): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/evaluations/peer/${teamNodeId}/scores`, {
    method: "PUT",
    body: JSON.stringify({ scores })
  });
}
