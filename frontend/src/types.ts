import type { ComponentType } from "react";
import type { LucideProps } from "lucide-react";

export type SystemRole = "user" | "admin";
export type IconComponent = ComponentType<LucideProps>;

export interface OrganizationNode {
  id: number;
  name: string;
  node_type: "company" | "head" | "team";
}

export type OrganizationNodeType = OrganizationNode["node_type"];
export type MembershipRole = "member" | "leader";
export type EvaluationType = "self_review" | "peer_review" | "direct_report_review";

export interface CurrentUser {
  email: string;
  display_name: string | null;
  job_title: string | null;
  system_role: SystemRole;
  has_leader_membership: boolean;
  organization_affiliation: string;
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

export interface EvaluationQuestion {
  id: number;
  evaluation_type: EvaluationType;
  title: string;
  description: string | null;
  weight: number | null;
  effective_weight_percent: number | null;
  sort_order: number;
  is_active: boolean;
}

export interface AdminQuestionsResponse {
  questions: EvaluationQuestion[];
}

export interface SelfReviewResponse {
  guide_content: string;
  questions: EvaluationQuestion[];
  answers: Record<string, string>;
}

export interface TeamReviewContext {
  team_node_id: number;
  title: string;
  role_label: string;
}

export interface TeamReviewContextsResponse {
  contexts: TeamReviewContext[];
}

export interface TeamReviewTarget {
  user_id: number;
  display_name: string | null;
  email: string | null;
  job_title: string | null;
  role_label: string;
  affiliation: string;
}

export interface TeamReviewResponse {
  team: {
    id: number;
    title: string;
  };
  guide_content: string;
  questions: EvaluationQuestion[];
  targets: TeamReviewTarget[];
  scores: Record<string, number>;
}
