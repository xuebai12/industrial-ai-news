#!/bin/bash
# Backward-compatible wrapper. Use the stable scheduler entrypoint.
set -euo pipefail

cd "$(dirname "$0")"
exec ./run_scheduled_dispatch.sh
