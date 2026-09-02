#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
BASE_COMPOSE="$DIR/docker-compose.yml"
VOLUMES_COMPOSE="$DIR/docker-compose-volumes.yml"

echo "🛑 Deteniendo context_graph..."

if [ -f "$VOLUMES_COMPOSE" ]; then
  docker compose -f "$BASE_COMPOSE" -f "$VOLUMES_COMPOSE" down
else
  docker compose -f "$BASE_COMPOSE" down
fi

echo "✅ context_graph detenido correctamente."
