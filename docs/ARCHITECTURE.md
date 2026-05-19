# Architecture

Evaluation Protocol is an internal HR evaluation app with a FastAPI backend, PostgreSQL state, and a Vite React frontend served by NGINX.

## Runtime Shape

- Frontend container serves the React bundle on port `8080`.
- Backend container serves FastAPI on port `8000`.
- Frontend NGINX proxies `/api/` to the backend.
- PostgreSQL stores auth/session state, whitelist data, organization tree data, evaluation questions, and evaluation answers/scores.
- Public traffic is expected to arrive through the sibling `root-proxy` service in server deployments.

## Auth Model

- Microsoft OAuth is initiated and completed by the backend.
- The browser stores only the `s1` HttpOnly session cookie.
- Session state is stored in `user_sessions`.
- Login is allowed when the email is either `INITIALIZATION_EMAIL` or present in `user_whitelist`.
- `INITIALIZATION_EMAIL` is a hidden bootstrap admin account and is not inserted into `user_whitelist`.

## User And Organization Model

- `users.system_role` is the only global user role.
  - `user`: regular employee.
  - `admin`: system administrator.
- Organization responsibility is not a global user property.
- Organization responsibility comes from `organization_memberships.membership_role`.
  - `member`: team member.
  - `leader`: company admin, head leader, or team leader depending on node type.
- Organization nodes are a fixed three-level tree:
  - `company`
  - `head`
  - `team`
- Current seeded root company is `NEXTIN`.
- One user may have multiple memberships.
- A user may have both `leader` and `member` memberships, even within the same team.

## Evaluation Model

Evaluation questions are stored in `evaluation_questions`. Evaluation screen guide text is stored in `evaluation_guides` and rendered as limited Markdown in the frontend.

- `self_review`: subjective self-review questions.
- `peer_review`: same-team numeric scoring questions.
- `direct_report_review`: team-member detail questions for leader workflows.

Self review:

- One answer per user per question.
- Stored in `self_review_answers`.
- Answers are limited to 1000 characters by API and UI.
- The submit button is currently a placeholder; saved answers remain editable.

Same-team review:

- The first page lists reviewable team contexts.
- A reviewable context is any `team` node where the current user has a membership.
- Head/company memberships do not create same-team review contexts.
- The detail page uses rows for target users and columns for peer-review questions.
- Scores are integers from 0 to 100.
- Scores are stored in `peer_review_scores`.
- The context key is `reviewer_user_id + team_node_id`.

Target selection for same-team review:

- Includes memberships on the selected team.
- Includes memberships on the selected team's parent head.
- Excludes the reviewer.
- Sorts by tree path, then `leader` before `member`, then membership creation order.
- Deduplicates by `user_id` after sorting, so a team leader/member duplicate appears once as the leader.
- The reviewer is included when they are part of the selected team or parent head target set.

## Caching

Frontend NGINX explicitly disables caching for:

- `index.html`
- SPA fallback routes
- `/api/`

Vite hashed assets under `/assets/` are cached as immutable long-lived files.
