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

## Managed Tables

Current system tables:

```sql
select tablename
from pg_tables
where schemaname = 'public'
order by tablename;
```

Expected core tables:

- `alembic_version`
- `evaluation_guides`
- `evaluation_questions`
- `oauth_transactions`
- `organization_memberships`
- `organization_nodes`
- `peer_review_scores`
- `self_review_answers`
- `user_sessions`
- `user_whitelist`
- `users`

## Check Users

List persisted users:

```sql
select
  id,
  email,
  display_name,
  job_title,
  system_role,
  organization_node_id,
  created_at,
  updated_at
from users
order by email;
```

Find one user:

```sql
select *
from users
where email = 'adrian.kim@nextinsol.com';
```

## Check Whitelist

List DB-managed Microsoft email addresses:

```sql
select id, email, created_at
from user_whitelist
order by email;
```

Add a whitelist row:

```sql
insert into user_whitelist (email)
values ('someone@nextinsol.com')
on conflict (email) do nothing;
```

Remove a whitelist row:

```sql
delete from user_whitelist
where email = 'someone@nextinsol.com';
```

Removing a whitelist row directly does not delete an existing user or existing sessions. Prefer the admin API for normal removals because it deletes the whitelist row and matching user row in one operation.

`INITIALIZATION_EMAIL` in `.env` and `.env.local` is a protected bootstrap account. It is allowed by env, seeded as one hidden `admin` user, and deliberately not inserted into `user_whitelist`. The application checks `INITIALIZATION_EMAIL` first and then checks `user_whitelist`, so emails added through the admin UI remain valid even though they are not written back to the env file.

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

List expired or revoked sessions:

```sql
select
  s.id,
  u.email,
  s.created_at,
  s.expires_at,
  s.revoked_at
from user_sessions s
join users u on u.id = s.user_id
where s.revoked_at is not null
   or s.expires_at <= now()
order by s.expires_at desc;
```

Do not manually delete a single session for normal operations. Prefer logout, expiry, or the cleanup job.

Cleanup removes sessions where `expires_at <= now()` or `revoked_at is not null`. The backend runs this once on startup and then every `SESSION_CLEANUP_INTERVAL_MINUTES`.

## Check OAuth Transactions

List pending OAuth transactions:

```sql
select id, email, status, redirect_after, created_at, expires_at, completed_at
from oauth_transactions
where status = 'pending'
order by expires_at desc;
```

List OAuth rows that should be cleaned up:

```sql
select count(*) as stale_oauth_transactions
from oauth_transactions
where expires_at <= now()
   or status <> 'pending'
   or completed_at is not null;
```

OAuth cleanup removes expired, completed, denied, failed, and otherwise non-pending transaction rows. The backend runs it on startup and in the same hourly cleanup loop as sessions.

## Check Organization Tree

List organization nodes:

```sql
select id, name, node_type, parent_id, created_at, updated_at
from organization_nodes
order by id;
```

`NEXTIN` is seeded as the root `company` node at backend startup if it does not already exist.

List organization memberships:

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
order by n.id, m.membership_role desc, u.email;
```

Membership roles:

- `member`: regular assigned person
- `leader`: head leader or team leader depending on the node type

## Check Evaluation Data

List evaluation questions:

```sql
select id, evaluation_type, title, weight, sort_order, is_active, created_at, updated_at
from evaluation_questions
order by evaluation_type, sort_order, id;
```

List evaluation guide text:

```sql
select id, evaluation_type, left(content, 160) as content_preview, updated_at
from evaluation_guides
order by evaluation_type;
```

List self-review answers:

```sql
select
  a.id,
  u.email,
  q.title,
  left(a.answer_text, 120) as answer_preview,
  a.updated_at
from self_review_answers a
join users u on u.id = a.user_id
join evaluation_questions q on q.id = a.question_id
order by u.email, q.sort_order, q.id;
```

List same-team scores:

```sql
select
  s.id,
  reviewer.email as reviewer_email,
  team.name as team_name,
  target.email as target_email,
  q.title,
  s.score,
  s.updated_at
from peer_review_scores s
join users reviewer on reviewer.id = s.reviewer_user_id
join organization_nodes team on team.id = s.team_node_id
join users target on target.id = s.target_user_id
join evaluation_questions q on q.id = s.question_id
order by reviewer.email, team.id, target.email, q.sort_order, q.id;
```

## Delete A User

Delete users only when the account must be removed from the system. Do not delete the `INITIALIZATION_EMAIL` user unless you are rebuilding the environment.

First inspect the row:

```sql
select id, email, display_name, job_title, system_role
from users
where email = 'someone@nextinsol.com';
```

Delete by email:

```sql
delete from users
where email = 'someone@nextinsol.com';
```

User deletion removes that user's sessions and organization memberships through `on delete cascade`.

For a normal admin UI removal, call `DELETE /api/admin/whitelist/{email}`. That path deletes both `user_whitelist.email` and the matching `users.email`, then database cascades remove sessions and organization memberships.

## Emergency Role Change

System roles:

- `user`
- `admin`

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

## Admin Safety Note

At this stage DB-managed admins are equal. An admin can remove another DB-managed user's admin access through the application once admin management UI exists. The env-managed `INITIALIZATION_EMAIL` account is hidden from those admin lists and cannot be deleted through the normal whitelist API.

For now, use direct DB role changes as the break-glass recovery path. In a later operations/security phase, add stronger controls such as protected owner accounts, two-person approval, audit logging, or security-team-only role changes.
