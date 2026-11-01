#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PYTHON="${PYTHON:-$PWD/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
    echo "Create the Python 3.11 environment and run setup.sh first (see README.md)." >&2
    exit 1
fi
unzip -qn office_loop.zip
mkdir -p logs
exec "$PYTHON" -u main.py --image_folder office_loop --max_loops 1 \
    --vis_map --keep_alive --log_results --log_path logs/office_loop_poses.txt "$@"
