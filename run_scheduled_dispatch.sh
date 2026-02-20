#!/bin/bash
# Stable scheduled entrypoint: fixed cwd/venv, lock protection, logs, dashboard + alerts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing python runtime: ${PYTHON_BIN}"
  exit 1
fi

mkdir -p logs output
today="$(date +%Y-%m-%d)"
ts="$(date +%Y%m%d-%H%M%S)"
log_file="logs/scheduled-${ts}.log"
lock_dir="/tmp/industrial-ai-news.lock"

cleanup() {
  rm -rf "${lock_dir}"
}
trap cleanup EXIT

if ! mkdir "${lock_dir}" 2>/dev/null; then
  echo "Another scheduled run is active; exiting."
  exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting scheduled dispatch..."

"${PYTHON_BIN}" main.py \
  --output both \
  --output-dir output \
  --log-format json \
  | tee "${log_file}"

"${PYTHON_BIN}" ops_dashboard.py \
  --output-dir output \
  --days 7 \
  --send-alert-email \
  | tee -a "${log_file}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Completed."
echo "Log: ${log_file}"
echo "Summary: output/run-summary-${today}.json"
echo "Dashboard: output/ops-dashboard.md"
