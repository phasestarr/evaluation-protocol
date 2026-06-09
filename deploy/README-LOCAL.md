# Local Deploy

Run the stack directly on `localhost` without sibling `root-proxy`.

## Assumptions

- Commands are run from `evaluation-protocol/deploy`
- Local env file lives at repo root as `../.env.local`
- Frontend is published on `http://localhost:8080`
- Local runtime uses a separate Microsoft Entra app registration from server runtime
- Local env keeps `SESSION_COOKIE_SECURE=false`

## First-Time Setup

```powershell
cd ~/evaluation-protocol/deploy && sh deploy.sh
```

Before first startup:

- replace every `$your-...` placeholder in `../.env.local`
- keep `SESSION_COOKIE_SECURE=false`
- confirm the Microsoft local app registration includes redirect URI `http://localhost:8080/api/v1/auth/callback/microsoft`

## Commands

Start:

```powershell
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml up --build -d
```

Stop:

```powershell
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml down
```

Restart:

```powershell
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml restart
```

Logs:

```powershell
docker compose --env-file ../.env.local -f docker-compose.yml -f docker-compose.local.yml logs -f
```

## Notes

- `docker-compose.local.yml` is the only place that should expose port `8080` to the host
- Local runtime does not require sibling `root-proxy`
- The backend and PostgreSQL remain internal to this stack
- Missing env values fail during Docker Compose interpolation before startup
- Placeholder `$your-...` values are intentionally visible in `.env.local` until replaced
