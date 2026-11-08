"""Run metadata for incremental video-input demonstrations."""

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from vggt_slam.demo.status import transition, write_json_atomic


def create_video_run(video_path, config, root=Path("logs/demo_runs")):
    video = Path(video_path).expanduser().resolve(strict=True)
    if not video.is_file():
        raise ValueError(f"video input is not a file: {video}")
    run_id = f"video_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{time.time_ns() % 1_000_000_000:09d}"
    run_dir = Path(root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    digest = hashlib.sha256()
    with video.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "source_mode": "video_file_incremental",
        "status": "prepared",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "config": {**config, "video": str(video), "video_sha256": digest.hexdigest(),
                   "video_size_bytes": video.stat().st_size},
        "assets": {},
        "environment": {"platform": platform.platform(), "python": sys.version.split()[0],
                        "device": None, "models": {}},
        "coverage": {f"F{i}": {"status": "NOT_RUN", "evidence": [],
                                  "reason": "not yet demonstrated by this run"}
                     for i in range(1, 8)},
    }
    write_json_atomic(run_dir / "manifest.json", manifest)
    write_json_atomic(run_dir / "status.json", {"schema_version": 1, "run_id": run_id,
                                                 "status": "prepared", "updated_at": manifest["created_at"]})
    return run_dir


def start_video_run(run_dir, device):
    transition(run_dir, "running", device=str(device), models={
        "vggt": {"checkpoint_url": "https://huggingface.co/facebook/VGGT-1B/resolve/main/model.pt"}})


def finish_video_run(run_dir, *, error=None):
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for key, name in (("events", "events.jsonl"), ("poses", "poses.txt"),
                      ("point_cloud", "poses_points.pcd")):
        if (run_dir / name).is_file():
            manifest["assets"][key] = name
    for key, name in (("video_frames", "keyframes/video_frames.jsonl"),
                      ("video_keyframes", "keyframes/video_keyframes.jsonl"),
                      ("video_drops", "keyframes/video_drops.jsonl"),
                      ("video_summary", "video_summary.json")):
        if (run_dir / name).is_file():
            manifest["assets"][key] = name
    write_json_atomic(manifest_path, manifest)
    transition(run_dir, "failed", error=error) if error else transition(run_dir, "completed")
