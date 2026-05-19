# Maintenance

This document records operational rules that are easy to forget while changing the evaluation system.

## Local Checks

Use the helper artifacts described in `README.md` for local checks:

```powershell
backend\.venv\Scripts\python.exe -m compileall backend\app backend\alembic
cd frontend
npm run typecheck
npm run build
```

`backend/.venv`, `frontend/node_modules`, and `frontend/dist` are disposable local helper artifacts and are ignored by git.

## Database Migrations

- The backend runs Alembic migrations on startup.
- New schema changes should be represented in `backend/alembic/versions`.
- Keep the SQLAlchemy models and Alembic migrations aligned.
- Existing deployments migrate through the full version chain.
- Fresh deployments use the initial schema plus later migrations, so do not leave removed runtime columns in the initial migration.

## Cascade Rules

Deleting a user cascades to:

- `user_sessions`
- `organization_memberships`
- `self_review_answers`
- `peer_review_scores` where the user is reviewer or target

Deleting an organization node cascades to:

- `organization_memberships`
- `peer_review_scores` for that team node

Application code also clears `users.organization_node_id` for deleted organization subtrees before deleting nodes.

Deleting an evaluation question cascades to:

- `self_review_answers`
- `peer_review_scores`

Question deletion is therefore destructive. Use it only when responses for that question should also be removed.

## Evaluation Question Rules

Self-review questions:

- `evaluation_type = 'self_review'`
- `weight = null`
- rendered as textarea questions
- answer limit is 1000 characters

Same-team questions:

- `evaluation_type = 'peer_review'`
- `weight > 0`
- effective weight is calculated at read time from active peer-review questions
- rendered as numeric score columns

Team-member detail questions:

- `evaluation_type = 'direct_report_review'`
- `weight > 0`
- managed separately from same-team questions
- user-facing workflow is not wired yet

## Role Rules

Do not reintroduce a global `staff/manager` user role.

- Admin access is controlled only by `users.system_role`.
- Evaluation context and team-lead access are controlled by `organization_memberships`.
- The dashboard's team detail entry appears when the user has at least one `leader` membership.

## Same-Team Review Rules

Reviewable contexts:

- only `team` node memberships
- both `member` and `leader` memberships count
- duplicate memberships for the same team collapse to one context

Review targets:

- selected team memberships
- parent head memberships
- reviewer included when present in the selected target set
- sorted by tree path, role priority, and membership creation order
- deduplicated by user after sorting

## Cache Rules

If users report old frontend UI after deploy:

- Verify `frontend/nginx/default.conf` still sends `Cache-Control: no-store` for `index.html`, SPA fallback routes, and `/api/`.
- Verify hashed Vite assets under `/assets/` are served with immutable caching.
- Browser cookies only contain the HttpOnly session cookie and are not a frontend UI cache.
