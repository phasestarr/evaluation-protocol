# Server Deploy

Run the stack behind sibling `root-proxy` on `edge-net`.

## Assumptions
- commands are run from `deploy/`.
- server env file lives at repo root as `../.env`.
- sibling `root-proxy` is already deployed.
- external Docker network `edge-net` already exists.
- `root-proxy` routes the service hostname to `evaluation-protocol:8080`.

## Commands

Start:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml up --build -d
```

Stop:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml down
```

Logs:

```bash
docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.server.yml logs -f
```

## Notes
- `docker-compose.server.yml` is the only place that should attach `frontend` to `edge-net`.
- The backend and PostgreSQL remain internal to this stack.
- This repo does not terminate TLS.
