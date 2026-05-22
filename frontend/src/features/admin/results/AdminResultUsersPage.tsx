import { useEffect, useState } from "react";
import { ArrowLeft, Table2 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { fetchResultCycleUsers } from "../../../shared/api/admin";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { CurrentUser, ResultCycleSummary, ResultSnapshotUserRow } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import { ImportedUsersTable } from "../organization/AdminOrganizationShared";

export function AdminResultUsersPage({ user }: { user: CurrentUser | null }) {
  const { cycleId } = useParams();
  const numericCycleId = Number(cycleId);
  const [cycle, setCycle] = useState<ResultCycleSummary | null>(null);
  const [users, setUsers] = useState<ResultSnapshotUserRow[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role !== "admin" || !Number.isFinite(numericCycleId)) return;
    fetchResultCycleUsers(numericCycleId)
      .then((result) => {
        setCycle(result.cycle);
        setUsers(result.users);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "스냅샷 사용자 목록을 불러오지 못했습니다."));
  }, [numericCycleId, user?.system_role]);

  if (user?.system_role !== "admin" || !Number.isFinite(numericCycleId)) {
    return <AccessDeniedPage />;
  }

  return (
    <section className="org-fullscreen">
      <PageHeader
        icon={Table2}
        eyebrow="Results"
        title={cycle ? `${cycle.name} 사용자 확인` : "스냅샷 사용자 확인"}
        description={cycle ? `${cycle.snapshot_date} 기준 사용자 스냅샷입니다.` : "사용자 스냅샷을 불러오는 중입니다."}
        aside={(
          <Link className="secondary-inline-button" to="/admin/results">
            <ArrowLeft size={16} />
            스냅샷 목록
          </Link>
        )}
      />
      <StatusMessage message={message} />
      <ImportedUsersTable
        people={users}
        managementLabel="열람"
        renderManagement={(person) =>
          "participant_id" in person ? (
            <Link className="secondary-inline-button" to={`/admin/results/${numericCycleId}/users/${person.participant_id}`}>
              열람
            </Link>
          ) : (
            "-"
          )
        }
      />
    </section>
  );
}
