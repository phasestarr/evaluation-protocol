# Server Deploy

Run the stack behind sibling `root-proxy` on `edge-net`.

## Assumptions

- Commands are run from `evaluation-protocol/deploy`
- Server env file lives at repo root as `../.env`
- Sibling `root-proxy` is already deployed
- External Docker network `edge-net` exists or can be created by setup
- `root-proxy` routes `evaluation.example.com` to `evaluation-protocol:8080`
- Microsoft Entra production app registration includes redirect URI `https://evaluation.example.com/api/v1/auth/callback/microsoft`

## First-Time Setup

```bash
cd ~/evaluation-protocol/deploy && sh deploy.sh
```

Before first startup:

- replace every `$your-...` placeholder in `../.env`
- keep `SESSION_COOKIE_SECURE=true`
- keep `EVALUATION_PROTOCOL_CONTAINER_NAME=evaluation-protocol` unless sibling `root-proxy` changes too
- set `INITIALIZATION_EMAIL` to the first bootstrap admin account
- set `COMPANY_EMAIL_DOMAIN` to the allowed user email domain

## Commands

Start:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml up --build -d
```

Stop:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml down
```

Restart:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml restart
```

Logs:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml logs -f
```

## Notes

- `docker-compose.server.yml` is the only place that should attach `frontend` to `edge-net`
- The backend and PostgreSQL remain internal to this stack
- This repo does not terminate TLS; TLS stays in sibling `root-proxy`
- Missing env values fail during Docker Compose interpolation before startup
- Placeholder `$your-...` values are intentionally visible in `.env` until replaced
