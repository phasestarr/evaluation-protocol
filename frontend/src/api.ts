import type { AdminOrgTreeResponse, AdminUserSearchResponse, AdminUsersResponse, AuthStatus, MembershipRole, OrganizationNodeType } from "./types";

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

export async function addWhitelistEmail(input: {
  email: string;
  job_title: string;
  display_name: string;
  system_role: string;
  organization_role: string;
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
