import { useEffect, useState } from "react";
import { fetchAdminOrgTree } from "../../../shared/api/admin";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, ImportedPersonRow } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import { ImportedUsersTable } from "./AdminOrganizationShared";

export function AdminOrganizationUsersPage({ user }: { user: CurrentUser | null }) {
  const [people, setPeople] = useState<ImportedPersonRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchAdminOrgTree()
        .then((result) => setPeople(result.imported_people))
        .catch((error) => setMessage(error instanceof Error ? error.message : "사용자 데이터를 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="org-fullscreen">
      <StatusMessage message={message} />
      <ImportedUsersTable people={people} />
    </section>
  );
}
