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
export type EvaluationType = "self" | "peer" | "manager_detail";

export interface CurrentUser {
  email: string;
  display_name: string | null;
  job_title: string | null;
  system_role: SystemRole;
  has_leader_membership: boolean;
  has_manager_detail_access: boolean;
  organization_affiliation: string;
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
  completion?: CompletionStatus;
};

export type CompletionStatus = "complete" | "incomplete";

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
}

export interface EvaluationCycleSummary {
  id: number;
  name: string;
  snapshot_date: string;
  status: "running" | "closed";
  started_at: string | null;
  ended_at: string | null;
}

export interface EvaluationSystemStateResponse {
  status: "idle" | "running";
  current_cycle: EvaluationCycleSummary | null;
}

export interface ReadinessItem {
  complete: boolean;
  label: string;
  detail: string;
}

export interface ManagerDetailReadinessItem extends ReadinessItem {
  teams: Array<{
    id: number;
    name: string;
    complete: boolean;
    question_count: number;
  }>;
}

export interface AdminReadinessResponse {
  ready: boolean;
  items: {
    organization: ReadinessItem;
    peer_teams: ReadinessItem;
    self_questions: ReadinessItem;
    peer_questions: ReadinessItem;
    manager_detail_questions: ManagerDetailReadinessItem;
  };
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

export interface AdminOrgTreeResponse {
  nodes: AdminOrganizationNode[];
  users: AdminUser[];
  imported_people: ImportedPersonRow[];
  whitelist: WhitelistEntry[];
}

export interface UserTableRowBase {
  line_number: number;
  attributes: string;
  name: string;
  title: string;
  office_phone: string;
  mobile: string;
  email: string;
  note: string;
  system_role: SystemRole;
}

export interface ImportedPersonRow extends UserTableRowBase {
  user_id: number;
}

export interface ResultSnapshotUserRow extends UserTableRowBase {
  participant_id: number;
}

export interface OrganizationImportResponse {
  people: ImportedPersonRow[];
  tree: AdminOrgTreeResponse;
}

export interface PeerTeamMember {
  id: number;
  user_id: number;
  name: string;
  email: string;
  job_title: string;
}

export interface PeerTeam {
  id: number;
  name: string;
  count: number;
  members: PeerTeamMember[];
}

export interface PeerTeamsResponse {
  teams: PeerTeam[];
}

export interface EvaluationQuestion {
  id: number;
  evaluation_type: EvaluationType;
  organization_node_id: number | null;
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

export interface ManagerDetailQuestionTeam {
  id: number;
  name: string;
  parent_id: number | null;
  path: string;
  question_count: number;
  complete: boolean;
}

export interface ManagerDetailQuestionTeamsResponse {
  teams: ManagerDetailQuestionTeam[];
}

export interface SelfReviewResponse {
  guide_content: string;
  questions: EvaluationQuestion[];
  answers: Record<string, string>;
}

export interface PeerReviewContext {
  team_node_id: number;
  target_user_id?: number;
  title: string;
  role_label: string;
  complete: boolean;
}

export interface PeerReviewContextsResponse {
  contexts: PeerReviewContext[];
}

export interface PeerReviewTarget {
  user_id: number;
  display_name: string | null;
  email: string | null;
  job_title: string | null;
  role_label: string;
  affiliation: string;
}

export interface PeerReviewResponse {
  team: {
    id: number;
    title: string;
  };
  guide_content: string;
  questions: EvaluationQuestion[];
  targets: PeerReviewTarget[];
  scores: Record<string, number>;
}

export type ManagerDetailContextsResponse = PeerReviewContextsResponse;
export type ManagerDetailReviewResponse = PeerReviewResponse;

export interface EvaluationCompletionSummary {
  complete: boolean;
  completed_count: number;
  total_count: number;
}

export interface EvaluationContextCompletionSummary extends EvaluationCompletionSummary {
  contexts: PeerReviewContext[];
}

export interface EvaluationProgressResponse {
  self: EvaluationCompletionSummary;
  peer: EvaluationContextCompletionSummary;
  manager_detail: EvaluationContextCompletionSummary;
}

export interface ResultCycleSummary extends EvaluationCycleSummary {
  participant_count: number;
}

export interface ResultCyclesResponse {
  cycles: ResultCycleSummary[];
}

export interface ResultCycleUsersResponse {
  cycle: ResultCycleSummary;
  users: ResultSnapshotUserRow[];
}

export interface ResultReviewerRow {
  user_id: number;
  display_name: string | null;
  email: string | null;
  job_title: string | null;
  role_label: string;
  affiliation: string;
}

export interface ResultReviewSection {
  team: {
    id: number | null;
    title: string;
  };
  guide_content: string;
  questions: EvaluationQuestion[];
  reviewers: ResultReviewerRow[];
  scores: Record<string, number>;
}

export interface ResultParticipantResponse {
  cycle: ResultCycleSummary;
  user: ResultSnapshotUserRow;
  self_review: {
    guide_content: string;
    items: Array<{
      question: EvaluationQuestion;
      answer_text: string;
    }>;
  };
  peer_reviews: ResultReviewSection[];
  manager_detail_reviews: ResultReviewSection[];
}
