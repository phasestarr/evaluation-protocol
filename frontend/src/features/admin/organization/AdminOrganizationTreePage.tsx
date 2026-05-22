import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { fetchAdminOrgTree } from "../../../shared/api/admin";
import { PageHeader } from "../../../shared/ui/PageHeader/PageHeader";
import { StatusMessage } from "../../../shared/ui/StatusMessage/StatusMessage";
import type { AdminOrgTreeResponse, CurrentUser } from "../../../shared/types";
import { AccessDeniedPage } from "../../access/AccessDeniedPage";
import { ReadonlyOrgTree } from "./AdminOrganizationShared";

export function AdminOrganizationTreePage({ user }: { user: CurrentUser | null }) {
  const [tree, setTree] = useState<AdminOrgTreeResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      fetchAdminOrgTree()
        .then(setTree)
        .catch((error) => setMessage(error instanceof Error ? error.message : "조직 트리를 불러오지 못했습니다."));
    }
  }, [user?.system_role]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  return (
    <section className="org-fullscreen">
      <PageHeader
        icon={GitBranch}
        eyebrow="Organization"
        title="조직 트리 확인"
        description="현재 반영된 COMPANY > HEAD > TEAM 조직 트리를 확인합니다."
      />
      <StatusMessage message={message} />
      {tree && <ReadonlyOrgTree tree={tree} />}
    </section>
  );
}
