"""Run live open-set SLAM with modern torch and read-only base SLAM dependencies."""

import argparse
import importlib
import json
from pathlib import Path
import site
import sys

# Load the isolated environment's tensor stack before exposing legacy SLAM packages.
import numpy
import torch
import torchvision


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--slam-env", type=Path, default=Path(__file__).resolve().parents[1] / ".venv")
    args, remaining = parser.parse_known_args()
    version = tuple(int(value) for value in torch.__version__.split("+")[0].split(".")[:2])
    if version < (2, 7):
        parser.error("run with .venv-open-set; SAM3 needs the modern torch stack")
    packages = args.slam_env / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    if not packages.is_dir():
        parser.error("base SLAM environment must use the same Python major/minor")
    site.addsitedir(str(packages.resolve()))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main_realtime as entry
    from vggt_slam.demo import video_run

    original = video_run.create_video_run
    provenance = {"torch": torch.__version__, "torchvision": torchvision.__version__,
                  "numpy": numpy.__version__, "base_slam_site_packages": str(packages.resolve()),
                  "dependency_paths": {name: str(getattr(importlib.import_module(name), "__file__", None))
                                       for name in ("torch", "torchvision", "numpy", "gtsam", "cv2", "viser", "sam3", "core")},
                  "limitations": ["Read-only reuse of local base dependencies; not a standalone distributable environment"]}

    def create(video, config, *a, **kw):
        path = original(video, config, *a, **kw)
        (path / "open_set_runtime.json").write_text(json.dumps(provenance, indent=2) + "\n")
        return path

    video_run.create_video_run = create
    if "--device" not in remaining:
        remaining += ["--device", "cpu"]
    sys.argv = ["main_realtime.py", *remaining]
    entry.main()


if __name__ == "__main__":
    main()
