"""Check the first submap's saved RGB/depth against its exported PCD."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from vggt_slam.demo.image_mapping import crop_mappings
from vggt_slam.pcd_io import read_cloud, unpack_rgb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new JSON evidence file; must not exist")
    args = parser.parse_args()
    run = args.run_dir
    manifest = json.loads((run / "manifest.json").read_text())
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    submaps = [event for event in events if event["event_type"] == "submap_created"]
    if len(submaps) != 1 or submaps[0]["submap_id"] != 0:
        raise ValueError("validator currently supports exactly one submap with ID 0")
    frames = [event for event in events if event["event_type"] == "frame_selected"]
    if len(frames) != submaps[0]["payload"]["frame_count"]:
        raise ValueError("incomplete frame events")
    records = [np.load(run / item["asset_paths"]["depth"]) for item in frames]
    confidence = np.stack([record["confidence"] for record in records])
    threshold = np.percentile(confidence, manifest["execution_args"]["conf_threshold"]) + 1e-6
    first = records[0]
    depth, K = first["depth"], first["intrinsic"]
    height, width = depth.shape
    u, v = np.meshgrid(np.arange(width), np.arange(height))
    local = np.stack(((u - K[0, 2]) * depth / K[0, 0],
                      (v - K[1, 2]) * depth / K[1, 1], depth), axis=-1).astype(np.float32)
    matrices = np.load(run / "poses_camera_matrices.npz")
    projection = matrices["projection_matrices"][0]
    K4 = np.eye(4)
    K4[:3, :3] = K
    homography = np.linalg.inv(projection) @ K4
    mask = first["confidence"] > threshold
    selected = local[mask]
    homogeneous = np.column_stack((selected, np.ones(len(selected)))) @ homography.T
    xyz = homogeneous[:, :3] / homogeneous[:, 3, None]
    finite = np.isfinite(xyz).all(axis=1)
    rgb = np.asarray(Image.open(run / frames[0]["asset_paths"]["rgb"]).convert("RGB"))[mask][finite]
    xyz = xyz[finite].astype(np.float32)
    cloud = read_cloud(run / "poses_points.pcd")
    if len(cloud) < len(xyz):
        raise ValueError("PCD shorter than reconstructed first frame")
    point_error = np.linalg.norm(cloud["xyz"][:len(xyz)] - xyz, axis=1)
    mismatched = int(np.count_nonzero(np.any(unpack_rgb(cloud["rgb"][:len(rgb)]) != rgb, axis=1)))
    metadata = [json.loads((run / item["asset_paths"]["metadata"]).read_text()) for item in frames]
    mapping = crop_mappings([item["source_path"] for item in metadata], depth.shape)[0]
    with Image.open(metadata[0]["source_path"]) as source:
        if source.mode == "RGBA":
            source = Image.alpha_composite(Image.new("RGBA", source.size, (255, 255, 255, 255)), source)
        resized = source.convert("RGB").resize(tuple(mapping["resized_size_wh"]), Image.Resampling.BICUBIC)
    cropped = np.asarray(resized)[mapping["crop_top"]:mapping["crop_top"] + 518]
    expected_rgb = np.full((height, width, 3), 255, dtype=np.uint8)
    top = mapping["batch_pad_top"]
    expected_rgb[top:top + len(cropped)] = cropped
    recorded_rgb = np.asarray(Image.open(run / frames[0]["asset_paths"]["rgb"]).convert("RGB"))
    source_rgb_error = int(np.abs(expected_rgb.astype(np.int16) - recorded_rgb.astype(np.int16)).max())
    result = {"run_id": manifest["run_id"], "frame_id": frames[0]["source_frame_id"],
              "tested_points": len(xyz), "confidence_threshold": float(threshold),
              "max_xyz_error": float(point_error.max()), "rgb_mismatched_points": mismatched,
              "source_preprocess_max_rgb_error_8bit": source_rgb_error,
              "pcd_total_points": len(cloud), "source_to_preprocessed_mapping_reconstructed": mapping,
              "limitations": ["First submap and first frame only", "Source images and current preprocessing implementation must match the original execution", "No ground-truth geometry or metric-depth accuracy verified"],
              "passed": bool(len(xyz) > 0 and point_error.max() < 1e-4 and mismatched == 0 and source_rgb_error <= 1)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
