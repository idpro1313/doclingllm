#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_DIR="${PROJECT_ROOT}/deploy"
ENV_FILE="${DEPLOY_DIR}/.env"

echo "[doclingllm] Starting stack from ${DEPLOY_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Engine on Ubuntu." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 not found." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Copy deploy/.env.example to deploy/.env and set VISION_API_KEY." >&2
  exit 1
fi

cd "${DEPLOY_DIR}"
docker compose up -d --build

echo "[doclingllm] Waiting for healthchecks..."
sleep 5
"${SCRIPT_DIR}/healthcheck.sh"

echo "[doclingllm] Stack is up."
echo "  docling-serve: http://localhost:5001"
echo "  gateway (internal): http://model-gateway:8080"
