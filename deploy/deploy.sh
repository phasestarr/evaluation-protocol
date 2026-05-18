#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-server}"
ACTION="${2:-up}"

case "$MODE" in
  local)
    ENV_FILE="../.env.local"
    OVERRIDE_FILE="docker-compose.local.yml"
    ;;
  server)
    ENV_FILE="../.env"
    OVERRIDE_FILE="docker-compose.server.yml"
    ;;
  *)
    echo "Usage: ./deploy.sh [local|server] [up|down|restart|logs|ps]"
    exit 1
    ;;
esac

case "$ACTION" in
  up)
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" up --build -d
    ;;
  down)
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" down
    ;;
  restart)
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" restart
    ;;
  logs)
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" logs -f
    ;;
  ps)
    docker compose --env-file "$ENV_FILE" -f docker-compose.yml -f "$OVERRIDE_FILE" ps
    ;;
  *)
    echo "Usage: ./deploy.sh [local|server] [up|down|restart|logs|ps]"
    exit 1
    ;;
esac
