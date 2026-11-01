"""Save actual projective node transforms around one optimization."""
import time

import numpy as np


def record_preview(submap, recorder, per_frame=1000):
    """Keep representative camera-local points and node IDs, not a dense copy."""
    point_parts, color_parts, node_parts = [], [], []
    for index, points in enumerate(submap.pointclouds):
        points = np.asarray(points).reshape(-1, 3)
        colors = np.asarray(submap.colors[index]).reshape(-1, 3)
        confidence = np.asarray(submap.get_conf_masks_frame(index)).reshape(-1)
        valid = np.flatnonzero((confidence > submap.get_conf_threshold()) & np.isfinite(points).all(axis=1))
        if not len(valid):
            continue
        selected = valid[np.linspace(0, len(valid) - 1, min(per_frame, len(valid)), dtype=np.int64)]
        point_parts.append(points[selected].astype(np.float32))
        color_parts.append(colors[selected].astype(np.uint8))
        node_parts.append(np.full(len(selected), submap.get_id() + index, dtype=np.int64))
    if not point_parts:
        return
    path = recorder.run_dir / "submaps" / str(submap.get_id()) / "preview.npz"
    if path.exists():
        raise FileExistsError(path)
    np.savez_compressed(path, points=np.concatenate(point_parts), colors=np.concatenate(color_parts),
                        node_ids=np.concatenate(node_parts), coordinate_system="camera_local")
    recorder.event("submap_preview_saved", submap_id=int(submap.get_id()),
                   asset_paths={"preview": str(path.relative_to(recorder.run_dir))},
                   payload={"points": int(sum(len(part) for part in point_parts)),
                            "coordinate_system": "camera_local", "per_frame_limit": per_frame})


def snapshot(graph, graph_map):
    ids, transforms, cameras = [], [], []
    for submap in graph_map.ordered_submaps_by_key():
        for index in range(len(submap.get_all_poses())):
            node = submap.get_id() + index
            H = np.asarray(graph.get_homography(node)).copy()
            camera = submap.proj_mats[index] @ np.linalg.inv(H)
            ids.append(node)
            transforms.append(H)
            cameras.append(camera)
    if len(set(ids)) != len(ids):
        raise ValueError("snapshot contains duplicate graph node IDs")
    return {"node_ids": np.asarray(ids, dtype=np.int64), "homographies": np.stack(transforms),
            "projection_matrices": np.stack(cameras)}


def optimize_recorded(graph, graph_map, recorder, step):
    before = snapshot(graph, graph_map)
    folder = recorder.run_dir / "snapshots" / str(step)
    folder.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(folder / "before.npz", **before)
    initial = float(graph.graph.error(graph.values))
    factor_count = int(graph.graph.size())
    recorder.event("optimization_started", payload={"step": step, "initial_error": initial,
                   "factor_count": factor_count, "node_count": len(before["node_ids"])},
                   asset_paths={"snapshot": str((folder / "before.npz").relative_to(recorder.run_dir))})
    start = time.perf_counter()
    graph.optimize()
    elapsed = time.perf_counter() - start
    final = float(graph.graph.error(graph.values))
    after = snapshot(graph, graph_map)
    if not np.array_equal(before["node_ids"], after["node_ids"]):
        raise ValueError("optimization changed the snapshot node set")
    np.savez_compressed(folder / "after.npz", **after)
    recorder.event("optimization_finished", payload={"step": step, "initial_error": initial,
                   "final_error": final, "elapsed_seconds": elapsed, "factor_count": factor_count,
                   "node_count": len(after["node_ids"])},
                   asset_paths={"snapshot": str((folder / "after.npz").relative_to(recorder.run_dir))})
