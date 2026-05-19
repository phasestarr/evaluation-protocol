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
- Current seeded root company is `NEXTIN`.
- One user may have multiple memberships.
- A user may have both `leader` and `member` memberships, even within the same team.

## Evaluation State

The system has one global evaluation state row in `evaluation_system_state`.

- `idle`: admin can edit whitelist, users, organization tree, memberships, questions, and guides.
- `running`: admin editing is locked. User evaluation pages read from the active cycle snapshot.

Starting an evaluation creates a new `evaluation_cycles` row and snapshots the current live state into cycle-scoped tables. Stopping an evaluation closes the current cycle and returns the system to `idle`. Closed cycle data remains for later result viewing or explicit deletion.

## Evaluation Types

The canonical evaluation type values are:

- `self`: 자기평가
- `peer`: 동료평가
- `manager_detail`: 팀원평가

Live `evaluation_questions` and `evaluation_guides` are templates only. User-facing running evaluations use `evaluation_cycle_questions` and `evaluation_cycle_guides` snapshots.

## Cycle Snapshot Model

When an evaluation starts, the backend snapshots:

- users into `evaluation_participants`
- organization nodes into `evaluation_org_node_snapshots`
- memberships into `evaluation_membership_snapshots`
- active questions into `evaluation_cycle_questions`
- guide markdown into `evaluation_cycle_guides`
- review relationships into `review_assignments`

Answers and scores belong to assignments and cycle questions:

- `self_review_answers.assignment_id`
- `self_review_answers.cycle_question_id`
- `review_scores.assignment_id`
- `review_scores.cycle_question_id`

Live user, organization, and template deletion does not delete an already-opened or closed cycle. Explicit cycle deletion is allowed to cascade through the snapshot graph.

## Peer Assignment Rules

Peer reviewer contexts are generated from team memberships in the cycle snapshot.

- Only `team` memberships create peer contexts.
- Duplicate memberships for the same reviewer/team collapse to one context.
- Targets are the selected team memberships plus the parent head memberships.
- The reviewer is included when they are part of that target set.
- Targets are sorted by snapshot tree path, then `leader` before `member`, then membership creation order.
- Targets are deduplicated by participant after sorting, so a team leader/member duplicate appears once as the leader.

## Caching

Frontend NGINX explicitly disables caching for:

- `index.html`
- SPA fallback routes
- `/api/`

Vite hashed assets under `/assets/` are cached as immutable long-lived files.
