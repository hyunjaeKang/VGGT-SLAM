"""Shared mask-to-3D object query result handling."""

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from vggt_slam.slam_utils import compute_obb_from_points


def boxes_from_masks(submap, frame_index, graph, masks, scores=None, minimum_points=8):
    """Map segmentation masks to confidence-filtered world points and OBBs."""
    scores = [None] * len(masks) if scores is None else np.asarray(scores).reshape(-1)
    detections = []
    for index, raw_mask in enumerate(masks):
        mask = np.asarray(raw_mask, dtype=bool).squeeze()
        if mask.ndim != 2:
            detections.append({"index": index, "valid": False, "reason": "mask must be 2D"})
            continue
        pixels = np.argwhere(mask)
        if not len(pixels):
            detections.append({"index": index, "valid": False, "reason": "empty mask", "mask": mask})
            continue
        points = np.asarray(submap.get_points_in_mask(frame_index, mask, graph), dtype=np.float64)
        points = points[np.isfinite(points).all(axis=1)]
        if len(points) < minimum_points:
            detections.append({"index": index, "valid": False,
                               "reason": f"only {len(points)} valid 3D points (need {minimum_points})",
                               "point_count": int(len(points)), "mask_pixels": int(mask.sum()), "mask": mask})
            continue
        singular_values = np.linalg.svd(points - points.mean(axis=0), compute_uv=False)
        tolerance = max(points.shape) * np.finfo(np.float64).eps * singular_values[0]
        rank = int(np.count_nonzero(singular_values > tolerance))
        if rank < 3:
            detections.append({"index": index, "valid": False, "reason": f"degenerate 3D support (rank {rank})",
                               "point_count": int(len(points)), "mask_pixels": int(mask.sum()),
                               "geometry_rank": rank, "mask": mask})
            continue
        center, extent, rotation = compute_obb_from_points(points)
        detections.append({"index": index, "valid": True, "point_count": int(len(points)),
                           "mask_pixels": int(mask.sum()), "geometry_rank": rank,
                           "score": float(scores[index]) if index < len(scores) and scores[index] is not None else None,
                           "center": center.tolist(), "extent": extent.tolist(),
                           "rotation": rotation.tolist(), "mask": mask})
    return detections


def save_query_evidence(query, retrieval_score, submap_id, frame_index, frame_image, detections, *,
                        run_dir=None, recorder=None):
    """Save query RGB, masks, 3D boxes, and an optional run event."""
    root = Path(run_dir) if run_dir is not None else Path("logs/object_queries")
    query_id = f"query_{time.time_ns()}"
    folder = root / "object_queries" / query_id if recorder is not None else root / query_id
    folder.mkdir(parents=True, exist_ok=False)
    if isinstance(frame_image, Image.Image):
        image = frame_image.convert("RGB")
    else:
        image = Image.fromarray(np.asarray(frame_image).astype(np.uint8)).convert("RGB")
    image.save(folder / "frame.png")
    saved = []
    for detection in detections:
        item = {key: value for key, value in detection.items() if key != "mask"}
        if "mask" in detection:
            mask_path = f"mask_{detection['index']:02d}.png"
            Image.fromarray(np.asarray(detection["mask"], dtype=np.uint8) * 255).save(folder / mask_path)
            item["mask_path"] = mask_path
        saved.append(item)
    result = {"schema_version": 1, "query_id": query_id, "query": str(query),
              "retrieval_score": float(retrieval_score), "submap_id": int(submap_id),
              "frame_index": int(frame_index), "frame_image": "frame.png", "detections": saved,
              "limitations": ["3D coordinates inherit the reconstruction scale and alignment",
                              "Mask and box quality require visual review"]}
    if recorder is not None:
        steps = [int(path.name) for path in (root / "snapshots").glob("*")
                 if path.name.isdigit() and (path / "after.npz").is_file()]
        if steps:
            result["snapshot"] = {"step": max(steps), "phase": "after"}
    result_path = folder / "result.json"
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if recorder is not None:
        recorder.event("object_query_result", submap_id=int(submap_id),
                       asset_paths={"result": str(result_path.relative_to(recorder.run_dir))},
                       payload={"query_id": query_id, "query": str(query),
                                "retrieval_score": float(retrieval_score),
                                "detection_count": sum(bool(item["valid"]) for item in saved)})
    return result_path
