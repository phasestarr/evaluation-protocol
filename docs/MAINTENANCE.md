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
- New schema changes should be represented in `backend/alembic/versions`.
- Keep the SQLAlchemy models and Alembic migrations aligned.
- Fresh deployments use the initial schema plus later migrations, so do not leave removed runtime columns in the initial migration.

## Evaluation State Rules

- `idle` is the only state where admin mutation is allowed.
- `running` locks whitelist, user, organization, membership, question, and guide edits.
- Starting a cycle snapshots the current user/tree/question/guide state and creates assignments.
- Stopping a cycle closes the current snapshot and returns to `idle`.
- If a user or question was missed, stop the current cycle, edit while idle, and start a new cycle.

## Cascade Rules

Live auth and organization cascades:

- `user_sessions.user_id -> users.id` cascades.
- `organization_memberships.user_id -> users.id` cascades.
- `organization_memberships.organization_node_id -> organization_nodes.id` cascades.
- `organization_nodes.parent_id -> organization_nodes.id` cascades for live tree subtree deletion.

Evaluation snapshot cascades:

- `evaluation_cycles` cascades to participants, org snapshots, membership snapshots, cycle questions, guides, assignments, answers, and scores.
- `review_assignments` cascades to `self_review_answers` and `review_scores`.
- `evaluation_cycle_questions` cascades to answer/score cells for that cycle question.

Do not connect running or closed answers/scores directly to live `users`, live `organization_nodes`, or live `evaluation_questions`. Live edits must affect only future cycles.

## Evaluation Question Rules

Live templates:

- `evaluation_type = 'self'`: no weight, textarea answers, 1000 character limit.
- `evaluation_type = 'peer'`: `weight > 0`, numeric score columns.
- `evaluation_type = 'manager_detail'`: `weight > 0`, reserved for leader-to-member detail scoring.

Effective weights are calculated from the active questions in the same evaluation type. Running evaluations calculate from the cycle question snapshot, not the live template table.

## Role Rules

Do not reintroduce a global `staff/manager` user role.

- Admin access is controlled only by `users.system_role`.
- Evaluation context and leader access are controlled by `organization_memberships`.
- The dashboard's team-member evaluation entry appears when the user has at least one `leader` membership.

## Peer Review Rules

Reviewable contexts:

- only `team` node memberships
- both `member` and `leader` memberships count
- duplicate memberships for the same team collapse to one context

Review targets:

- selected team memberships
- parent head memberships
- reviewer included when present in the selected target set
- sorted by tree path, role priority, and membership creation order
- deduplicated by participant after sorting

## Cache Rules

If users report old frontend UI after deploy:

- Verify `frontend/nginx/default.conf` still sends `Cache-Control: no-store` for `index.html`, SPA fallback routes, and `/api/`.
- Verify hashed Vite assets under `/assets/` are served with immutable caching.
- Browser cookies only contain the HttpOnly session cookie and are not a frontend UI cache.
