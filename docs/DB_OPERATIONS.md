# Database Operations

This document covers direct PostgreSQL checks and emergency maintenance for the evaluation system.

## Access

Run commands from `deploy/`.

Local:

```bash
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Server:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Expected Core Tables

- `alembic_version`
- `evaluation_cycles`
- `evaluation_system_state`
- `evaluation_participants`
- `evaluation_org_node_snapshots`
- `evaluation_membership_snapshots`
- `evaluation_cycle_questions`
- `evaluation_cycle_guides`
- `evaluation_guides`
- `evaluation_questions`
- `oauth_transactions`
- `organization_memberships`
- `organization_nodes`
- `review_assignments`
- `review_scores`
- `self_review_answers`
- `user_sessions`
- `user_whitelist`
- `users`

## Check Users

```sql
select id, email, display_name, job_title, system_role, created_at, updated_at
from users
order by email;
```

## Check Evaluation State

```sql
select s.id, s.status, s.current_cycle_id, c.name, c.snapshot_date, c.started_at, c.ended_at
from evaluation_system_state s
left join evaluation_cycles c on c.id = s.current_cycle_id;
```

List cycles:

```sql
select id, name, snapshot_date, status, started_at, ended_at
from evaluation_cycles
order by id desc;
```

Delete a closed cycle and all snapshot data:

```sql
delete from evaluation_cycles
where id = 123
  and status = 'closed';
```

Do not delete a `running` cycle directly. Stop it through the admin API first so `evaluation_system_state` returns to `idle`.

## Check Whitelist

```sql
select id, email, created_at
from user_whitelist
order by email;
```

`INITIALIZATION_EMAIL` is allowed by env, seeded as one hidden `admin` user, and deliberately not inserted into `user_whitelist`.

## Check Sessions

List active sessions:

```sql
select
  s.id,
  u.email,
  s.created_at,
  s.expires_at,
  s.revoked_at,
  s.last_seen_at
from user_sessions s
join users u on u.id = s.user_id
where s.revoked_at is null
  and s.expires_at > now()
order by s.expires_at desc;
```

Cleanup removes sessions where `expires_at <= now()` or `revoked_at is not null`. The backend runs this once on startup and then every `SESSION_CLEANUP_INTERVAL_MINUTES`.

## Check Organization Tree

```sql
select id, name, node_type, parent_id, created_at, updated_at
from organization_nodes
order by id;
```

`NEXTIN` is seeded as the root `company` node at backend startup if it does not already exist.

List live memberships:

```sql
select
  m.id,
  u.email,
  n.name as organization_node,
  n.node_type,
  m.membership_role,
  m.created_at
from organization_memberships m
join users u on u.id = m.user_id
join organization_nodes n on n.id = m.organization_node_id
order by n.id, m.membership_role desc, m.id;
```

Live organization edits affect only future cycles after the next evaluation start.

## Check Evaluation Templates

```sql
select id, evaluation_type, title, weight, sort_order, is_active, created_at, updated_at
from evaluation_questions
order by evaluation_type, sort_order, id;
```

```sql
select id, evaluation_type, left(content, 160) as content_preview, updated_at
from evaluation_guides
order by evaluation_type;
```

Canonical evaluation types are `self`, `peer`, and `manager_detail`.

## Check Cycle Snapshot

Participants:

```sql
select id, cycle_id, source_user_id, email_snapshot, display_name_snapshot, job_title_snapshot, system_role_snapshot, sort_order
from evaluation_participants
where cycle_id = 123
order by sort_order, id;
```

Organization snapshot:

```sql
select id, cycle_id, source_node_id, name_snapshot, node_type_snapshot, parent_snapshot_id, sort_order
from evaluation_org_node_snapshots
where cycle_id = 123
order by sort_order, id;
```

Membership snapshot:

```sql
select
  m.id,
  p.email_snapshot,
  n.name_snapshot,
  n.node_type_snapshot,
  m.membership_role_snapshot,
  m.sort_order
from evaluation_membership_snapshots m
join evaluation_participants p on p.id = m.participant_id
join evaluation_org_node_snapshots n on n.id = m.org_node_snapshot_id
where m.cycle_id = 123
order by m.sort_order, m.id;
```

Cycle questions:

```sql
select id, cycle_id, source_question_id, evaluation_type, title_snapshot, weight_snapshot, sort_order_snapshot
from evaluation_cycle_questions
where cycle_id = 123
order by evaluation_type, sort_order_snapshot, id;
```

## Check Evaluation Inputs

Self-review answers:

```sql
select
  a.id,
  reviewer.email_snapshot,
  q.title_snapshot,
  left(a.answer_text, 120) as answer_preview,
  a.updated_at
from self_review_answers a
join review_assignments ra on ra.id = a.assignment_id
join evaluation_participants reviewer on reviewer.id = ra.reviewer_participant_id
join evaluation_cycle_questions q on q.id = a.cycle_question_id
where ra.cycle_id = 123
order by reviewer.email_snapshot, q.sort_order_snapshot, q.id;
```

Peer scores:

```sql
select
  s.id,
  reviewer.email_snapshot as reviewer_email,
  team.name_snapshot as team_name,
  target.email_snapshot as target_email,
  q.title_snapshot,
  s.score,
  s.updated_at
from review_scores s
join review_assignments ra on ra.id = s.assignment_id
join evaluation_participants reviewer on reviewer.id = ra.reviewer_participant_id
join evaluation_participants target on target.id = ra.target_participant_id
left join evaluation_org_node_snapshots team on team.id = ra.context_team_snapshot_id
join evaluation_cycle_questions q on q.id = s.cycle_question_id
where ra.cycle_id = 123
  and ra.review_type = 'peer'
order by reviewer.email_snapshot, team.sort_order, target.email_snapshot, q.sort_order_snapshot, q.id;
```

## Delete A User

Delete users only when the account must be removed from the live system. Do not delete the `INITIALIZATION_EMAIL` user unless you are rebuilding the environment.

```sql
delete from users
where email = 'someone@nextinsol.com';
```

User deletion removes that user's sessions and live organization memberships. Existing evaluation cycle snapshots remain.

For normal admin UI removal, call `DELETE /api/admin/whitelist/{email}` while the system is `idle`. That path deletes both `user_whitelist.email` and the matching `users.email`, then database cascades remove sessions and live memberships.

## Emergency Role Change

Promote a user to system admin:

```sql
update users
set system_role = 'admin',
    updated_at = now()
where email = 'adrian.kim@nextinsol.com';
```

Demote a user from system admin:

```sql
update users
set system_role = 'user',
    updated_at = now()
where email = 'someone@nextinsol.com';
```

The env-managed `INITIALIZATION_EMAIL` account is hidden from normal admin lists and cannot be deleted through the whitelist API.
