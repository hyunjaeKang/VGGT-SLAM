"""Validate video frame identities and export TUM with timestamp provenance."""

import argparse
import json
from pathlib import Path
import re

import numpy as np


def validate(run):
    def lines(path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    summary = json.loads((run / "video_summary.json").read_text())
    decoded = lines(run / "keyframes/video_frames.jsonl")
    selected = lines(run / "keyframes/video_keyframes.jsonl")
    dropped = lines(run / "keyframes/video_drops.jsonl")
    events = lines(run / "events.jsonl")
    processed = {}
    for event in events:
        if event["event_type"] != "frame_selected":
            continue
        meta = json.loads((run / event["asset_paths"]["metadata"]).read_text())
        source_id = int(event["source_frame_id"])
        keyframe_id = int(re.search(r"(\d+)$", Path(meta["source_path"]).stem).group(1))
        record = (source_id, meta["source_timestamp"], meta.get("source_timestamp_type", "video_pts_seconds"))
        if keyframe_id in processed and processed[keyframe_id] != record:
            raise ValueError("overlap metadata disagrees")
        processed[keyframe_id] = record
    selected_ids = {int(item["source_frame_id"]) for item in selected}
    dropped_ids = {int(item["source_frame_id"]) for item in dropped}
    processed_ids = {record[0] for record in processed.values()}
    if processed_ids & dropped_ids or selected_ids != processed_ids | dropped_ids:
        raise ValueError("selected frames must partition into processed and dropped frames")
    if len(decoded) != summary["decoded_frames"] or len(dropped) != summary["keyframe_backlog_dropped"]:
        raise ValueError("summary count disagrees with sidecars")
    poses = np.loadtxt(run / "poses.txt", ndmin=2)
    if poses.shape[1] != 8 or not np.isfinite(poses).all():
        raise ValueError("poses must contain eight finite columns")
    pose_ids = poses[:, 0].astype(int)
    if not np.array_equal(poses[:, 0], pose_ids) or len(set(pose_ids)) != len(pose_ids):
        raise ValueError("invalid or duplicate exported pose frame IDs")
    if set(pose_ids) != set(processed):
        raise ValueError("pose IDs do not match processed keyframe filenames")
    norms = np.linalg.norm(poses[:, 4:8], axis=1)
    if not np.allclose(norms, 1, atol=1e-4):
        raise ValueError("pose quaternions must be normalized")
    timestamps = [processed[index][1] for index in pose_ids]
    if any(value is None or not np.isfinite(value) for value in timestamps) or np.any(np.diff(timestamps) <= 0):
        raise ValueError("TUM export requires strictly increasing valid PTS timestamps")
    tum = poses.copy()
    tum[:, 0] = timestamps
    timestamp_types = sorted({record[2] for record in processed.values()})
    approximate = any(kind != "video_pts_seconds" for kind in timestamp_types)
    result = {"run": str(run.resolve()), "pacing": summary["pacing"], "decoded": len(decoded),
              "selected": len(selected), "dropped": len(dropped), "processed_unique": len(processed),
              "pose_rows": len(poses), "submaps": summary["submaps"],
              "frame_partition_valid": True, "pose_mapping_valid": True,
              "timestamp_types": timestamp_types, "timestamps_approximate": approximate,
              "estimated_trajectory_file": "estimated_approximate.tum" if approximate else "estimated_pts.tum",
              "ate_rmse": None,
              "limitations": ["TUM-format estimate only; no ground truth or evo evaluation",
                              "Reconstruction translation scale unverified"],
              "mapping": [{"pose_frame_id": int(index), "source_frame_id": processed[index][0],
                           "timestamp_seconds": processed[index][1], "timestamp_type": processed[index][2]} for index in pose_ids]}
    return result, tum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result, tum = validate(args.run)
    args.output.mkdir(parents=True, exist_ok=False)
    np.savetxt(args.output / result["estimated_trajectory_file"], tum, fmt="%.9f")
    (args.output / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "mapping"}, indent=2))


if __name__ == "__main__":
    main()
