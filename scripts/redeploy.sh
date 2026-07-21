#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "[doclingllm] Redeploy from ${PROJECT_ROOT}"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git not found." >&2
  exit 1
fi

if [[ ! -d "${PROJECT_ROOT}/.git" ]]; then
  echo "ERROR: ${PROJECT_ROOT} is not a git repository." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"
echo "[doclingllm] git pull"
git pull

"${SCRIPT_DIR}/stop.sh"
"${SCRIPT_DIR}/start.sh"

echo "[doclingllm] Redeploy complete."
