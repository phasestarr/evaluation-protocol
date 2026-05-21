# Database Operations

This file is for inspecting and cleaning the PostgreSQL database from Docker,
even if you are not comfortable with SQL.

All commands are PowerShell-friendly one-liners. They intentionally avoid SQL
single quotes inside the command by using PostgreSQL dollar-quoted strings such
as `$$closed$$`. In the shell command those dollars are escaped as `\$\$closed\$\$`
so the container shell does not expand them.

Commands containing `"PUT_*_HERE"` are templates. Replace the full quoted
placeholder with the actual id, email, or other value before running the command.

## Safety Rules

1. Run the inspect command first.
2. Copy the `id` you need.
3. Paste that `id` into the next command.
4. Before any `DELETE`, run a `SELECT` with the same condition.
5. Do not delete a running evaluation cycle. Stop it through the app first.

## Connect

Interactive shell:

```powershell
docker exec -it evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Run one query:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT NOW();"'
```

Expanded output:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT * FROM evaluation_system_state;"'
```

## Current Tables

Application tables:

1. `users`: live user accounts.
2. `user_whitelist`: DB-managed login allowlist.
3. `user_sessions`: server-side cookie sessions.
4. `oauth_transactions`: Microsoft OAuth transaction state.
5. `organization_nodes`: live `company > head > team` tree.
6. `organization_memberships`: live user membership/role assignments.
7. `organization_import_users`: latest organization CSV user-display rows.
8. `peer_review_teams`: live explicit peer-review team definitions.
9. `peer_review_team_members`: live peer-review team memberships.
10. `evaluation_questions`: live editable question templates.
11. `evaluation_guides`: live editable guide markdown.
12. `evaluation_cycles`: one evaluation run/snapshot root.
13. `evaluation_system_state`: global `idle/running` status.
14. `evaluation_participants`: user snapshot rows for one cycle.
15. `evaluation_org_node_snapshots`: organization node snapshot rows for one cycle.
16. `evaluation_membership_snapshots`: membership snapshot rows for one cycle.
17. `evaluation_peer_team_snapshots`: peer-review team snapshot rows for one cycle.
18. `evaluation_peer_team_member_snapshots`: peer-review team member snapshot rows for one cycle.
19. `evaluation_cycle_questions`: question snapshot rows for one cycle.
20. `evaluation_cycle_guides`: guide markdown snapshot rows for one cycle.
21. `review_assignments`: cycle-scoped evaluation edges for self, peer, and `manager_detail`.
22. `self_review_answers`: self-review text answers.
23. `review_scores`: peer and `manager_detail` numeric score cells.

Migration metadata:

24. `alembic_version`

## Whole-Database Inspect

List tables:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema() ORDER BY table_name;"'
```

Estimated row counts:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT relname AS table_name, n_live_tup AS estimated_rows FROM pg_stat_user_tables ORDER BY relname;"'
```

Alembic head:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version;"'
```

Foreign-key delete rules:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name, rc.delete_rule FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema JOIN information_schema.referential_constraints rc ON rc.constraint_name = tc.constraint_name AND rc.constraint_schema = tc.table_schema WHERE tc.constraint_type = \$\$FOREIGN KEY\$\$ AND tc.table_schema = current_schema() ORDER BY tc.table_name, kcu.column_name;"'
```

## Common Workflows

### Workflow A: find one user and inspect live memberships

List users:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, display_name, job_title, system_role, created_at FROM users ORDER BY email;"'
```

Use the copied `users.id`:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT m.id, m.user_id, u.email, n.id AS node_id, n.name AS node_name, n.node_type, m.membership_role, m.created_at FROM organization_memberships m JOIN users u ON u.id = m.user_id JOIN organization_nodes n ON n.id = m.organization_node_id WHERE m.user_id = \$\$\"PUT_USER_ID_HERE\"\$\$ ORDER BY n.id, m.membership_role DESC, m.id;"'
```

### Workflow B: inspect the current live tree

List organization nodes:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, node_type, parent_id, created_at FROM organization_nodes ORDER BY id;"'
```

List live memberships:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT m.id, n.name AS node_name, n.node_type, m.membership_role, u.email, u.display_name, u.job_title FROM organization_memberships m JOIN organization_nodes n ON n.id = m.organization_node_id JOIN users u ON u.id = m.user_id ORDER BY n.id, CASE WHEN m.membership_role = \$\$leader\$\$ THEN 0 ELSE 1 END, m.id;"'
```

### Workflow C: inspect live data after CSV organization import

CSV import is an app-level operation, not a stored upload table. It rebuilds live whitelist rows, non-root organization nodes, and live memberships from the file while the system is `idle`.

Check the imported allowlist:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, created_at FROM user_whitelist ORDER BY email;"'
```

Check imported users:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, display_name, job_title, system_role FROM users ORDER BY email;"'
```

Check imported organization shape:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, node_type, parent_id FROM organization_nodes ORDER BY id;"'
```

Check imported memberships:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT u.email, u.display_name, u.job_title, n.name AS node_name, n.node_type, m.membership_role FROM organization_memberships m JOIN users u ON u.id = m.user_id JOIN organization_nodes n ON n.id = m.organization_node_id ORDER BY n.id, CASE WHEN m.membership_role = \$\$leader\$\$ THEN 0 ELSE 1 END, u.email;"'
```

Expected import behavior:

- `INITIALIZATION_EMAIL` is excluded from whitelist/user deletion.
- Existing imported users keep `system_role`.
- New imported users get `system_role = user`.
- `organization_memberships` are recreated from `______USER` and `______ASSIGNMENT` rows.
- `organization_import_users` stores `office_phone`, `mobile`, and `note` for the admin user preview.
- `peer_review_teams` and `peer_review_team_members` are cleared when organization CSV is imported.

### Workflow D: inspect a cycle snapshot

List cycles:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, snapshot_date, status, started_at, ended_at FROM evaluation_cycles ORDER BY id DESC;"'
```

Use the copied `evaluation_cycles.id` to inspect participants:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_user_id, email_snapshot, display_name_snapshot, job_title_snapshot, system_role_snapshot, sort_order FROM evaluation_participants WHERE cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY sort_order, id;"'
```

Inspect the snapshot tree:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_node_id, name_snapshot, node_type_snapshot, parent_snapshot_id, sort_order FROM evaluation_org_node_snapshots WHERE cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY sort_order, id;"'
```

Inspect snapshot memberships:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT m.id, p.email_snapshot, p.display_name_snapshot, n.name_snapshot AS node_name, n.node_type_snapshot, m.membership_role_snapshot, m.sort_order FROM evaluation_membership_snapshots m JOIN evaluation_participants p ON p.id = m.participant_id JOIN evaluation_org_node_snapshots n ON n.id = m.org_node_snapshot_id WHERE m.cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY m.sort_order, m.id;"'
```

Inspect peer-team snapshots:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT t.id, t.name_snapshot, m.participant_id, p.email_snapshot, p.display_name_snapshot FROM evaluation_peer_team_snapshots t LEFT JOIN evaluation_peer_team_member_snapshots m ON m.peer_team_snapshot_id = t.id LEFT JOIN evaluation_participants p ON p.id = m.participant_id WHERE t.cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY t.sort_order, m.sort_order;"'
```

Inspect cycle questions:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_question_id, context_team_snapshot_id, evaluation_type, title_snapshot, weight_snapshot, sort_order_snapshot FROM evaluation_cycle_questions WHERE cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY evaluation_type, context_team_snapshot_id, sort_order_snapshot, id;"'
```

### Workflow E: inspect one cycle's assignments and answers

Review assignments:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT ra.id, ra.review_type, reviewer.email_snapshot AS reviewer, target.email_snapshot AS target, peer.name_snapshot AS peer_team, team.name_snapshot AS org_team, head.name_snapshot AS head, ra.display_role_label_snapshot, ra.status, ra.submitted_at, ra.sort_order FROM review_assignments ra JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id LEFT JOIN evaluation_participants target ON target.id = ra.target_participant_id LEFT JOIN evaluation_peer_team_snapshots peer ON peer.id = ra.context_peer_team_snapshot_id LEFT JOIN evaluation_org_node_snapshots team ON team.id = ra.context_team_snapshot_id LEFT JOIN evaluation_org_node_snapshots head ON head.id = ra.context_head_snapshot_id WHERE ra.cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY ra.sort_order, ra.id;"'
```

Self-review answers:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT a.id, reviewer.email_snapshot, q.title_snapshot, LEFT(a.answer_text, 120) AS answer_preview, a.updated_at FROM self_review_answers a JOIN review_assignments ra ON ra.id = a.assignment_id JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id JOIN evaluation_cycle_questions q ON q.id = a.cycle_question_id WHERE ra.cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY reviewer.email_snapshot, q.sort_order_snapshot, q.id;"'
```

Peer and manager-detail scores:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT s.id, ra.review_type, reviewer.email_snapshot AS reviewer, target.email_snapshot AS target, peer.name_snapshot AS peer_team, team.name_snapshot AS org_team, q.title_snapshot, s.score, s.updated_at FROM review_scores s JOIN review_assignments ra ON ra.id = s.assignment_id JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id JOIN evaluation_participants target ON target.id = ra.target_participant_id LEFT JOIN evaluation_peer_team_snapshots peer ON peer.id = ra.context_peer_team_snapshot_id LEFT JOIN evaluation_org_node_snapshots team ON team.id = ra.context_team_snapshot_id JOIN evaluation_cycle_questions q ON q.id = s.cycle_question_id WHERE ra.cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY reviewer.email_snapshot, ra.review_type, target.email_snapshot, q.sort_order_snapshot, q.id;"'
```

### Workflow F: delete one closed cycle safely

Inspect the target cycle first:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, snapshot_date, status, started_at, ended_at FROM evaluation_cycles WHERE id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$;"'
```

Delete only if `status = closed`:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM evaluation_cycles WHERE id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ AND status = \$\$closed\$\$ RETURNING id, name, snapshot_date, status;"'
```

That delete cascades participants, org snapshots, membership snapshots, cycle
questions, cycle guides, assignments, self-review answers, and review scores.

### Workflow F: delete one live user safely

Inspect the user:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, display_name, job_title, system_role, created_at FROM users WHERE email = \$\$\"PUT_USER_EMAIL_HERE\"\$\$;"'
```

Inspect live memberships:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT m.id, n.name, n.node_type, m.membership_role FROM organization_memberships m JOIN organization_nodes n ON n.id = m.organization_node_id JOIN users u ON u.id = m.user_id WHERE u.email = \$\$\"PUT_USER_EMAIL_HERE\"\$\$ ORDER BY m.id;"'
```

Delete the user:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM users WHERE email = \$\$\"PUT_USER_EMAIL_HERE\"\$\$ RETURNING id, email, display_name;"'
```

That delete cascades live sessions and live organization memberships. Cycle
snapshot data remains.

## Friendly Table Queries

### users

Role:

- Live user accounts.
- Hard-delete removes live sessions and live memberships.
- Cycle snapshots remain through `ON DELETE SET NULL` source pointers.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, display_name, job_title, system_role, created_at, updated_at FROM users ORDER BY email;"'
```

Delete one user by id:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM users WHERE id = \$\$\"PUT_USER_ID_HERE\"\$\$ RETURNING id, email, display_name;"'
```

### user_whitelist

Role:

- DB-managed Microsoft login allowlist.
- The env-managed `INITIALIZATION_EMAIL` is not stored here.
- CSV organization import deletes and recreates allowlist rows from imported `______USER` emails.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, created_at FROM user_whitelist ORDER BY email;"'
```

Add one email:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "INSERT INTO user_whitelist (email) VALUES (\$\$\"PUT_USER_EMAIL_HERE\"\$\$) ON CONFLICT (email) DO NOTHING RETURNING id, email;"'
```

Delete one allowlist row:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM user_whitelist WHERE email = \$\$\"PUT_USER_EMAIL_HERE\"\$\$ RETURNING id, email;"'
```

### user_sessions

Role:

- Server-side session rows for the browser `s1` cookie.

Inspect active sessions:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT s.id, u.email, s.created_at, s.expires_at, s.revoked_at, s.last_seen_at FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE s.revoked_at IS NULL AND s.expires_at > NOW() ORDER BY s.expires_at DESC;"'
```

Delete one session:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM user_sessions WHERE id = \$\$\"PUT_SESSION_ID_HERE\"\$\$ RETURNING id, user_id, expires_at, revoked_at;"'
```

### oauth_transactions

Role:

- Microsoft OAuth start/callback state.
- Startup cleanup removes expired/completed/non-pending rows.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, email, status, redirect_after, created_at, expires_at, completed_at, failure_reason FROM oauth_transactions ORDER BY created_at DESC;"'
```

Delete stale rows:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM oauth_transactions WHERE expires_at <= NOW() OR status <> \$\$pending\$\$ OR completed_at IS NOT NULL RETURNING id, email, status;"'
```

### organization_nodes

Role:

- Live organization tree.
- `company > head > team`.
- CSV organization import keeps the single root company node and rebuilds all non-root nodes.
- Cycle snapshots remain when live nodes change.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, node_type, parent_id, created_at, updated_at FROM organization_nodes ORDER BY id;"'
```

Delete one non-root node:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM organization_nodes WHERE id = \$\$\"PUT_NODE_ID_HERE\"\$\$ AND NOT (node_type = \$\$company\$\$ AND parent_id IS NULL) RETURNING id, name, node_type;"'
```

### organization_memberships

Role:

- Live user-to-node membership assignments.
- `member`: team member.
- `leader`: 관리자/본부장/팀장 depending on node type.
- CSV organization import recreates these rows from `______USER` and `______ASSIGNMENT`.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT m.id, m.user_id, u.email, n.id AS node_id, n.name AS node_name, n.node_type, m.membership_role, m.created_at FROM organization_memberships m JOIN users u ON u.id = m.user_id JOIN organization_nodes n ON n.id = m.organization_node_id ORDER BY n.id, CASE WHEN m.membership_role = \$\$leader\$\$ THEN 0 ELSE 1 END, m.id;"'
```

Delete one live membership:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM organization_memberships WHERE id = \$\$\"PUT_MEMBERSHIP_ID_HERE\"\$\$ RETURNING id, user_id, organization_node_id, membership_role;"'
```

### evaluation_questions

Role:

- Live editable question templates.
- Copied into `evaluation_cycle_questions` when a cycle starts.
- `manager_detail` rows must have `organization_node_id` set to a live organization team.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, evaluation_type, organization_node_id, title, weight, sort_order, is_active, created_at, updated_at FROM evaluation_questions ORDER BY evaluation_type, organization_node_id, sort_order, id;"'
```

Delete one template:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM evaluation_questions WHERE id = \$\$\"PUT_QUESTION_ID_HERE\"\$\$ RETURNING id, evaluation_type, title;"'
```

### evaluation_guides

Role:

- Live editable screen guide markdown.
- Copied into `evaluation_cycle_guides` when a cycle starts.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, evaluation_type, LEFT(content, 160) AS content_preview, created_at, updated_at FROM evaluation_guides ORDER BY evaluation_type;"'
```

Raw guide text:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT id, evaluation_type, content FROM evaluation_guides WHERE evaluation_type = \$\$peer\$\$;"'
```

### evaluation_system_state

Role:

- Single-row global status.
- `idle`: admin edits allowed.
- `running`: admin edits locked; users evaluate against current cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT s.id, s.status, s.current_cycle_id, c.name, c.snapshot_date FROM evaluation_system_state s LEFT JOIN evaluation_cycles c ON c.id = s.current_cycle_id;"'
```

Emergency unlock only if the app is stuck:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE evaluation_system_state SET status = \$\$idle\$\$, current_cycle_id = NULL, updated_at = NOW() WHERE id = 1 RETURNING *;"'
```

### evaluation_cycles

Role:

- Parent row for one evaluation run.
- Deleting a closed cycle deletes all snapshot, assignment, answer, and score
  rows for that cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, name, snapshot_date, status, started_at, ended_at, created_at FROM evaluation_cycles ORDER BY id DESC;"'
```

Delete one closed cycle:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DELETE FROM evaluation_cycles WHERE id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ AND status = \$\$closed\$\$ RETURNING id, name, snapshot_date, status;"'
```

### evaluation_participants

Role:

- User snapshot for one cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_user_id, email_snapshot, display_name_snapshot, job_title_snapshot, system_role_snapshot, sort_order FROM evaluation_participants ORDER BY cycle_id DESC, sort_order, id;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### evaluation_org_node_snapshots

Role:

- Organization node snapshot for one cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_node_id, name_snapshot, node_type_snapshot, parent_snapshot_id, sort_order FROM evaluation_org_node_snapshots ORDER BY cycle_id DESC, sort_order, id;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### evaluation_membership_snapshots

Role:

- User-to-node membership snapshot for one cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_membership_id, participant_id, org_node_snapshot_id, membership_role_snapshot, sort_order FROM evaluation_membership_snapshots ORDER BY cycle_id DESC, sort_order, id;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### evaluation_cycle_questions

Role:

- Question snapshot for one cycle.
- Scores and answers reference this table, not live `evaluation_questions`.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, source_question_id, evaluation_type, title_snapshot, weight_snapshot, sort_order_snapshot FROM evaluation_cycle_questions ORDER BY cycle_id DESC, evaluation_type, sort_order_snapshot, id;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### evaluation_cycle_guides

Role:

- Guide markdown snapshot for one cycle.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, evaluation_type, LEFT(content_markdown_snapshot, 160) AS guide_preview FROM evaluation_cycle_guides ORDER BY cycle_id DESC, evaluation_type;"'
```

Raw guide text:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT id, cycle_id, evaluation_type, content_markdown_snapshot FROM evaluation_cycle_guides WHERE cycle_id = \$\$\"PUT_CYCLE_ID_HERE\"\$\$ ORDER BY evaluation_type;"'
```

### review_assignments

Role:

- Generated evaluation edges for one cycle.
- `self`: reviewer evaluates self.
- `peer`: explicit peer-team members evaluate every member in their peer team, including self.
- `manager_detail`: team leaders evaluate team members; head memberships evaluate all members of teams under that head.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, cycle_id, review_type, reviewer_participant_id, target_participant_id, context_peer_team_snapshot_id, context_team_snapshot_id, context_head_snapshot_id, display_role_label_snapshot, status, submitted_at, sort_order FROM review_assignments ORDER BY cycle_id DESC, sort_order, id;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### self_review_answers

Role:

- Text answers for `self` assignments.
- Stores `cycle_id` and references same-cycle `review_assignments` and `evaluation_cycle_questions`.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT a.id, a.cycle_id, reviewer.email_snapshot, q.title_snapshot, LEFT(a.answer_text, 120) AS answer_preview, a.created_at, a.updated_at FROM self_review_answers a JOIN review_assignments ra ON ra.id = a.assignment_id JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id JOIN evaluation_cycle_questions q ON q.id = a.cycle_question_id ORDER BY a.cycle_id DESC, reviewer.email_snapshot, q.sort_order_snapshot;"'
```

Raw answer text:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT a.id, a.cycle_id, reviewer.email_snapshot, q.title_snapshot, a.answer_text FROM self_review_answers a JOIN review_assignments ra ON ra.id = a.assignment_id JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id JOIN evaluation_cycle_questions q ON q.id = a.cycle_question_id WHERE a.id = \$\$\"PUT_ANSWER_ID_HERE\"\$\$;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

### review_scores

Role:

- Numeric score cells for `peer` and `manager_detail`.
- Stores `cycle_id` and references same-cycle `review_assignments` and `evaluation_cycle_questions`.

Inspect:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT s.id, s.cycle_id, ra.review_type, reviewer.email_snapshot AS reviewer, target.email_snapshot AS target, q.title_snapshot, s.score, s.created_at, s.updated_at FROM review_scores s JOIN review_assignments ra ON ra.id = s.assignment_id JOIN evaluation_participants reviewer ON reviewer.id = ra.reviewer_participant_id LEFT JOIN evaluation_participants target ON target.id = ra.target_participant_id JOIN evaluation_cycle_questions q ON q.id = s.cycle_question_id ORDER BY s.cycle_id DESC, reviewer.email_snapshot, target.email_snapshot, q.sort_order_snapshot;"'
```

Cleanup:

- Delete the parent `evaluation_cycles` row.

## Quick Smoke Checks

Migration head:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT version_num FROM alembic_version;"'
```

Global evaluation state:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT status, current_cycle_id FROM evaluation_system_state;"'
```

Live user count:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS users FROM users;"'
```

Cycle row counts:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT c.id, c.name, c.status, COUNT(DISTINCT p.id) AS participants, COUNT(DISTINCT n.id) AS org_nodes, COUNT(DISTINCT m.id) AS memberships, COUNT(DISTINCT q.id) AS questions, COUNT(DISTINCT ra.id) AS assignments FROM evaluation_cycles c LEFT JOIN evaluation_participants p ON p.cycle_id = c.id LEFT JOIN evaluation_org_node_snapshots n ON n.cycle_id = c.id LEFT JOIN evaluation_membership_snapshots m ON m.cycle_id = c.id LEFT JOIN evaluation_cycle_questions q ON q.cycle_id = c.id LEFT JOIN review_assignments ra ON ra.cycle_id = c.id GROUP BY c.id ORDER BY c.id DESC;"'
```

Stale sessions:

```powershell
docker exec evaluation-protocol-postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, user_id, expires_at, revoked_at FROM user_sessions WHERE revoked_at IS NOT NULL OR expires_at <= NOW() ORDER BY expires_at DESC;"'
```

## Code Pointers

- SQLAlchemy models: `backend/app/db/postgres/models/evaluation.py`
- Alembic migrations: `backend/alembic/versions/`
- Migration runner: `backend/app/db/postgres/migrations.py`
- App entrypoint: `backend/app/main.py`
- Routers: `backend/app/api/`
- Domain services: `backend/app/services/`



