# Maintenance

This document records operational rules that are easy to forget while changing the evaluation system.

## Verification

```powershell
cd deploy
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml up --build -d
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml ps
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml exec backend python -m compileall app alembic
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml exec frontend nginx -t
```

All verification and tests must run through Docker Compose. `backend/.venv`, `frontend/node_modules`, and `frontend/dist` are disposable IDE helper artifacts and are ignored by git.

## Database Migrations

- The backend runs Alembic migrations on startup.
- The current architecture is represented as a single initial schema migration in `backend/alembic/versions`.
- Keep the SQLAlchemy models and the initial Alembic schema aligned.
- When changing architecture before production data matters, update the initial schema directly instead of carrying obsolete transitional migrations.
- If production history becomes important later, stop squashing and add forward-only migrations from that point.

## Evaluation State Rules

- `idle` is the only state where admin mutation is allowed.
- `running` locks whitelist, user, organization, membership, question, and guide edits.
- Starting a cycle snapshots the current user/tree/question/guide state and creates assignments.
- Stopping a cycle closes the current snapshot, clears live setup tables, and returns to `idle`.
- If a user or question was missed, stop the current cycle, edit while idle, and start a new cycle.
- Treat `evaluation_system_state` id `1` as the state-machine serialization row. Start/stop code must lock it in the same DB transaction before checking or changing `status` and `current_cycle_id`.
- Do not create cycles through ad hoc SQL while the system state is `running`.
- The DB constrains `evaluation_system_state.status` to `idle/running`, `evaluation_cycles.status` to `running/closed`, and allows at most one `running` cycle.
- `evaluation_system_state.status` and `current_cycle_id` must agree: `idle` has no current cycle, `running` has one.

Required race handling:

- Use `SELECT ... FOR UPDATE` or SQLAlchemy `with_for_update()` on `evaluation_system_state`.
- Check `status` only after the lock is held.
- Create the cycle, snapshot rows, assignments, and state update in one transaction.
- On failure before commit, the whole attempted cycle start should roll back.

Stop behavior:

- Keep the closed cycle snapshot and result rows.
- Clear imported organization users, live memberships, live non-root organization nodes, peer-review teams, live question templates, and live guides.
- Do not delete user sessions or historical cycle snapshots as part of normal stop.

## Cascade Rules

Live auth and organization cascades:

- `user_sessions.user_id -> users.id` cascades.
- `organization_memberships.user_id -> users.id` cascades.
- `organization_memberships.organization_node_id -> organization_nodes.id` cascades.
- `organization_nodes.parent_id -> organization_nodes.id` cascades for live tree subtree deletion.

Evaluation snapshot cascades:

- `evaluation_cycles` cascades to participants, org snapshots, membership snapshots, peer-team snapshots, cycle questions, guides, assignments, answers, and scores.
- `review_assignments` cascades to `self_review_answers` and `review_scores`.
- `evaluation_cycle_questions` cascades to answer/score cells for that cycle question.

Do not connect running or closed answers/scores directly to live `users`, live `organization_nodes`, or live `evaluation_questions`. Live edits must affect only future cycles.

Cycle-local integrity:

- Rows under a cycle should not reference rows from another cycle.
- The schema exposes unique `(cycle_id, id)` keys on `evaluation_participants`, `evaluation_org_node_snapshots`, `evaluation_cycle_questions`, and `review_assignments`.
- `evaluation_membership_snapshots` uses composite FKs to ensure its participant and org node snapshot are from the same cycle.
- `review_assignments` uses composite FKs to ensure reviewer, target, team context, and head context are from the same cycle.
- `self_review_answers` and `review_scores` store their own `cycle_id` and use composite FKs to ensure assignment and question are from the same cycle.
- Keep this pattern when adding new cycle-owned result tables.

## Organization Tree Rules

- The root company name comes from the first `COMPANY` row in the latest organization CSV import.
- Do not allow additional `company` nodes through the API.
- The DB has a partial unique index that allows only one root company row.
- The DB requires company rows to have no parent. The backend updates the root company name from organization CSV import.
- The DB requires non-company rows to have a parent.
- Heads must be direct children of the root company.
- Teams must be direct children of a head.
- `organization_memberships.membership_role = leader` means company admin, head leader, or team leader depending on node type.
- `organization_memberships.membership_role = member` should be used for normal team membership. Avoid company-level member rows unless a future workflow explicitly needs them.

## CSV Organization Import Rules

- Imports are admin-only and allowed only while the evaluation state is `idle`.
- The backend accepts UTF-8 with BOM or CP949 CSV input.
- Parsing starts at `BEGIN`; earlier rows are ignored.
- The first row after `BEGIN` must be `COMPANY,<company-name>` with a non-empty company name.
- Parsing stops at `END`; later cells and rows are ignored.
- Blank rows between `BEGIN` and `END` are rejected.
- `COMPANY`, `__HEAD`, and `____TEAM` read only the second cell.
- `______USER` requires an empty section cell, `attributes`, `name`, and `email`. `attributes` must be `LEADER` or `MEMBER`.
- `______ASSIGNMENT` is an extra membership. It must match a `______USER` in the same file by `(name, email)`, but it may appear before that user row.
- `______USER` emails must be unique because live users and whitelist rows are keyed by email.
- `______USER` emails must match `first.last@<COMPANY_EMAIL_DOMAIN>`.
- `mobile` is validated as `000-0000-0000` when present. `office_phone` is not validated.
- CSV import is destructive for live admin data: it rebuilds `user_whitelist`, live non-root `organization_nodes`, and `organization_memberships` from the file.
- CSV import stores user-display source rows in `organization_import_users`, including `office_phone`, `mobile`, and `note`.
- CSV import clears peer-review team tables because those teams depend on the imported user set.
- The initialization account is not inserted into `user_whitelist` and is excluded from user deletion during import.
- Existing users that are still present in the CSV keep their `system_role`; new imported users are created as `user`.
- Do not add a CSV history table unless a future workflow needs uploaded-file audit, rollback, or delayed apply semantics.

## Peer Team CSV Import Rules

- Imports are admin-only and allowed only while the evaluation state is `idle`.
- Parsing starts at `BEGIN`; earlier rows are ignored.
- Parsing stops at `END`; later cells and rows are ignored.
- Blank rows between `BEGIN` and `END` are rejected.
- Each row is `team_name,count,member...`.
- Count is validated against all non-empty member cells after the count cell.
- Member names must exist in `organization_import_users.name`; otherwise the error should say that the user name is unknown in the organization import users.
- Duplicate names are a data-management responsibility. Maintain ambiguous names as `OOO1`, `OOO2` in both CSV files.
- Import replaces all rows in `peer_review_teams` and `peer_review_team_members`.

## Evaluation Question Rules

Live templates:

- `evaluation_type = 'self'`: no weight, textarea answers, 1000 character limit.
- `evaluation_type = 'peer'`: `weight > 0`, numeric score columns.
- `evaluation_type = 'manager_detail'`: `weight > 0`, numeric score columns, and a required `organization_node_id` pointing to a live organization `team`.

Effective weights are calculated from the active questions in the same evaluation type and scope. For `manager_detail`, the scope is the team. Running evaluations calculate from the cycle question snapshot, not the live template table.

Question creation requires a non-empty title and description; weighted types also require `weight > 0`. Setup readiness requires a non-empty screen guide plus at least one active question. For `manager_detail`, the common guide must be non-empty and every live organization team must have at least one active team-scoped question.

Use only the canonical values `self`, `peer`, and `manager_detail` in code, DB rows, and docs. Do not introduce alternate internal names for 팀원평가.

## Role Rules

Do not reintroduce a global `staff/manager` user role.

- Admin access is controlled only by `users.system_role`.
- Evaluation context is controlled by generated `review_assignments`.
- The dashboard shows the `manager_detail` entry to all users; the runtime page lists only assignments generated for the current cycle.

## Peer Review Rules

- Do not infer peer review targets from `organization_memberships`.
- Peer review team management uses `peer_review_teams` and `peer_review_team_members`.
- Starting a cycle snapshots peer teams into `evaluation_peer_team_snapshots` and `evaluation_peer_team_member_snapshots`.
- Every member in a peer team evaluates every member in that peer team, including self.
- Peer questions remain global across all peer teams.
- Each peer target is scored out of 100 after effective weights are applied.
- Weighted score saves are rejected when the reviewer's average total score across peer targets in the same peer team exceeds 50.

## Manager Detail Rules

- Manager-detail question management is per live organization `team`.
- Do not create global `manager_detail` questions with `organization_node_id = NULL`; the DB check constraint rejects that shape.
- Team `leader` memberships evaluate that team's `member` memberships.
- Head-level `leader` and `member` memberships evaluate all `leader` and `member` memberships in teams under that head.
- Runtime manager-detail assignments and scores are cycle-owned and must not read live organization rows after cycle start.
- Each manager-detail target is scored out of 100 after effective weights are applied.
- Manager-detail does not apply the peer-review average-50 relative-rating constraint.

## Cache Rules

If users report old frontend UI after deploy:

- Verify `frontend/nginx/default.conf` still sends `Cache-Control: no-store` for `index.html`, SPA fallback routes, and `/api/`.
- Verify hashed Vite assets under `/assets/` are served with immutable caching.
- Browser cookies only contain the HttpOnly session cookie and are not a frontend UI cache.
