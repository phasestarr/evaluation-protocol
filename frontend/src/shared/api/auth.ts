import { fetchJson } from "./client";
import type { AuthStatus } from "../types";

export async function fetchAuthStatus(): Promise<AuthStatus> {
  return fetchJson<AuthStatus>("/api/auth/me");
}

export async function logout(): Promise<{ ok: boolean }> {
  return fetchJson<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
  });
}
