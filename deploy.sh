#!/usr/bin/env bash
# deploy.sh – one‑liner to launch Sentinel locally or on a server
# Usage: ./deploy.sh   (makes sure Docker is running, builds and starts the stack)

set -euo pipefail

# Ensure Docker daemon is reachable
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Please start Docker Desktop (Windows) or the Docker daemon." >&2
  exit 1
fi

# Build and start services in detached mode
docker compose up --build -d

echo "✅ Sentinel stack is up. Dashboard: http://localhost:3000   API: http://localhost:8000/api"
