import { fetchJson } from "./client";
import type { AuthStatus } from "../types";

export async function fetchAuthStatus(): Promise<AuthStatus> {
  return fetchJson<AuthStatus>("/api/v1/auth/me");
}

export async function logout(): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>("/api/v1/auth/logout", {
    method: "POST",
  });
}
