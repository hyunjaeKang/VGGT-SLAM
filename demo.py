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
    view.add_argument("--version", choices=["classic", "smooth"], default="classic")
    view.add_argument("--source-fps", type=float, default=10., help="V2 fallback FPS when timestamps are unavailable")
    versions = commands.add_parser("versions", help="choose between preserved Classic V1 and Smooth V2")
    versions.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()
    if args.command == "doctor":
        import torch
        print(json.dumps({"torch": torch.__version__, "mps": torch.backends.mps.is_available(), "cuda": torch.cuda.is_available(), "packages": {name: bool(importlib.util.find_spec(name)) for name in ("cv2", "viser", "sam3", "evo")}}, indent=2))
    elif args.command == 'versions':
        from vggt_slam.demo.version_picker import serve_picker
        serve_picker(args.port)
    elif args.command == "view":
        if args.version == 'smooth':
            from vggt_slam.demo.viewer_smooth import serve
            serve(args.run,args.port,source_fps=args.source_fps)
        else:
            from vggt_slam.demo.viewer import serve
            serve(args.run, args.port)
    else:
        try:
            print(prepare(json.loads(args.config.read_text())))
        except (ValueError, KeyError, OSError) as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
