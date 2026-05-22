import { fetchJson } from "./client";
import type {
  AdminOrgTreeResponse,
  AdminQuestionsResponse,
  AdminReadinessResponse,
  AdminUsersResponse,
  EvaluationSystemStateResponse,
  EvaluationType,
  ManagerDetailQuestionTeamsResponse,
  OrganizationImportResponse,
  PeerTeamsResponse,
  ResultCycleUsersResponse,
  ResultCyclesResponse,
  ResultParticipantResponse,
  SystemRole,
} from "../types";

export async function fetchAdminUsers(): Promise<AdminUsersResponse> {
  return fetchJson<AdminUsersResponse>("/api/v1/admin/users");
}

export async function fetchEvaluationState(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/v1/admin/evaluation-state");
}

export async function fetchAdminReadiness(): Promise<AdminReadinessResponse> {
  return fetchJson<AdminReadinessResponse>("/api/v1/admin/readiness");
}

export async function startEvaluationCycle(name: string): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/v1/admin/evaluation-state/start", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function stopEvaluationCycle(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/v1/admin/evaluation-state/stop", {
    method: "POST",
  });
}

export async function addWhitelistEmail(input: {
  email: string;
  job_title: string;
  display_name: string;
  system_role: string;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/v1/admin/whitelist", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteWhitelistEmail(email: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/admin/whitelist/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
}

export async function fetchAdminOrgTree(): Promise<AdminOrgTreeResponse> {
  return fetchJson<AdminOrgTreeResponse>("/api/v1/admin/org/tree");
}

export async function updateOrgUserSystemRole(userId: number, systemRole: SystemRole): Promise<unknown> {
  return fetchJson<unknown>(`/api/v1/admin/org/users/${userId}/system-role`, {
    method: "PUT",
    body: JSON.stringify({ system_role: systemRole }),
  });
}

export async function importOrganizationCsv(file: File): Promise<OrganizationImportResponse> {
  const body = new FormData();
  body.append("file", file);
  return fetchJson<OrganizationImportResponse>("/api/v1/admin/org/import-csv", {
    method: "POST",
    body,
  });
}

export async function fetchPeerTeams(): Promise<PeerTeamsResponse> {
  return fetchJson<PeerTeamsResponse>("/api/v1/admin/peer-teams");
}

export async function importPeerTeamsCsv(file: File): Promise<PeerTeamsResponse> {
  const body = new FormData();
  body.append("file", file);
  return fetchJson<PeerTeamsResponse>("/api/v1/admin/peer-teams/import-csv", {
    method: "POST",
    body,
  });
}

export async function fetchAdminQuestions(): Promise<AdminQuestionsResponse> {
  return fetchJson<AdminQuestionsResponse>("/api/v1/admin/questions");
}

export async function createEvaluationQuestion(input: {
  evaluation_type: EvaluationType;
  title: string;
  description: string;
  weight: number | null;
  organization_node_id?: number | null;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/v1/admin/questions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function fetchManagerDetailQuestionTeams(): Promise<ManagerDetailQuestionTeamsResponse> {
  return fetchJson<ManagerDetailQuestionTeamsResponse>("/api/v1/admin/questions/manager-detail/teams");
}

export async function deleteEvaluationQuestion(questionId: number): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/admin/questions/${questionId}`, {
    method: "DELETE",
  });
}

export async function fetchEvaluationGuide(
  evaluationType: EvaluationType,
): Promise<{ evaluation_type: EvaluationType; content: string }> {
  return fetchJson<{ evaluation_type: EvaluationType; content: string }>(
    `/api/v1/admin/evaluation-guides/${evaluationType}`,
  );
}

export async function saveEvaluationGuide(
  evaluationType: EvaluationType,
  content: string,
): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/v1/admin/evaluation-guides/${evaluationType}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export async function fetchResultCycles(): Promise<ResultCyclesResponse> {
  return fetchJson<ResultCyclesResponse>("/api/v1/admin/results/cycles");
}

export async function fetchResultCycleUsers(cycleId: number): Promise<ResultCycleUsersResponse> {
  return fetchJson<ResultCycleUsersResponse>(`/api/v1/admin/results/cycles/${cycleId}/users`);
}

export async function fetchResultParticipant(cycleId: number, participantId: number): Promise<ResultParticipantResponse> {
  return fetchJson<ResultParticipantResponse>(`/api/v1/admin/results/cycles/${cycleId}/users/${participantId}`);
}
