#!/bin/zsh
set -eu
LUMVIA_PROJECT_DIR="${0:A:h}"
cd "$LUMVIA_PROJECT_DIR"
"$LUMVIA_PROJECT_DIR/.venv/bin/python" scripts/run_local.py stop --all
