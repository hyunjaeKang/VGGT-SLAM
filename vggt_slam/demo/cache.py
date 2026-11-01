"""Lightweight read-only access to recorded demo runs."""
import json
from pathlib import Path

import numpy as np

from vggt_slam.pcd_io import read_cloud, unpack_rgb


class CachedRun:
    def __init__(self, run_dir):
        self.path = Path(run_dir)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.events = []
        event_path = self.path / "events.jsonl"
        if event_path.exists():
            self.events = [json.loads(line) for line in event_path.read_text().splitlines()]
        self.frames = [event for event in self.events if event["event_type"] == "frame_selected"]
        self.steps = sorted(int(p.name) for p in (self.path / "snapshots").glob("*")
                            if p.is_dir() and (p / "before.npz").is_file() and (p / "after.npz").is_file())
        self.previews = []
        for event in self.events:
            if event["event_type"] == "submap_preview_saved":
                with np.load(self.path / event["asset_paths"]["preview"]) as data:
                    self.previews.append((int(event["submap_id"]), data["points"].copy(),
                                          data["colors"].copy(), data["node_ids"].copy()))
        asset = self.manifest.get("assets", {}).get("point_cloud")
        self.cloud = None
        if asset:
            path = Path(asset["path"]) if isinstance(asset, dict) else self.path / asset
            if path.is_file():
                self.cloud = read_cloud(path)
        self.poses = None
        asset = self.manifest.get("assets", {}).get("poses")
        if asset:
            path = Path(asset["path"]) if isinstance(asset, dict) else self.path / asset
            if path.is_file():
                self.poses = np.loadtxt(path, ndmin=2)

    def frame(self, index):
        if not self.frames:
            return None
        return self.frames[max(0, min(index, len(self.frames) - 1))]

    def render(self, step=None, phase="after", frame_index=None, budget=300_000, color_mode="RGB"):
        if not 1 <= budget <= 2_000_000:
            raise ValueError("point budget must be between 1 and 2000000")
        if phase not in ("before", "after"):
            raise ValueError("phase must be before or after")
        if self.previews and self.steps:
            step = self.steps[-1] if step is None else int(step)
            if step not in self.steps:
                raise ValueError("snapshot step not available")
            with np.load(self.path / "snapshots" / str(step) / f"{phase}.npz") as data:
                matrices = {int(key): matrix.copy() for key, matrix in zip(data["node_ids"], data["homographies"])}
                cameras = {int(key): matrix.copy() for key, matrix in zip(data["node_ids"], data["projection_matrices"])}
            selected = self.frames if frame_index is None else self.frames[:frame_index + 1]
            visible_nodes = set()
            for event in selected:
                metadata = json.loads((self.path / event["asset_paths"]["metadata"]).read_text())
                visible_nodes.add(int(event["submap_id"]) + int(metadata["submap_frame_index"]))
            points, colors, trajectory = [], [], []
            for submap_id, local, rgb, node_ids in self.previews:
                for node in np.unique(node_ids):
                    node = int(node)
                    if node not in matrices or node not in visible_nodes:
                        continue
                    H = matrices[node]
                    subset = node_ids == node
                    local_points = local[subset]
                    numerator = local_points @ H[:3, :3].T + H[:3, 3]
                    denominator = local_points @ H[3, :3] + H[3, 3]
                    with np.errstate(divide="ignore", invalid="ignore"):
                        transformed = numerator / denominator[:, None]
                    valid = np.isfinite(transformed).all(axis=1)
                    points.append(transformed[valid].astype(np.float32))
                    if color_mode == "Submaps":
                        color = np.array([(53 * submap_id + 90) % 256, (97 * submap_id + 150) % 256,
                                          (149 * submap_id + 200) % 256], dtype=np.uint8)
                        colors.append(np.broadcast_to(color, (valid.sum(), 3)).copy())
                    else:
                        colors.append(rgb[subset][valid])
                    origin = H[:3, 3] / H[3, 3] if H[3, 3] != 0 else np.full(3, np.nan)
                    if np.isfinite(origin).all():
                        trajectory.append((node, origin))
            pts = np.concatenate(points) if points else np.empty((0, 3), np.float32)
            cols = np.concatenate(colors) if colors else np.empty((0, 3), np.uint8)
            if len(pts) > budget:
                sample = np.linspace(0, len(pts) - 1, budget, dtype=np.int64)
                pts, cols = pts[sample], cols[sample]
            return {"points": pts, "colors": cols, "trajectory": np.array([x[1] for x in trajectory]).reshape(-1, 3),
                    "nodes": [x[0] for x in trajectory], "cameras": cameras,
                    "source": "recorded submap preview", "step": step}
        if self.cloud is None:
            return {"points": np.empty((0, 3)), "colors": np.empty((0, 3), np.uint8),
                    "trajectory": np.empty((0, 3)), "nodes": [], "cameras": {}, "source": "no point cloud", "step": None}
        idx = np.linspace(0, len(self.cloud) - 1, min(len(self.cloud), budget), dtype=np.int64)
        pts = np.asarray(self.cloud["xyz"][idx], dtype=np.float32)
        valid = np.isfinite(pts).all(axis=1)
        trajectory = self.poses[:, 1:4] if self.poses is not None else np.empty((0, 3))
        return {"points": pts[valid], "colors": unpack_rgb(self.cloud["rgb"][idx])[valid],
                "trajectory": trajectory, "nodes": [], "cameras": {}, "source": "saved PCD", "step": None}
