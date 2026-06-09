#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
repo_root=$(CDPATH= cd -- .. && pwd)

env_example="$repo_root/.env.example"
server_env="$repo_root/.env"
local_env="$repo_root/.env.local"

copy_if_missing() {
    source_file="$1"
    target_file="$2"
    label="$3"

    if [ ! -f "$target_file" ]; then
        cp "$source_file" "$target_file"
        echo "Created $label: $target_file"
    else
        echo "Found existing $label: $target_file"
    fi
}

copy_if_missing "$env_example" "$server_env" "server env"

if [ ! -f "$local_env" ]; then
    sed "s/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=false/" "$env_example" > "$local_env"
    echo "Created local env: $local_env"
else
    echo "Found existing local env: $local_env"
fi

if docker network inspect edge-net >/dev/null 2>&1; then
    echo "Found Docker network edge-net"
else
    docker network create edge-net >/dev/null
    echo "Created Docker network edge-net"
fi

server_placeholders=$(grep -n '\$your-' "$server_env" || true)
local_placeholders=$(grep -n '\$your-' "$local_env" || true)

cat <<EOF
evaluation-protocol setup complete.

Container status: not started
Server env: $server_env
Local env: $local_env

Next steps:
1. Replace placeholder values in .env before server deployment.
2. Replace placeholder values in .env.local before local deployment.
3. Use deploy/README-SERVER.md or deploy/README-LOCAL.md for Docker Compose commands.
EOF

if [ -n "$server_placeholders" ]; then
    printf '\nServer placeholders still present:\n%s\n' "$server_placeholders"
fi

if [ -n "$local_placeholders" ]; then
    printf '\nLocal placeholders still present:\n%s\n' "$local_placeholders"
fi
