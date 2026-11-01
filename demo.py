"""Prepare a VGGT-SLAM demo run without starting inference."""
import argparse
import importlib.util
import json
from pathlib import Path

from vggt_slam.demo.prepare import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="show optional package and device availability")
    prep = commands.add_parser("prepare", help="validate images and create a new run; does not run inference")
    prep.add_argument("--config", type=Path, required=True, help="JSON: run_id and image_dir with optional start/end, or source_mode=cached_playback with existing_assets and pose_first_column")
    view = commands.add_parser("view", help="open a cached run without loading inference models")
    view.add_argument("--run", type=Path, required=True, help="run directory containing manifest.json")
    view.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    if args.command == "doctor":
        import torch
        print(json.dumps({"torch": torch.__version__, "mps": torch.backends.mps.is_available(), "cuda": torch.cuda.is_available(), "packages": {name: bool(importlib.util.find_spec(name)) for name in ("cv2", "viser", "sam3", "evo")}}, indent=2))
    elif args.command == "view":
        from vggt_slam.demo.viewer import serve
        serve(args.run, args.port)
    else:
        try:
            print(prepare(json.loads(args.config.read_text())))
        except (ValueError, KeyError, OSError) as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
