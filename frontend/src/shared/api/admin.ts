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
} from "../types";

export async function fetchAdminUsers(): Promise<AdminUsersResponse> {
  return fetchJson<AdminUsersResponse>("/api/admin/users");
}

export async function fetchEvaluationState(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state");
}

export async function fetchAdminReadiness(): Promise<AdminReadinessResponse> {
  return fetchJson<AdminReadinessResponse>("/api/admin/readiness");
}

export async function startEvaluationCycle(name: string): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state/start", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function stopEvaluationCycle(): Promise<EvaluationSystemStateResponse> {
  return fetchJson<EvaluationSystemStateResponse>("/api/admin/evaluation-state/stop", {
    method: "POST",
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
    body: JSON.stringify(input),
  });
}

export async function deleteWhitelistEmail(email: string): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/whitelist/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
}

export async function fetchAdminOrgTree(): Promise<AdminOrgTreeResponse> {
  return fetchJson<AdminOrgTreeResponse>("/api/admin/org/tree");
}

export async function importOrganizationCsv(file: File): Promise<OrganizationImportResponse> {
  const body = new FormData();
  body.append("file", file);
  return fetchJson<OrganizationImportResponse>("/api/admin/org/import-csv", {
    method: "POST",
    body,
  });
}

export async function fetchPeerTeams(): Promise<PeerTeamsResponse> {
  return fetchJson<PeerTeamsResponse>("/api/admin/peer-teams");
}

export async function importPeerTeamsCsv(file: File): Promise<PeerTeamsResponse> {
  const body = new FormData();
  body.append("file", file);
  return fetchJson<PeerTeamsResponse>("/api/admin/peer-teams/import-csv", {
    method: "POST",
    body,
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
  organization_node_id?: number | null;
}): Promise<unknown> {
  return fetchJson<unknown>("/api/admin/questions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function fetchManagerDetailQuestionTeams(): Promise<ManagerDetailQuestionTeamsResponse> {
  return fetchJson<ManagerDetailQuestionTeamsResponse>("/api/admin/questions/manager-detail/teams");
}

export async function deleteEvaluationQuestion(questionId: number): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/questions/${questionId}`, {
    method: "DELETE",
  });
}

export async function fetchEvaluationGuide(
  evaluationType: EvaluationType,
): Promise<{ evaluation_type: EvaluationType; content: string }> {
  return fetchJson<{ evaluation_type: EvaluationType; content: string }>(
    `/api/admin/evaluation-guides/${evaluationType}`,
  );
}

export async function saveEvaluationGuide(
  evaluationType: EvaluationType,
  content: string,
): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>(`/api/admin/evaluation-guides/${evaluationType}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}
