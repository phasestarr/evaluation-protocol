import type { ComponentType } from "react";
import type { LucideProps } from "lucide-react";

export type SystemRole = "user" | "admin";
export type OrganizationRole = "staff" | "manager";
export type IconComponent = ComponentType<LucideProps>;

export interface OrganizationNode {
  id: number;
  name: string;
  node_type: "company" | "head" | "team";
}

export type OrganizationNodeType = OrganizationNode["node_type"];
export type MembershipRole = "member" | "leader";

export interface CurrentUser {
  email: string;
  display_name: string | null;
  system_role: SystemRole;
  organization_role: OrganizationRole;
  organization_node: OrganizationNode | null;
}

export interface AuthStatus {
  authenticated: boolean;
  user: CurrentUser | null;
}

export type Action = {
  to: string;
  title: string;
  description: string;
  icon: IconComponent;
  tone?: "default" | "admin";
};

export interface WhitelistEntry {
  id: number;
  email: string;
  created_at: string | null;
}

export interface AdminUser {
  id: number;
  email: string;
  display_name: string | null;
  job_title: string | null;
  system_role: SystemRole;
  organization_role: OrganizationRole;
  organization_node_id: number | null;
}

export interface OrganizationMembership {
  id: number;
  user_id: number;
  email: string | null;
  display_name: string | null;
  job_title: string | null;
  organization_node_id: number;
  membership_role: MembershipRole;
}

export interface AdminOrganizationNode extends OrganizationNode {
  parent_id: number | null;
  memberships: OrganizationMembership[];
}

export interface AdminUsersResponse {
  whitelist: WhitelistEntry[];
  users: AdminUser[];
}

export interface AdminUserSearchResponse {
  users: AdminUser[];
}

export interface AdminOrgTreeResponse {
  nodes: AdminOrganizationNode[];
  users: AdminUser[];
  whitelist: WhitelistEntry[];
}
