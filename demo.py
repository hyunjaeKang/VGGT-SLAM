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
    view.add_argument("--version", choices=["classic", "smooth", "live4", "slam5"], default="classic")
    view.add_argument("--source-fps", type=float, default=10., help="V2 fallback FPS when timestamps are unavailable")
    versions = commands.add_parser("versions", help="choose between preserved Classic V1 and Smooth V2")
    versions.add_argument("--port", type=int, default=8100)
    live = commands.add_parser("live", help="Live V3: choose a video and build a new searchable map")
    live.add_argument("--port", type=int, default=8103)
    live.add_argument("--viewer-port", type=int, default=8104)
    view.add_argument("--live-control", type=Path, help=argparse.SUPPRESS)
    view.add_argument("--studio-label", default="Smooth V2", help=argparse.SUPPRESS)
    live4=commands.add_parser('live4',help='Live V4: resident predefined-object tracking during mapping')
    live4.add_argument('--port',type=int,default=8105)
    live4.add_argument('--viewer-port',type=int,default=8106)
    live5=commands.add_parser("live5",help="SLAM V5: VGGT-SLAM only, adjustable inference resolution")
    live5.add_argument("--port",type=int,default=8107)
    live5.add_argument("--viewer-port",type=int,default=8108)
    args = parser.parse_args()
    if args.command == "doctor":
        import torch
        print(json.dumps({"torch": torch.__version__, "mps": torch.backends.mps.is_available(), "cuda": torch.cuda.is_available(), "packages": {name: bool(importlib.util.find_spec(name)) for name in ("cv2", "viser", "sam3", "evo")}}, indent=2))
    elif args.command == "live5":
        from vggt_slam.demo.live_studio5 import serve_v5
        serve_v5(args.port,args.viewer_port)
    elif args.command == 'live4':
        from vggt_slam.demo.live_studio4 import serve_v4
        serve_v4(args.port,args.viewer_port)
    elif args.command == 'live':
        from vggt_slam.demo.live_studio import serve_live
        serve_live(args.port, args.viewer_port)
    elif args.command == 'versions':
        from vggt_slam.demo.version_picker import serve_picker
        serve_picker(args.port)
    elif args.command == "view":
        if args.version == 'slam5':
            from vggt_slam.demo.viewer_slam5 import serve
            serve(args.run,args.port,source_fps=args.source_fps,live_control=args.live_control)
        elif args.version == 'live4':
            from vggt_slam.demo.viewer_live4 import serve
            serve(args.run,args.port,source_fps=args.source_fps,live_control=args.live_control)
        elif args.version == 'smooth':
            from vggt_slam.demo.viewer_smooth import serve
            serve(args.run,args.port,source_fps=args.source_fps,live_control=args.live_control,studio_label=args.studio_label)
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
