import type { CurrentUser } from "../../../shared/types";
import { AdminQuestionManagementPage } from "./AdminQuestionManagementShared";

export function AdminSelfQuestionManagementPage({ user }: { user: CurrentUser | null }) {
  return <AdminQuestionManagementPage user={user} evaluationType="self" />;
}
