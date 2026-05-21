import type { CurrentUser } from "../../../shared/types";
import { AdminQuestionManagementPage } from "./AdminQuestionManagementShared";

export function AdminPeerQuestionManagementPage({ user }: { user: CurrentUser | null }) {
  return <AdminQuestionManagementPage user={user} evaluationType="peer" />;
}
