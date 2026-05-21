import { useEffect, useState } from "react";
import { fetchAdminOrgTree } from "../../../shared/api/admin";
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
      <StatusMessage message={message} />
      {tree && <ReadonlyOrgTree tree={tree} />}
    </section>
  );
}
