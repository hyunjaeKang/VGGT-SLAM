"""Audit real saved masks/OBBs against recorded depth, without modifying the run."""

import argparse
import json
import itertools
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from vggt_slam.demo.cache import CachedRun
from vggt_slam.demo.object_query import boxes_from_masks


def draw_envelope(axis, low, high, color, label):
    bits = list(itertools.product((0, 1), repeat=3))
    corners = np.array([np.where(bit, high, low) for bit in bits])
    first = True
    for i, a in enumerate(bits):
        for j, b in enumerate(bits[i+1:], start=i+1):
            if sum(x != y for x, y in zip(a, b)) == 1:
                axis.plot(*corners[[i, j]].T, color=color, linewidth=1,
                          label=label if first else None)
                first = False


class MaskPoints:
    def __init__(self, points, valid):
        self.points, self.valid = points, valid

    def get_points_in_mask(self, frame_index, mask, graph):
        return self.points[mask & self.valid]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    run = CachedRun(args.run)
    report = {"source_run": str(args.run.resolve()), "queries": [], "limitations": [
        "Support containment checks consistency, not independent object accuracy",
        "No object labels, metric dimensions or 3D ground truth", "Coordinates retain unverified reconstruction scale",
        "Volume expansion flags use a review heuristic, not a calibrated acceptance threshold"]}
    for query in run.object_queries:
        if query.get('search', {}).get('schema_version', 0) >= 3:
            report.setdefault('skipped', []).append({'query_id': query['query_id'],
                'reason': 'native multi-frame schema; use per-observation masks and search consistency audit'})
            continue
        if query["query"] not in {"car", "tree"}:
            continue
        name = query["query"]
        original_folder = run.path / Path(query["_asset_path"]).parent
        replay_folder = args.replay / name
        replay = json.loads((replay_folder / "result.json").read_text())
        image = np.asarray(Image.open(original_folder / "frame.png").convert("RGB"))
        replay_image = np.asarray(Image.open(replay_folder / "frame.png").convert("RGB"))
        if not np.array_equal(image, replay_image):
            raise ValueError("SAM3 replay image differs from saved query RGB")
        submap = run.path / "submaps" / str(query["submap_id"])
        with np.load(submap / "frames" / str(query["frame_index"]) / "depth.npz") as depth:
            z, confidence, valid = [depth[key].copy() for key in ("depth", "confidence", "valid")]
        all_conf = []
        for path in (submap / "frames").glob("*/depth.npz"):
            with np.load(path) as data:
                all_conf.append(data["confidence"].copy())
        threshold = np.percentile(np.stack(all_conf), run.manifest["config"]["conf_threshold"]) + 1e-6
        snapshot = query["snapshot"]
        with np.load(run.path / "snapshots" / str(snapshot["step"]) / (snapshot["phase"] + ".npz")) as data:
            node = query["submap_id"] + query["frame_index"]
            projection = data["projection_matrices"][list(data["node_ids"]).index(node)]
        y, x = np.indices(z.shape)
        projected = np.stack((x*z, y*z, z, np.ones_like(z)), axis=-1) @ np.linalg.inv(projection).T
        with np.errstate(divide="ignore", invalid="ignore"):
            points = projected[..., :3] / projected[..., 3:]
        valid &= (confidence > threshold) & np.isfinite(points).all(axis=2)
        masks = [np.asarray(Image.open(replay_folder / f"mask_{index:02d}.png")) > 0
                 for index in range(replay["mask_count"])]
        adapter = MaskPoints(points, valid)
        detections = boxes_from_masks(adapter, 0, None, masks, replay["scores"])
        summary = {"query": name, "snapshot": snapshot, "original_valid_boxes": sum(d["valid"] for d in query["detections"]),
                   "replayed_masks": len(masks), "new_valid_boxes": sum(d["valid"] for d in detections), "detections": []}
        rows = (len(masks) + 3) // 4
        figure, axes = plt.subplots(rows, 4, figsize=(16, 3*rows), squeeze=False, constrained_layout=True)
        for axis in axes.flat:
            axis.axis("off")
        for index, detection in enumerate(detections):
            mask = masks[index]
            support = adapter.get_points_in_mask(0, mask, None)
            item = {key: value for key, value in detection.items() if key != "mask"}
            original = next((d for d in query["detections"] if d["index"] == index), None)
            if original and original.get("mask_path"):
                old_mask = np.asarray(Image.open(original_folder / original["mask_path"])) > 0
                item["replay_mask_identical"] = bool(np.array_equal(old_mask, mask))
                item["replay_mask_iou"] = float((old_mask & mask).sum() / max(1, (old_mask | mask).sum()))
            if original and original["valid"] and len(support):
                extent = np.asarray(original["extent"])
                local = (support - original["center"]) @ np.asarray(original["rotation"])
                tolerance = max(float(extent.max()) * 1e-5, 1e-6)
                excess = np.abs(local) - extent/2
                item["inside_original_box_fraction"] = float(np.all(excess <= tolerance, axis=1).mean())
                item["max_outside_original_box"] = float(max(0, excess.max()))
                robust_extent = np.diff(np.quantile(local, [.02, .98], axis=0), axis=0)[0]
                volume = float(np.prod(robust_extent))
                item["box_to_robust_volume_ratio"] = float(np.prod(extent)/volume) if volume > 0 else None
                item["review_extreme_point_expansion"] = bool(volume > 0 and np.prod(extent)/volume > 10)
                if item["review_extreme_point_expansion"]:
                    diagnostic = plt.figure(figsize=(12, 4), layout="constrained")
                    rgb_axis = diagnostic.add_subplot(121)
                    rgb_axis.imshow(image)
                    rgb_axis.imshow(np.ma.masked_where(~mask, mask), cmap="autumn", alpha=.5, vmin=0, vmax=1)
                    rgb_axis.axis("off")
                    spatial = diagnostic.add_subplot(122, projection="3d")
                    spatial.scatter(*local.T, s=.3, alpha=.4, color="black")
                    draw_envelope(spatial, -extent/2, extent/2, "red", "Saved OBB")
                    low, high = np.quantile(local, [.02, .98], axis=0)
                    draw_envelope(spatial, low, high, "blue", "2–98% support envelope")
                    spatial.set(xlabel="OBB local X", ylabel="OBB local Y", zlabel="OBB local Z")
                    spatial.legend(fontsize=7)
                    diagnostic.suptitle(f"{name} #{index}: extreme-point sensitivity review; units unverified")
                    diagnostic.savefig(args.output / f"{name}_{index:02d}_expansion.png", dpi=140)
                    plt.close(diagnostic)
            summary["detections"].append(item)
            axis = axes.flat[index]
            axis.imshow(image)
            axis.imshow(np.ma.masked_where(~mask, mask), cmap="autumn", alpha=.5, vmin=0, vmax=1)
            if np.any(mask & valid):
                axis.contour(mask & valid, levels=[.5], colors=["cyan"], linewidths=.4)
            status = "BOX" if detection["valid"] else detection["reason"]
            axis.set_title(f"#{index}: {status}\n{len(support)} supported pixels", fontsize=9)
            Image.fromarray(mask.astype(np.uint8)*255).save(args.output / f"{name}_mask_{index:02d}.png")
        figure.suptitle(f"{name}: orange = actual SAM3 mask; cyan = usable depth support; reconstruction scale unverified")
        figure.savefig(args.output / f"{name}_mask_review.png", dpi=130)
        plt.close(figure)
        report["queries"].append(summary)
    (args.output / "quality_audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({q["query"]: {key: q[key] for key in ("original_valid_boxes", "replayed_masks", "new_valid_boxes")}
                      for q in report["queries"]}, indent=2))


if __name__ == "__main__":
    main()
