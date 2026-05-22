import { useEffect, useState } from "react";
import { ShieldCheck, Table2 } from "lucide-react";
import { fetchAdminOrgTree, updateOrgUserSystemRole } from "../../../shared/api/admin";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, ImportedPersonRow, SystemRole } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import { ImportedUsersTable } from "./AdminOrganizationShared";

export function AdminOrganizationUsersPage({ user }: { user: CurrentUser | null }) {
  const [people, setPeople] = useState<ImportedPersonRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [updatingUserId, setUpdatingUserId] = useState<number | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      void loadImportedUsers(setPeople, setMessage);
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="org-fullscreen">
      <PageHeader
        icon={Table2}
        eyebrow="Organization"
        title="사용자 확인"
        description="업로드된 조직 CSV 기준 사용자 행을 확인합니다."
      />
      <StatusMessage message={message} />
      <ImportedUsersTable
        people={people}
        renderManagement={(person) => {
          const livePerson = person as ImportedPersonRow;
          return (
            <div className="result-management-cell">
              <span className="role-pill">{livePerson.system_role}</span>
              <div className="result-management-action">
                <button
                  className="secondary-inline-button"
                  type="button"
                  disabled={updatingUserId === livePerson.user_id}
                  onClick={async () => {
                    const nextRole: SystemRole = livePerson.system_role === "admin" ? "user" : "admin";
                    setUpdatingUserId(livePerson.user_id);
                    setMessage(null);
                    try {
                      await updateOrgUserSystemRole(livePerson.user_id, nextRole);
                      await loadImportedUsers(setPeople, setMessage);
                      setMessage("시스템 권한 변경이 완료되었습니다.");
                    } catch (error) {
                      setMessage(error instanceof Error ? error.message : "시스템 권한을 변경하지 못했습니다.");
                    } finally {
                      setUpdatingUserId(null);
                    }
                  }}
                >
                  <ShieldCheck size={16} />
                  {livePerson.system_role === "admin" ? "직원으로 변경" : "관리자로 변경"}
                </button>
              </div>
            </div>
          );
        }}
      />
    </section>
  );
}

async function loadImportedUsers(
  setPeople: (people: ImportedPersonRow[]) => void,
  setMessage: (message: string | null) => void,
) {
  try {
    const result = await fetchAdminOrgTree();
    setPeople(result.imported_people);
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "사용자 데이터를 불러오지 못했습니다.");
  }
}
