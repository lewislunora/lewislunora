#!/usr/bin/env bash
# OMNITEST quick launcher
set -euo pipefail
cd "$(dirname "$0")"
PY=../.venv-omni/bin/python
[ -x "$PY" ] || PY=python3
TARGET="${TARGET:-omnitest.targets.gfg_win}"
exec "$PY" -m omnitest "$@"
