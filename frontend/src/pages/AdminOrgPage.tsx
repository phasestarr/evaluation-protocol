import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileUp, GitBranch, Table2 } from "lucide-react";
import { fetchAdminOrgTree, importOrganizationCsv } from "../api";
import { StatusMessage } from "../components/StatusMessage";
import type {
  AdminOrganizationNode,
  AdminOrgTreeResponse,
  CurrentUser,
  ImportedPersonRow,
  OrganizationMembership,
} from "../types";
import { AccessDeniedPage } from "./AccessDeniedPage";

type TreeNode = AdminOrganizationNode & {
  children: TreeNode[];
};

export function AdminOrgPage({ user }: { user: CurrentUser | null }) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);

  if (user?.system_role !== "admin") {
    return <AccessDeniedPage />;
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage("CSV 파일을 선택해 주세요.");
      return;
    }
    setImporting(true);
    setMessage(null);
    try {
      await importOrganizationCsv(file);
      setMessage("CSV 검증과 조직 반영이 완료되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CSV를 반영하지 못했습니다.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <section className="dashboard">
      <div className="page-heading">
        <p className="eyebrow">Organization</p>
        <h1>조직 관리</h1>
        <p>CSV 파일로 사용자 화이트리스트와 조직 트리를 한 번에 반영합니다.</p>
      </div>
      <StatusMessage message={message} />
      <form className="surface-panel import-panel" onSubmit={submitImport}>
        <div>
          <h2>CSV 업로드</h2>
          <p className="muted-copy">COMPANY 행부터 읽고, LEADER/MEMBER 속성으로 조직 역할을 배정합니다.</p>
        </div>
        <label className="file-drop">
          <FileUp size={24} />
          <span>{file ? file.name : "CSV 파일 선택"}</span>
          <input
            accept=".csv,text/csv"
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="inline-button" type="submit" disabled={importing}>
          {importing ? "반영 중" : "검증 및 반영"}
        </button>
      </form>
      <div className="action-grid two">
        <Link className="action-card" to="/admin/org/users">
          <div className="action-icon">
            <Table2 size={24} />
          </div>
          <div>
            <h3>사용자 확인</h3>
            <p>CSV 사용자 목록 확인</p>
          </div>
        </Link>
        <Link className="action-card" to="/admin/org/tree-view">
          <div className="action-icon">
            <GitBranch size={24} />
          </div>
          <div>
            <h3>조직 트리 확인</h3>
            <p>반영된 조직 트리 확인</p>
          </div>
        </Link>
      </div>
    </section>
  );
}

export function AdminOrgUsersPage({ user }: { user: CurrentUser | null }) {
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

export function AdminOrgTreePage({ user }: { user: CurrentUser | null }) {
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

function ImportedUsersTable({ people }: { people: ImportedPersonRow[] }) {
  return (
    <div className="surface-panel evaluation-table-panel">
      <div className="evaluation-table-wrap">
        <table className="evaluation-table">
          <thead>
            <tr>
              <th>attributes</th>
              <th>name</th>
              <th>title</th>
              <th>office_phone</th>
              <th>mobile</th>
              <th>email</th>
              <th>note</th>
            </tr>
          </thead>
          <tbody>
            {people.map((person) => (
              <tr key={`${person.line_number}:${person.email}`}>
                <td>{person.attributes}</td>
                <td>{person.name}</td>
                <td>{person.title}</td>
                <td>{person.office_phone}</td>
                <td>{person.mobile}</td>
                <td>{person.email}</td>
                <td>{person.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReadonlyOrgTree({ tree }: { tree: AdminOrgTreeResponse }) {
  const roots = buildTree(tree.nodes);
  return (
    <div className="org-wide-canvas">
      {roots.map((node) => (
        <CompanyTree key={node.id} node={node} />
      ))}
    </div>
  );
}

function CompanyTree({ node }: { node: TreeNode }) {
  const heads = node.children.filter((child) => child.node_type === "head");
  return (
    <div className="company-chart">
      <div className="company-top">
        <OrgNodeCard node={node} />
      </div>
      {heads.length > 0 && (
        <div className="head-row">
          {heads.map((head) => (
            <HeadColumn key={head.id} node={head} />
          ))}
        </div>
      )}
    </div>
  );
}

function HeadColumn({ node }: { node: TreeNode }) {
  const teams = node.children.filter((child) => child.node_type === "team");
  return (
    <section className="head-column">
      <OrgNodeCard node={node} />
      {teams.length > 0 && (
        <div className="team-stack">
          {teams.map((team) => (
            <div className="team-bubble" key={team.id}>
              <OrgNodeCard node={team} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function OrgNodeCard({ node }: { node: TreeNode }) {
  const leaders = node.memberships.filter((membership) => membership.membership_role === "leader");
  const members = node.memberships.filter((membership) => membership.membership_role === "member");
  return (
    <div className={`org-bubble ${node.node_type}`}>
      <div className="tree-node-header">
        <span className={`node-type ${node.node_type}`}>{node.node_type}</span>
        <strong>{node.name}</strong>
      </div>
      {(leaders.length > 0 || members.length > 0) && (
        <div className="membership-list">
          {leaders.length > 0 && <MembershipGroup label={leaderLabel(node)} memberships={leaders} />}
          {members.length > 0 && <MembershipGroup label="팀원" memberships={members} />}
        </div>
      )}
    </div>
  );
}

function MembershipGroup({ label, memberships }: { label: string; memberships: OrganizationMembership[] }) {
  return (
    <div className="membership-group">
      <div className="membership-group-label">{label}</div>
      {memberships.map((membership) => (
        <div className={`member-row ${membership.membership_role}`} key={membership.id}>
          <span>ㄴ</span>
          <strong>{[membership.job_title, membership.display_name || membership.email].filter(Boolean).join(" ")}</strong>
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
