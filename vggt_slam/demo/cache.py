"""Lightweight read-only access to recorded demo runs."""
import json
from pathlib import Path

import numpy as np

from vggt_slam.pcd_io import read_cloud, unpack_rgb


class CachedRun:
    def __init__(self, run_dir, use_dense=True):
        self.path = Path(run_dir)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.events = []
        event_path = self.path / "events.jsonl"
        if event_path.exists():
            self.events = [json.loads(line) for line in event_path.read_text().splitlines()]
        self.frames = [event for event in self.events if event["event_type"] == "frame_selected"]
        self.object_queries = []
        last_completed_step = None
        for event in self.events:
            if event["event_type"] == "optimization_finished":
                last_completed_step = event.get("payload", {}).get("step")
            if event["event_type"] != "object_query_result":
                continue
            result_path = event.get("asset_paths", {}).get("result")
            if not result_path:
                continue
            try:
                result = json.loads((self.path / result_path).read_text())
                if "snapshot" not in result and last_completed_step is not None:
                    result["snapshot"] = {"step": last_completed_step, "phase": "after",
                                          "provenance": "preceding optimization_finished event"}
                result["_asset_path"] = result_path
                self.object_queries.append(result)
            except (OSError, json.JSONDecodeError):
                continue
        self.steps = sorted(int(p.name) for p in (self.path / "snapshots").glob("*")
                            if p.is_dir() and (p / "before.npz").is_file() and (p / "after.npz").is_file())
        self.evaluations = []
        metric_paths = set(self.path.glob("evaluation*/trajectory_metrics.json"))
        metric_paths.update(self.path.glob("*/trajectory_metrics.json"))
        for metric_path in sorted(metric_paths):
            try:
                self.evaluations.append(json.loads(metric_path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
        self.previews = []
        self.preview_groups = []
        self.sky_groups = {}
        self.sky_index = None
        self.sky_dir = None
        for path in sorted((self.path / 'evidence').glob('sky_*/index.json'), reverse=True):
            index = json.loads(path.read_text())
            if index.get('status') == 'completed' and Path(index['source_run']).resolve() == self.path.resolve():
                self.sky_index, self.sky_dir = index, path.parent
                break
        self.dense_index = None
        self.dense_dir = None
        from vggt_slam.demo.dense_display import source_digest
        for path in (sorted((self.path / 'evidence').glob('dense_*/index.json'), reverse=True) if use_dense else []):
            index = json.loads(path.read_text())
            if (index.get('status') == 'completed' and index.get('complete_run')
                    and index.get('source_run') == str(self.path.resolve())
                    and index.get('events_sha256') == source_digest(self.path)
                    and index.get('frame_count') == len(self.frames)
                    and (self.sky_index is None or index.get('sky_index') == str((self.sky_dir/'index.json').resolve()))):
                self.dense_index, self.dense_dir = index, path.parent
                break
        for event in self.events:
            if event["event_type"] == "submap_preview_saved":
                dense_path = (self.dense_dir / self.dense_index['submaps'][str(event['submap_id'])]
                              if self.dense_index else None)
                with np.load(dense_path or self.path / event["asset_paths"]["preview"]) as data:
                    self.previews.append((int(event["submap_id"]), data["points"].copy(),
                                          data["colors"].copy(), data["node_ids"].copy()))
                submap_id, local, rgb, nodes = self.previews[-1]
                sky_scores = None
                if self.sky_dir is not None:
                    with np.load(dense_path or self.sky_dir / f'submap_{submap_id}.npz') as data:
                        sky_scores = data['sky_scores' if dense_path else 'scores'].copy()
                    if len(sky_scores) != len(local):
                        raise ValueError('sky overlay does not match preview points')
                boundaries = [0, *list(np.flatnonzero(nodes[1:] != nodes[:-1]) + 1), len(nodes)]
                for start, end in zip(boundaries[:-1], boundaries[1:]):
                    if end > start:
                        self.preview_groups.append((submap_id, int(nodes[start]), local[start:end], rgb[start:end]))
                        if sky_scores is not None:
                            self.sky_groups[(submap_id, int(nodes[start]))] = sky_scores[start:end]
        self.refresh_queries()
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

    def refresh_queries(self):
        """Discover separately saved searches without modifying recorded events."""
        deleted_path = self.path / 'evidence' / 'deleted_queries.json'
        deleted = set(json.loads(deleted_path.read_text())) if deleted_path.is_file() else set()
        self.object_queries = [q for q in self.object_queries if q['query_id'] not in deleted]
        known = {item['query_id'] for item in self.object_queries} | deleted
        for status_path in sorted((self.path / 'evidence' / 'query_jobs').glob('*/status.json')):
            status = json.loads(status_path.read_text())
            if status.get('state') != 'completed':
                continue
            path = self.path / status['result']
            result = json.loads(path.read_text())
            if result['query_id'] not in known:
                result['_asset_path'] = str(path.relative_to(self.path))
                self.object_queries.append(result)
                known.add(result['query_id'])

    def delete_query(self, query_id):
        """Persist a list deletion while retaining source events and query evidence."""
        if not any(q['query_id'] == query_id for q in self.object_queries):
            raise ValueError('Unknown saved query')
        path = self.path / 'evidence' / 'deleted_queries.json'
        deleted = set(json.loads(path.read_text())) if path.is_file() else set()
        deleted.add(query_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(sorted(deleted)) + '\n')
        temporary.replace(path)
        self.refresh_queries()

    def frame(self, index):
        if not self.frames:
            return None
        return self.frames[max(0, min(index, len(self.frames) - 1))]

    def camera_preview(self, frame_index, step, phase='after', hide_sky=False, sky_threshold=32, budget=50000):
        """Keep the current frame legible without increasing the global map budget."""
        event = self.frame(frame_index)
        empty = (np.empty((0, 3), np.float32), np.empty((0, 3), np.uint8))
        if event is None or step not in self.steps:
            return empty
        meta = json.loads((self.path / event['asset_paths']['metadata']).read_text())
        node = int(event['submap_id']) + meta['submap_frame_index']
        with np.load(self.path / 'snapshots' / str(step) / f'{phase}.npz') as data:
            ids = list(data['node_ids'])
            if node not in ids:
                return empty
            matrix = data['homographies'][ids.index(node)]
        for sid, n, local, colors in self.preview_groups:
            if sid != event['submap_id'] or n != node:
                continue
            scores = self.sky_groups.get((sid, n)) if hide_sky else None
            indices = np.flatnonzero(scores < sky_threshold) if scores is not None else np.arange(len(local))
            if len(indices) > budget:
                indices = indices[np.linspace(0, len(indices)-1, budget, dtype=int)]
            xyz = local[indices]
            denominator = xyz @ matrix[3, :3] + matrix[3, 3]
            with np.errstate(divide='ignore', invalid='ignore'):
                world = (xyz @ matrix[:3, :3].T + matrix[:3, 3]) / denominator[:, None]
            finite = np.isfinite(world).all(axis=1)
            return world[finite].astype(np.float32), colors[indices][finite]
        return empty

    def render(self, step=None, phase="after", frame_index=None, budget=300_000, color_mode="RGB", hide_sky=False, sky_threshold=32):
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
            def kept_indices(sid, node, local):
                scores = self.sky_groups.get((sid, node)) if hide_sky else None
                return np.flatnonzero(scores < sky_threshold) if scores is not None else None

            total_visible = sum(int(np.count_nonzero(self.sky_groups[(sid, node)] < sky_threshold))
                                if hide_sky and (sid, node) in self.sky_groups else len(local)
                                for sid, node, local, _ in self.preview_groups
                                if node in matrices and node in visible_nodes)
            camera_positions = {}
            for submap_id, node, local, rgb in self.preview_groups:
                node = int(node)
                if node not in matrices or node not in visible_nodes:
                    continue
                H = matrices[node]
                local_points = local
                local_colors = rgb
                kept = kept_indices(submap_id, node, local)
                count = len(kept) if kept is not None else len(local)
                per_node_budget = max(1, int(np.ceil(budget * count / max(1, total_visible))))
                if kept is not None or count > per_node_budget:
                    sample = np.linspace(0, count - 1, min(count, per_node_budget), dtype=np.int64)
                    if kept is not None:
                        sample = kept[sample]
                    local_points, local_colors = local_points[sample], local_colors[sample]
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
                    colors.append(local_colors[valid])
                origin = H[:3, 3] / H[3, 3] if H[3, 3] != 0 else np.full(3, np.nan)
                if np.isfinite(origin).all() and node not in camera_positions:
                    trajectory.append((node, origin))
                    camera_positions[node] = origin
            edge_segments, edge_colors = [], []
            edge_types = {"overlap_edge_added", "loop_auxiliary_edge_added", "loop_constraint_added"}
            for event in self.events:
                if event["event_type"] not in edge_types:
                    continue
                payload = event.get("payload", {})
                source, target = payload.get("from_node"), payload.get("to_node")
                if source in camera_positions and target in camera_positions:
                    edge_segments.append([camera_positions[source], camera_positions[target]])
                    edge_colors.append((230, 70, 70) if event["event_type"] == "loop_constraint_added"
                                       else (80, 180, 230))
            pts = np.concatenate(points) if points else np.empty((0, 3), np.float32)
            cols = np.concatenate(colors) if colors else np.empty((0, 3), np.uint8)
            if len(pts) > budget:
                sample = np.linspace(0, len(pts) - 1, budget, dtype=np.int64)
                pts, cols = pts[sample], cols[sample]
            return {"points": pts, "colors": cols, "trajectory": np.array([x[1] for x in trajectory]).reshape(-1, 3),
                    "nodes": [x[0] for x in trajectory], "cameras": cameras,
                    "edges": np.asarray(edge_segments, dtype=np.float32).reshape(-1, 2, 3),
                    "edge_colors": np.asarray(edge_colors, dtype=np.uint8).reshape(-1, 3),
                    "source": "dense depth display cache" if self.dense_index else "recorded submap preview", "step": step}
        if self.cloud is None:
            return {"points": np.empty((0, 3)), "colors": np.empty((0, 3), np.uint8),
                    "trajectory": np.empty((0, 3)), "nodes": [], "cameras": {},
                    "edges": np.empty((0, 2, 3), np.float32), "edge_colors": np.empty((0, 3), np.uint8),
                    "source": "no point cloud", "step": None}
        idx = np.linspace(0, len(self.cloud) - 1, min(len(self.cloud), budget), dtype=np.int64)
        pts = np.asarray(self.cloud["xyz"][idx], dtype=np.float32)
        valid = np.isfinite(pts).all(axis=1)
        trajectory = self.poses[:, 1:4] if self.poses is not None else np.empty((0, 3))
        return {"points": pts[valid], "colors": unpack_rgb(self.cloud["rgb"][idx])[valid],
                "trajectory": trajectory, "nodes": [], "cameras": {},
                "edges": np.empty((0, 2, 3), np.float32), "edge_colors": np.empty((0, 3), np.uint8),
                "source": "saved PCD", "step": None}
