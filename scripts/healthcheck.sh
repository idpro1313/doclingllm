#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
DOCLING_URL="${DOCLING_URL:-http://localhost:5001}"

check_url() {
  local name="$1"
  local url="$2"
  if curl -sf "${url}" >/dev/null; then
    echo "[OK] ${name}: ${url}"
    return 0
  fi
  echo "[FAIL] ${name}: ${url}" >&2
  return 1
}

failed=0
check_url "gateway" "${GATEWAY_URL}/health" || failed=1
check_url "docling-serve" "${DOCLING_URL}/health" || failed=1

exit "${failed}"
