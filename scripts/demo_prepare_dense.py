"""Prepare a high-density display cache without rerunning VGGT."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vggt_slam.demo.dense_display import prepare_dense_display

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-frame', type=int, default=20000)
    parser.add_argument('--max-frames', type=int)
    args = parser.parse_args()
    result = prepare_dense_display(args.run, args.output, args.per_frame, args.max_frames)
    print(json.dumps({k: v for k, v in result.items() if k not in ('frames', 'submaps')}, indent=2))
