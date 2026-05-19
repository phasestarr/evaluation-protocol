import type { SystemRole } from "./types";

export function systemRoleLabel(role: SystemRole) {
  return role === "admin" ? "관리자" : "직원";
}
