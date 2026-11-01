"""Prepare an image selection without loading inference models."""
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


def _package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _manifest(config, mode, assets):
    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    return {
        "schema_version": 1, "run_id": config["run_id"], "source_mode": mode,
        "status": "prepared", "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
        "config": config, "assets": assets,
        "environment": {"platform": platform.platform(), "python": platform.python_version(),
                        "packages": {name: _package_version(name) for name in ("torch", "viser", "opencv-python")},
                        "device": None, "models": {}},
        "coverage": {f"F{i}": {"status": "NOT_RUN", "evidence": [], "reason": "not yet demonstrated by this run"} for i in range(1, 8)},
    }


def prepare(config, root=Path("logs/demo_runs")):
    run_id = config["run_id"]
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("run_id must contain only letters, digits, underscore or hyphen")
    target = Path(root) / run_id
    target.mkdir(parents=True, exist_ok=False)
    try:
        return _prepare_reserved(config, root)
    except Exception as exc:
        from vggt_slam.demo.status import write_json_atomic

        write_json_atomic(target / "status.json", {
            "schema_version": 1, "run_id": run_id, "status": "failed",
            "phase": "prepare", "error_type": type(exc).__name__, "message": str(exc),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        raise


def _prepare_reserved(config, root):
    run_id = config["run_id"]
    mode = config.get("source_mode", "offline_compute")
    if mode == "cached_playback":
        return _register_cached(config, root)
    if mode != "offline_compute":
        raise ValueError(f"unsupported source_mode for prepare: {mode}")
    start, end = config.get("start"), config.get("end")
    if any(value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0) for value in (start, end)):
        raise ValueError("start and end must be nonnegative integer frame IDs")
    if start is not None and end is not None and start > end:
        raise ValueError("start must not exceed end")
    source = Path(config["image_dir"]).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError("image_dir must be a directory")
    requested_ids = None
    if "frame_ids_file" in config:
        requested_ids = json.loads(Path(config["frame_ids_file"]).expanduser().read_text())
        if (not isinstance(requested_ids, list) or not requested_ids
                or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in requested_ids)
                or any(a >= b for a, b in zip(requested_ids, requested_ids[1:]))):
            raise ValueError("frame_ids_file must contain strictly increasing nonnegative frame IDs")
        requested_ids = set(requested_ids)
    timestamps = None
    if "timestamp_file" in config:
        if config.get("timestamp_type") not in ("unix_seconds", "relative_seconds"):
            raise ValueError("timestamp_type must be unix_seconds or relative_seconds")
        timestamps = json.loads(Path(config["timestamp_file"]).expanduser().read_text())
        if not isinstance(timestamps, list) or any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) for t in timestamps):
            raise ValueError("timestamp_file must contain a JSON array of finite seconds indexed by frame ID")
        if any(a >= b for a, b in zip(timestamps, timestamps[1:])):
            raise ValueError("timestamps must be strictly increasing")
    frames = []
    seen = set()
    for path in source.iterdir():
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"} or "depth" in path.stem.lower():
            continue
        match = re.search(r"(\d+)$", path.stem)
        if not match:
            raise ValueError(f"image name has no numeric frame ID: {path.name}")
        frame_id = int(match.group(1))
        if frame_id in seen:
            raise ValueError(f"duplicate frame ID: {frame_id}")
        seen.add(frame_id)
        if frame_id < config.get("start", frame_id) or frame_id > config.get("end", frame_id):
            continue
        if requested_ids is not None and frame_id not in requested_ids:
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            raise ValueError(f"invalid image: {path}") from exc
        if timestamps is not None and frame_id >= len(timestamps):
            raise ValueError(f"timestamp missing for frame ID: {frame_id}")
        frames.append({"frame_id": frame_id, "source": str(path),
                       "timestamp": timestamps[frame_id] if timestamps is not None else None,
                       "timestamp_type": config["timestamp_type"] if timestamps is not None else "unavailable"})
    frames.sort(key=lambda item: item["frame_id"])
    if not frames:
        raise ValueError("no images selected")
    if requested_ids is not None and {frame["frame_id"] for frame in frames} != requested_ids:
        raise ValueError("requested frame IDs are missing or outside the configured range")
    ids = [f["frame_id"] for f in frames]
    missing = [i for i in range(ids[0], ids[-1] + 1) if i not in seen]
    selection = {"frames": frames, "missing_ids": missing,
                 "selection_policy": "explicit_frame_ids" if requested_ids is not None else "inclusive_range"}
    digest = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
    manifest = _manifest(config, mode, {"selection": "selection.json"})
    manifest["selection_sha256"] = digest
    manifest["selection_checksum_scope"] = "canonical JSON selection list and missing IDs; not image contents"
    return _write_run(root, run_id, config, manifest, selection)


def _register_cached(config, root):
    """Register existing files by reference; never copy or modify them."""
    assets = config["existing_assets"]
    if not isinstance(assets, dict) or not {"point_cloud", "poses"} <= assets.keys():
        raise ValueError("cached_playback requires existing_assets.point_cloud and poses")
    references = {}
    for name, value in assets.items():
        path = Path(value).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"asset is not a file: {path}")
        references[name] = {"path": str(path), "size_bytes": path.stat().st_size, "external_read_only": True}
    manifest = _manifest(config, "cached_playback", references)
    manifest["limitations"] = ["Existing PCD and poses do not contain depth, semantic embeddings, pixel mappings or optimization history.",
                               "Pose first column must be interpreted using pose_first_column in config."]
    if config.get("pose_first_column") not in ("frame_id", "timestamp_seconds"):
        raise ValueError("cached_playback requires pose_first_column: frame_id or timestamp_seconds")
    return _write_run(root, config["run_id"], config, manifest)


def _write_run(root, run_id, config, manifest, selection=None):
    from vggt_slam.demo.status import write_json_atomic

    target = Path(root) / run_id
    files = [("config.json", config)]
    if selection is not None:
        files.append(("selection.json", selection))
    files.append(("manifest.json", manifest))
    files.append(("status.json", {"schema_version": 1, "run_id": run_id, "status": "prepared",
                                   "updated_at": manifest["created_at"]}))
    for name, data in files:
        write_json_atomic(target / name, data)
    return target
