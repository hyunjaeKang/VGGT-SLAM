#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON="${PYTHON:-python3}"
WITH_OPEN_SET=0
if [[ "${1:-}" == "--with-open-set" ]]; then
    WITH_OPEN_SET=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--with-open-set]" >&2
    exit 2
fi

# Use the active environment's interpreter for every installation.
"$PYTHON" -m pip install -r requirements.txt
mkdir -p third_party
clone_if_missing() {
    if [[ ! -d "$2/.git" ]]; then
        git clone --depth 1 "$1" "$2"
    fi
}
clone_if_missing https://github.com/Dominic101/salad.git third_party/salad
clone_if_missing https://github.com/MIT-SPARK/VGGT_SPARK.git third_party/vggt
"$PYTHON" scripts/patch_vggt.py
"$PYTHON" -m pip install -e ./third_party/salad -e ./third_party/vggt -e .

# These are only used by --run_os and have additional platform requirements.
if [[ "$WITH_OPEN_SET" == 1 ]]; then
    clone_if_missing https://github.com/facebookresearch/perception_models.git third_party/perception_models
    clone_if_missing https://github.com/facebookresearch/sam3.git third_party/sam3
    "$PYTHON" -m pip install -e ./third_party/perception_models -e ./third_party/sam3
fi

echo "Installation complete. Unzip office_loop.zip, then run:"
echo "$PYTHON main.py --image_folder office_loop --max_loops 1 --vis_map --keep_alive"
