#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_DIR="${PROJECT_ROOT}/deploy"

DO_GIT_PULL=1
DO_BUILD=1
SERVICES=(model-gateway)

usage() {
  cat <<'EOF'
Usage: ./scripts/redeploy-fast.sh [OPTIONS]

Quick redeploy with Docker layer cache (no --no-cache, no full stack down).

Default: git pull → build model-gateway → up -d model-gateway → healthcheck

Options:
  --all           Rebuild and restart model-gateway + docling-serve
  --docling       Rebuild and restart docling-serve only
  --gateway       Rebuild and restart model-gateway only (default)
  --no-build      git pull + docker compose up -d (restart, use existing images)
  --no-pull       Skip git pull
  -h, --help      Show this help

Examples:
  ./scripts/redeploy-fast.sh
  ./scripts/redeploy-fast.sh --all
  ./scripts/redeploy-fast.sh --no-build
  ./scripts/redeploy-fast.sh --no-pull --gateway

Full rebuild (both services, compose down/up): ./scripts/redeploy.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      SERVICES=(model-gateway docling-serve)
      shift
      ;;
    --docling)
      SERVICES=(docling-serve)
      shift
      ;;
    --gateway)
      SERVICES=(model-gateway)
      shift
      ;;
    --no-build)
      DO_BUILD=0
      shift
      ;;
    --no-pull)
      DO_GIT_PULL=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 not found." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"

if [[ "${DO_GIT_PULL}" -eq 1 ]]; then
  if [[ ! -d "${PROJECT_ROOT}/.git" ]]; then
    echo "ERROR: ${PROJECT_ROOT} is not a git repository." >&2
    exit 1
  fi
  echo "[doclingllm] git pull"
  git pull
fi

cd "${DEPLOY_DIR}"

service_list="${SERVICES[*]}"
echo "[doclingllm] Fast redeploy services: ${service_list}"

if [[ "${DO_BUILD}" -eq 1 ]]; then
  echo "[doclingllm] docker compose build ${service_list}"
  docker compose build "${SERVICES[@]}"
else
  echo "[doclingllm] Skipping build (--no-build)"
fi

echo "[doclingllm] docker compose up -d ${service_list}"
docker compose up -d "${SERVICES[@]}"

echo "[doclingllm] Waiting for healthchecks..."
sleep 3
"${SCRIPT_DIR}/healthcheck.sh"

echo "[doclingllm] Fast redeploy complete."
echo "  gateway admin UI:  http://localhost:8080/admin"
echo "  docling UI:        http://localhost:5001/ui"
