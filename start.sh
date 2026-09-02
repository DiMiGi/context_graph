#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
CONFIG_FILE="$DIR/projects_config.json"
EXAMPLE_FILE="$DIR/projects_config.example.json"
BASE_COMPOSE="$DIR/docker-compose.yml"
VOLUMES_COMPOSE="$DIR/docker-compose-volumes.yml"

if [ ! -f "$CONFIG_FILE" ]; then
  if [ -f "$EXAMPLE_FILE" ]; then
    echo "⚠️ projects_config.json no existe. Creándolo desde projects_config.example.json..."
    cp "$EXAMPLE_FILE" "$CONFIG_FILE"
  fi
fi

# 1. Extraer volúmenes dinámicos usando exclusivamente Bash puro POSIX
VOLUMES_LIST=""

if [ -f "$CONFIG_FILE" ]; then
  while read -r host_path id; do
    if [ -n "$host_path" ]; then
      host_path=$(echo "$host_path" | sed -e 's/^[ "]*//' -e 's/[ ",]*$//')
      id=$(echo "$id" | sed -e 's/^[ "]*//' -e 's/[ ",]*$//')

      # Inferir automáticamente container_path del nombre de la carpeta de host_path
      folder_name=$(basename "$host_path")
      container_path="/sources/$folder_name"

      if [ -n "$host_path" ] && [ -n "$container_path" ]; then
        VOLUMES_LIST="${VOLUMES_LIST}\n      - ${host_path}:${container_path}:ro"
      fi
    fi
  done < <(grep -E '"(host_path|id)"' "$CONFIG_FILE" | awk '
    /"id"/ { gsub(/.*"id"[ \t]*:[ \t]*"/, ""); gsub(/".*/, ""); id=$0 }
    /"host_path"/ { gsub(/.*"host_path"[ \t]*:[ \t]*"/, ""); gsub(/".*/, ""); hp=$0; print hp, id; hp=""; id="" }
    END { if (hp != "") print hp, id }
  ')
fi

# 2. Generar docker-compose-volumes.yml (override)
cat << COMPOSE_OVERRIDE_EOF > "$VOLUMES_COMPOSE"
services:
  context_graph:
    volumes:$(echo -e "$VOLUMES_LIST")
COMPOSE_OVERRIDE_EOF

echo "✅ 'docker-compose-volumes.yml' generado dinámicamente con inferencia automática de rutas."

# 3. Levantar combinando el base y el archivo de volúmenes dinámico
echo "🚀 Levantando context_graph..."
docker compose -f "$BASE_COMPOSE" -f "$VOLUMES_COMPOSE" up -d --build
echo "🌐 context_graph listo en http://localhost:8899"
