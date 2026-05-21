# Architecture

Evaluation Protocol is an internal HR evaluation app with a FastAPI backend, PostgreSQL state, and a Vite React frontend served by NGINX.

## Runtime Shape

- Frontend container serves the React bundle on port `8080`.
- Backend container serves FastAPI on port `8000`.
- Frontend NGINX proxies `/api/` to the backend.
- PostgreSQL stores auth/session state, whitelist data, current organization data, evaluation templates, evaluation cycle snapshots, assignments, answers, and scores.

## Auth Model

- Microsoft OAuth is initiated and completed by the backend.
- The browser stores only the `s1` HttpOnly session cookie.
- Session state is stored in `user_sessions`.
- Login is allowed when the email is either `INITIALIZATION_EMAIL` or present in `user_whitelist`.
- `INITIALIZATION_EMAIL` is a hidden bootstrap admin account and is not inserted into `user_whitelist`.

## Current User And Organization Model

- `users.system_role` is the only global user role.
  - `user`: regular employee.
  - `admin`: system administrator.
- Organization responsibility is not a global user property.
- Organization responsibility comes from `organization_memberships.membership_role`.
  - `member`: regular member.
  - `leader`: company admin, head leader, or team leader depending on node type.
- Organization nodes are a fixed three-level live tree: `company > head > team`.
- The root company name is taken from the first `COMPANY` row in the latest organization CSV import.
- Additional root company nodes must not be created. All heads belong under the root company; all teams belong under a head.
- The DB enforces a single root company row. The configured root name is enforced by the backend CSV/API rules, not hardcoded into a DB check constraint.
- One user may have multiple memberships.
- A user may have both `leader` and `member` memberships, even within the same team.

## Organization Import

Admin organization management is CSV-driven while the system is `idle`.

- The import endpoint ignores rows before `BEGIN`, requires a non-empty `COMPANY,<company-name>` row immediately after `BEGIN`, and stops at `END`.
- Supported row types between `BEGIN` and `END` are `COMPANY`, `__HEAD`, `____TEAM`, `______USER`, and `______ASSIGNMENT`. Blank rows are rejected inside the block.
- `COMPANY` establishes the live root company name. `__HEAD` creates a head under the root company; `____TEAM` creates a team under the current head.
- `______USER` creates or updates the live user, whitelist entry, primary membership, and import-display profile.
- `______ASSIGNMENT` creates an additional membership for a person that also appears as a `______USER` in the same CSV, matched by name and email. The assignment row may appear before the user row.
- `attributes` must be `LEADER` or `MEMBER`, stored as `organization_memberships.membership_role = leader/member`.
- CSV `title` is displayed as-is in the import preview. Internally, `users.job_title` stores the last segment after `/`.
- `office_phone`, `mobile`, and `note` are stored in `organization_import_users` for the admin import preview. They are not shown in the organization tree.
- `mobile` must match `000-0000-0000` when present. Email must match `first.last@<COMPANY_EMAIL_DOMAIN>`.

Applying an import rebuilds the live whitelist, non-root organization nodes, and live memberships from the CSV. The initialization account is excluded from whitelist/user deletion. Existing users that remain in the CSV keep their `system_role`; new CSV users are created as `user`.

Organization import also clears live peer-review team configuration, because peer teams reference the imported user set.

## Peer Team Import

Peer-review team management is also CSV-driven while the system is `idle`.

- The endpoint ignores rows before `BEGIN` and after `END`; blank rows are rejected inside the block.
- Each team row uses `team_name,count,member...`.
- `count` must equal the number of non-empty member cells on that row.
- Members are matched by `organization_import_users.name`.
- Duplicate real names are not disambiguated in code. If needed, maintain names as `OOO1`, `OOO2` in the organization CSV and peer-team CSV.
- Applying a peer-team import replaces all live `peer_review_teams` and `peer_review_team_members` rows.

## Evaluation State

The system has one global evaluation state row in `evaluation_system_state`.

- `idle`: admin can edit whitelist, users, organization tree, memberships, questions, and guides.
- `running`: admin editing is locked. User evaluation pages read from the active cycle snapshot.

Starting an evaluation creates a new `evaluation_cycles` row and snapshots the current live state into cycle-scoped tables. Stopping an evaluation closes the current cycle and returns the system to `idle`. Closed cycle data remains for later result viewing or explicit deletion.

Start/stop transitions should treat `evaluation_system_state` as the serialization point. Code that changes the global state must lock that row in the database transaction before checking or updating it, so two admins cannot start overlapping cycles.

The DB also enforces valid state values and allows at most one `running` cycle.

## Evaluation Types

The canonical evaluation type values are:

- `self`: 자기평가
- `peer`: 동료평가
- `manager_detail`: 팀원평가

Live `evaluation_questions` and `evaluation_guides` are templates only. User-facing running evaluations use `evaluation_cycle_questions` and `evaluation_cycle_guides` snapshots.

`self` and `peer` questions are global for the evaluation type. `manager_detail` questions are scoped to a live organization `team` node through `evaluation_questions.organization_node_id`, and are snapshotted onto the matching team snapshot when a cycle starts.

## Cycle Snapshot Model

When an evaluation starts, the backend snapshots:

- users into `evaluation_participants`
- organization nodes into `evaluation_org_node_snapshots`
- memberships into `evaluation_membership_snapshots`
- peer-review teams into `evaluation_peer_team_snapshots`
- peer-review team members into `evaluation_peer_team_member_snapshots`
- active questions into `evaluation_cycle_questions`
- guide markdown into `evaluation_cycle_guides`
- self, peer, and manager-detail relationships into `review_assignments`

Answers and scores belong to assignments and cycle questions:

- `self_review_answers.assignment_id`
- `self_review_answers.cycle_question_id`
- `review_scores.assignment_id`
- `review_scores.cycle_question_id`

Live user, organization, and template deletion does not delete an already-opened or closed cycle. Explicit cycle deletion is allowed to cascade through the snapshot graph.

Cycle-owned rows must not cross cycles. The schema enforces the core same-cycle relationships with cycle-local unique constraints and composite foreign keys. For example, an answer or score must reference an assignment and a cycle question from the same `evaluation_cycles.id`.

## Peer Assignment Rules

Peer-review team setup is explicit and lives in `peer_review_teams` and `peer_review_team_members`.

- Peer targets are not inferred from the organization tree.
- Starting a cycle snapshots peer teams into `evaluation_peer_team_snapshots`.
- For each peer team snapshot, every member evaluates every member in the same peer team, including self.
- Peer questions are shared across all peer teams.

## Manager Detail Rules

Manager-detail evaluation is organization-team based.

- Admin question management lists live organization `team` nodes and stores separate `manager_detail` questions for each team.
- Starting a cycle snapshots each team-scoped question onto the corresponding `evaluation_org_node_snapshots` team row.
- A team `leader` membership evaluates that team's `member` memberships.
- A parent head membership, whether `leader` or `member`, evaluates every `leader` and `member` in each team under that head.
- Manager-detail scores use the team-specific cycle questions for the evaluated team.

## Caching

Frontend NGINX explicitly disables caching for:

- `index.html`
- SPA fallback routes
- `/api/`

Vite hashed assets under `/assets/` are cached as immutable long-lived files.
