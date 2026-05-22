import type { ReactNode } from "react";
import type {
  AdminOrganizationNode,
  AdminOrgTreeResponse,
  ImportedPersonRow,
  OrganizationMembership,
  UserTableRowBase,
} from "../../../shared/types";
import "./AdminOrganizationPages.css";

type TreeNode = AdminOrganizationNode & {
  children: TreeNode[];
};

export function ImportedUsersTable({
  people,
  managementLabel = "management",
  renderManagement,
}: {
  people: UserTableRowBase[];
  managementLabel?: string;
  renderManagement?: (person: UserTableRowBase) => ReactNode;
}) {
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
              <th>{managementLabel}</th>
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
                <td>{renderManagement ? renderManagement(person) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ReadonlyOrgTree({ tree }: { tree: AdminOrgTreeResponse }) {
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
