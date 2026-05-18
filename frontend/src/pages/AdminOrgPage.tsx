import { FormEvent, useEffect, useMemo, useState } from "react";
import { GitBranch, Trash2, UserRoundPlus } from "lucide-react";
import {
  createOrganizationMembership,
  createOrganizationNode,
  deleteOrganizationMembership,
  deleteOrganizationNode,
  fetchAdminOrgTree,
  searchAdminUsers
} from "../api";
import type {
  AdminOrgTreeResponse,
  AdminOrganizationNode,
  AdminUser,
  CurrentUser,
  MembershipRole,
  OrganizationMembership,
  OrganizationNodeType
} from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

type TreeNode = AdminOrganizationNode & {
  children: TreeNode[];
};

type ActiveFormKind = "head" | "team" | "member";

type ActiveForm = {
  nodeId: number;
  kind: ActiveFormKind;
} | null;

export function AdminOrgPage({ user }: { user: CurrentUser | null }) {
  const [data, setData] = useState<AdminOrgTreeResponse | null>(null);
  const [activeForm, setActiveForm] = useState<ActiveForm>(null);
  const [draftName, setDraftName] = useState("");
  const [userQuery, setUserQuery] = useState("");
  const [userResults, setUserResults] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [draftRole, setDraftRole] = useState<MembershipRole>("member");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user?.system_role === "admin") {
      loadOrg(setData, setMessage);
    }
  }, [user?.system_role]);

  const tree = useMemo(() => buildTree(data?.nodes ?? []), [data?.nodes]);

  useEffect(() => {
    if (activeForm?.kind !== "member" || !userQuery.trim()) {
      setUserResults([]);
      return;
    }
    if (selectedUser && userQuery === formatUserLabel(selectedUser)) {
      setUserResults([]);
      return;
    }

    let cancelled = false;
    searchAdminUsers(userQuery)
      .then((result) => {
        if (!cancelled) setUserResults(result.users);
      })
      .catch((error) => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Failed to search users");
      });
    return () => {
      cancelled = true;
    };
  }, [activeForm?.kind, userQuery]);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  function openForm(nodeId: number, kind: ActiveFormKind) {
    setActiveForm({ nodeId, kind });
    setDraftName("");
    setUserQuery("");
    setUserResults([]);
    setSelectedUser(null);
    setDraftRole("member");
    setMessage(null);
  }

  function selectUserForMembership(user: AdminUser) {
    setSelectedUser(user);
    setUserQuery(formatUserLabel(user));
    setUserResults([]);
  }

  async function submitInlineForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeForm) return;

    await runAdminAction(
      () => {
        if (activeForm.kind === "member") {
          if (!selectedUser) {
            throw new Error("사용자를 선택해 주세요.");
          }
          return createOrganizationMembership({
            user_id: selectedUser.id,
            organization_node_id: activeForm.nodeId,
            membership_role: draftRole
          });
        }

        return createOrganizationNode({
          name: draftName,
          node_type: activeForm.kind as OrganizationNodeType,
          parent_id: activeForm.nodeId
        });
      },
      () => {
        setActiveForm(null);
        setDraftName("");
        setUserQuery("");
        setUserResults([]);
        setSelectedUser(null);
        setDraftRole("member");
      },
      setData,
      setMessage,
    );
  }

  async function removeNode(node: TreeNode) {
    await runAdminAction(
      () => deleteOrganizationNode(node.id),
      () => setActiveForm(null),
      setData,
      setMessage,
    );
  }

  async function removeMembership(membershipId: number) {
    await runAdminAction(
      () => deleteOrganizationMembership(membershipId),
      () => undefined,
      setData,
      setMessage,
    );
  }

  return (
    <section className="org-fullscreen">
      {message && <div className="admin-message">{message}</div>}
      <div className="org-wide-canvas">
        {tree.map((node) => (
          <CompanyTree
            key={node.id}
            node={node}
            activeForm={activeForm}
            draftName={draftName}
            draftRole={draftRole}
            selectedUser={selectedUser}
            userQuery={userQuery}
            userResults={userResults}
            onChangeDraftName={setDraftName}
            onChangeDraftRole={setDraftRole}
            onChangeUserQuery={setUserQuery}
            onDeleteMembership={removeMembership}
            onDeleteNode={removeNode}
            onOpenForm={openForm}
            onSelectUser={selectUserForMembership}
            onSubmitForm={submitInlineForm}
          />
        ))}
      </div>
    </section>
  );
}

function CompanyTree(props: OrgTreeProps) {
  const heads = props.node.children.filter((child) => child.node_type === "head");
  const showHeadDraft = props.activeForm?.nodeId === props.node.id && props.activeForm.kind === "head";

  return (
    <div className="company-chart">
      <div className="company-top">
        <OrgNodeCard {...props} />
      </div>
      {(heads.length > 0 || showHeadDraft) && (
        <div className="head-row">
          {heads.map((head) => (
            <HeadColumn key={head.id} {...props} node={head} />
          ))}
          {showHeadDraft && (
            <section className="head-column draft-column">
              <InlineForm
                kind="head"
                node={props.node}
                draftName={props.draftName}
                draftRole={props.draftRole}
                selectedUser={props.selectedUser}
                userQuery={props.userQuery}
                userResults={props.userResults}
                onChangeDraftName={props.onChangeDraftName}
                onChangeDraftRole={props.onChangeDraftRole}
                onChangeUserQuery={props.onChangeUserQuery}
                onSelectUser={props.onSelectUser}
                onSubmit={props.onSubmitForm}
              />
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function HeadColumn(props: OrgTreeProps) {
  const teams = props.node.children.filter((child) => child.node_type === "team");
  const showTeamDraft = props.activeForm?.nodeId === props.node.id && props.activeForm.kind === "team";

  return (
    <section className="head-column">
      <OrgNodeCard {...props} />
      {(teams.length > 0 || showTeamDraft) && (
        <div className="team-stack">
          {teams.map((team) => (
            <div className="team-bubble" key={team.id}>
              <OrgNodeCard {...props} node={team} />
            </div>
          ))}
          {showTeamDraft && (
            <div className="team-bubble draft-team-bubble">
              <InlineForm
                kind="team"
                node={props.node}
                draftName={props.draftName}
                draftRole={props.draftRole}
                selectedUser={props.selectedUser}
                userQuery={props.userQuery}
                userResults={props.userResults}
                onChangeDraftName={props.onChangeDraftName}
                onChangeDraftRole={props.onChangeDraftRole}
                onChangeUserQuery={props.onChangeUserQuery}
                onSelectUser={props.onSelectUser}
                onSubmit={props.onSubmitForm}
              />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

type OrgTreeProps = {
  node: TreeNode;
  activeForm: ActiveForm;
  draftName: string;
  draftRole: MembershipRole;
  selectedUser: AdminUser | null;
  userQuery: string;
  userResults: AdminUser[];
  onChangeDraftName: (value: string) => void;
  onChangeDraftRole: (value: MembershipRole) => void;
  onChangeUserQuery: (value: string) => void;
  onDeleteMembership: (membershipId: number) => void;
  onDeleteNode: (node: TreeNode) => void;
  onOpenForm: (nodeId: number, kind: ActiveFormKind) => void;
  onSelectUser: (user: AdminUser) => void;
  onSubmitForm: (event: FormEvent<HTMLFormElement>) => void;
};

function OrgNodeCard({
  node,
  activeForm,
  draftName,
  draftRole,
  selectedUser,
  userQuery,
  userResults,
  onChangeDraftName,
  onChangeDraftRole,
  onChangeUserQuery,
  onDeleteMembership,
  onDeleteNode,
  onOpenForm,
  onSelectUser,
  onSubmitForm
}: OrgTreeProps) {
  const leaders = node.memberships.filter((membership) => membership.membership_role === "leader");
  const members = node.memberships.filter((membership) => membership.membership_role === "member");
  const active = activeForm?.nodeId === node.id ? activeForm.kind : null;
  const canDelete = !isRootNode(node);

  return (
    <div className={`org-bubble ${node.node_type}`}>
      <div className="tree-node-header">
        <span className={`node-type ${node.node_type}`}>{node.node_type}</span>
        <strong>{node.name}</strong>
        <div className="node-actions">
          {node.node_type === "company" && (
            <>
              <button type="button" title="본부 추가" onClick={() => onOpenForm(node.id, "head")}>
                <GitBranch size={15} />
              </button>
              <button type="button" title="회사 인원 추가" onClick={() => onOpenForm(node.id, "member")}>
                <UserRoundPlus size={15} />
              </button>
            </>
          )}
          {node.node_type === "head" && (
            <>
              <button type="button" title="팀 추가" onClick={() => onOpenForm(node.id, "team")}>
                <GitBranch size={15} />
              </button>
              <button type="button" title="본부 인원 추가" onClick={() => onOpenForm(node.id, "member")}>
                <UserRoundPlus size={15} />
              </button>
            </>
          )}
          {node.node_type === "team" && (
            <button type="button" title="팀 인원 추가" onClick={() => onOpenForm(node.id, "member")}>
              <UserRoundPlus size={15} />
            </button>
          )}
          {canDelete && (
            <button className="danger" type="button" title="노드 삭제" onClick={() => onDeleteNode(node)}>
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>

      {(leaders.length > 0 || members.length > 0) && (
        <div className="membership-list">
          {leaders.length > 0 && (
            <MembershipGroup label={leaderLabel(node)} memberships={leaders} onDelete={onDeleteMembership} />
          )}
          {members.length > 0 && (
            <MembershipGroup label="인원" memberships={members} onDelete={onDeleteMembership} />
          )}
        </div>
      )}

      {active === "member" && (
        <InlineForm
          kind={active}
          node={node}
          draftName={draftName}
          draftRole={draftRole}
          selectedUser={selectedUser}
          userQuery={userQuery}
          userResults={userResults}
          onChangeDraftName={onChangeDraftName}
          onChangeDraftRole={onChangeDraftRole}
          onChangeUserQuery={onChangeUserQuery}
          onSelectUser={onSelectUser}
          onSubmit={onSubmitForm}
        />
      )}
    </div>
  );
}

function InlineForm({
  kind,
  node,
  draftName,
  draftRole,
  selectedUser,
  userQuery,
  userResults,
  onChangeDraftName,
  onChangeDraftRole,
  onChangeUserQuery,
  onSelectUser,
  onSubmit
}: {
  kind: ActiveFormKind;
  node: AdminOrganizationNode;
  draftName: string;
  draftRole: MembershipRole;
  selectedUser: AdminUser | null;
  userQuery: string;
  userResults: AdminUser[];
  onChangeDraftName: (value: string) => void;
  onChangeDraftRole: (value: MembershipRole) => void;
  onChangeUserQuery: (value: string) => void;
  onSelectUser: (user: AdminUser) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  if (kind === "member") {
    return (
      <form className="node-inline-form" onSubmit={onSubmit}>
        <input
          value={userQuery}
          placeholder="사용자 검색"
          onChange={(event) => onChangeUserQuery(event.target.value)}
          required
        />
        {userResults.length > 0 && (
          <div className="user-search-results">
            {userResults.map((user) => (
              <button
                className={selectedUser?.id === user.id ? "selected" : ""}
                key={user.id}
                type="button"
                onClick={() => onSelectUser(user)}
              >
                <strong>{user.display_name || user.email}</strong>
                <span>{[user.job_title, user.email].filter(Boolean).join(" · ")}</span>
              </button>
            ))}
          </div>
        )}
        <select value={draftRole} onChange={(event) => onChangeDraftRole(event.target.value as MembershipRole)}>
          <option value="member">인원</option>
          <option value="leader">{leaderLabel(node)}</option>
        </select>
        <button className="inline-button" type="submit">
          추가
        </button>
      </form>
    );
  }

  return (
    <form className="node-inline-form" onSubmit={onSubmit}>
      <input
        value={draftName}
        placeholder={kind === "head" ? "본부 이름 입력" : "팀 이름 입력"}
        onChange={(event) => onChangeDraftName(event.target.value)}
        required
      />
      <button className="inline-button" type="submit">
        {kind === "head" ? "본부 추가" : "팀 추가"}
      </button>
    </form>
  );
}

function MembershipGroup({
  label,
  memberships,
  onDelete
}: {
  label: string;
  memberships: OrganizationMembership[];
  onDelete: (membershipId: number) => void;
}) {
  return (
    <div className="membership-group">
      <div className="membership-group-label">{label}</div>
      {memberships.map((membership) => (
        <div className={`member-row ${membership.membership_role}`} key={membership.id}>
          <span>ㄴ</span>
          <strong>{[membership.job_title, membership.display_name || membership.email].filter(Boolean).join(" ")}</strong>
          <button type="button" title="배정 삭제" onClick={() => onDelete(membership.id)}>
            <Trash2 size={13} />
          </button>
        </div>
      ))}
    </div>
  );
}

function buildTree(nodes: AdminOrganizationNode[]): TreeNode[] {
  const map = new Map<number, TreeNode>();
  nodes.forEach((node) => map.set(node.id, { ...node, children: [] }));
  const roots: TreeNode[] = [];
  map.forEach((node) => {
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)?.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

function leaderLabel(node: AdminOrganizationNode) {
  if (node.node_type === "head") return "본부장";
  if (node.node_type === "team") return "팀장";
  return "관리자";
}

function isRootNode(node: AdminOrganizationNode) {
  return node.node_type === "company" && node.parent_id === null && node.name === "NEXTIN";
}

function formatUserLabel(user: AdminUser) {
  return [user.display_name || user.email, user.job_title].filter(Boolean).join(" ");
}

async function loadOrg(
  setData: (data: AdminOrgTreeResponse) => void,
  setMessage: (message: string | null) => void,
) {
  try {
    setData(await fetchAdminOrgTree());
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "Failed to load organization");
  }
}

async function runAdminAction(
  action: () => Promise<unknown>,
  afterSuccess: () => void,
  setData: (data: AdminOrgTreeResponse) => void,
  setMessage: (message: string | null) => void,
) {
  setMessage(null);
  try {
    await action();
    afterSuccess();
    await loadOrg(setData, setMessage);
  } catch (error) {
    setMessage(error instanceof Error ? error.message : "Request failed");
  }
}
