"""Project real SAM3 masks into a saved VGGT-SLAM snapshot; preserve source runs."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from vggt_slam.demo.object_query import boxes_from_masks, save_query_evidence


class RecordedFrame:
    def __init__(self, points, valid):
        self.points, self.valid = points, valid

    def get_points_in_mask(self, frame_index, mask, graph):
        if mask.shape != self.valid.shape:
            raise ValueError("mask must match recorded RGB/depth grid")
        return self.points[mask & self.valid]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", type=Path, required=True)
    parser.add_argument("--segmentation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    retrieval = json.loads((args.retrieval / "result.json").read_text())
    segmentation = json.loads((args.segmentation / "result.json").read_text())
    run = Path(retrieval["source_run"])
    frame = retrieval["best_frame"]
    rgb = run / frame["asset_paths"]["rgb"]
    if segmentation["status"] != "completed" or Path(segmentation["image"]).resolve() != rgb.resolve():
        parser.error("segmentation must be completed on the PE-selected RGB")
    if segmentation["query"] != retrieval["query"]:
        parser.error("query mismatch")
    metadata = json.loads((run / frame["asset_paths"]["metadata"]).read_text())
    with np.load(run / frame["asset_paths"]["depth"]) as record:
        depth, confidence, intrinsic, valid = [record[key].copy() for key in ("depth", "confidence", "intrinsic", "valid")]
    manifest = json.loads((run / "manifest.json").read_text())
    percentile = manifest.get("config", manifest.get("execution_args", {}))["conf_threshold"]
    confidences = [np.load(path)["confidence"] for path in (run / "submaps" / str(frame["submap_id"]) / "frames").glob("*/depth.npz")]
    threshold = np.percentile(np.stack(confidences), percentile) + 1e-6
    valid &= confidence > threshold
    step = max(int(path.name) for path in (run / "snapshots").iterdir() if path.is_dir())
    node = int(frame["submap_id"]) + metadata["submap_frame_index"]
    with np.load(run / "snapshots" / str(step) / "after.npz") as snapshot:
        projection = snapshot["projection_matrices"][list(snapshot["node_ids"]).index(node)]
    y, x = np.indices(depth.shape)
    pixels = np.stack((x * depth, y * depth, depth, np.ones_like(depth)), axis=-1)
    world = pixels @ np.linalg.inv(projection).T
    with np.errstate(divide="ignore", invalid="ignore"):
        points = world[..., :3] / world[..., 3:]
    valid &= np.isfinite(points).all(axis=2)
    masks = [np.asarray(Image.open(args.segmentation / f"mask_{index:02d}.png")) > 0
             for index in range(segmentation["mask_count"])]
    detections = boxes_from_masks(RecordedFrame(points, valid), 0, None, masks, segmentation["scores"])
    args.output.mkdir(parents=True, exist_ok=False)
    result = save_query_evidence(retrieval["query"], retrieval["scores"][retrieval["best_index"]],
                                 frame["submap_id"], metadata["submap_frame_index"], Image.open(rgb),
                                 detections, run_dir=args.output)
    provenance = {"source_run": str(run), "retrieval": str(args.retrieval.resolve()),
                  "segmentation": str(args.segmentation.resolve()), "snapshot_step": step,
                  "phase": "after", "node_id": node, "confidence_threshold": float(threshold),
                  "valid_boxes": sum(item["valid"] for item in detections),
                  "result": str(result.relative_to(args.output)),
                  "limitations": ["Unverified reconstruction scale", "OBB quality requires visual review"]}
    (args.output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
