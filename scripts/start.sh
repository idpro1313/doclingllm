#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEPLOY_DIR="${PROJECT_ROOT}/deploy"
ENV_FILE="${DEPLOY_DIR}/.env"
ENV_DEFAULTS="${DEPLOY_DIR}/.env.defaults"

echo "[doclingllm] Starting stack from ${DEPLOY_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Engine on Ubuntu." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 not found." >&2
  exit 1
fi

ensure_env_file() {
  if [[ ! -f "${ENV_DEFAULTS}" ]]; then
    echo "ERROR: ${ENV_DEFAULTS} not found." >&2
    exit 1
  fi
  if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${ENV_DEFAULTS}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo "[doclingllm] Created ${ENV_FILE} from .env.defaults"
  fi
}

read_current_vision_api_key() {
  local line
  line="$(grep -E '^VISION_API_KEY=' "${ENV_FILE}" | tail -n 1 || true)"
  line="${line#VISION_API_KEY=}"
  printf '%s' "${line}"
}

vision_api_key_is_missing() {
  local value
  value="$(read_current_vision_api_key)"
  [[ -z "${value}" || "${value}" == "replace-with-your-cloud-ru-token" ]]
}

write_vision_api_key() {
  local vision_key="$1"
  local tmp_file
  tmp_file="$(mktemp)"
  grep -v '^VISION_API_KEY=' "${ENV_FILE}" > "${tmp_file}" || true
  printf 'VISION_API_KEY=%s\n' "${vision_key}" >> "${tmp_file}"
  mv "${tmp_file}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
}

prompt_for_vision_api_key() {
  local vision_key=""
  if [[ ! -t 0 ]]; then
    echo "ERROR: VISION_API_KEY is not set in ${ENV_FILE} and stdin is not a TTY." >&2
    echo "Set VISION_API_KEY in ${ENV_FILE} or run ./scripts/start.sh interactively." >&2
    exit 1
  fi
  echo -n "Enter VISION_API_KEY (ai-billing.develonica.group): "
  read -rs vision_key
  echo
  if [[ -z "${vision_key}" ]]; then
    echo "ERROR: VISION_API_KEY is required." >&2
    exit 1
  fi
  write_vision_api_key "${vision_key}"
  echo "[doclingllm] VISION_API_KEY saved to ${ENV_FILE}"
}

ensure_env_file

if vision_api_key_is_missing; then
  prompt_for_vision_api_key
fi

cd "${DEPLOY_DIR}"
docker compose up -d --build

echo "[doclingllm] Waiting for healthchecks..."
sleep 5
"${SCRIPT_DIR}/healthcheck.sh"

echo "[doclingllm] Stack is up."
echo "  docling-serve API: http://localhost:5001"
echo "  docling UI:        http://localhost:5001/ui"
echo "  gateway (internal): http://model-gateway:8080"
