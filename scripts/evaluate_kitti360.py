"""Evaluate frame-index camera poses against KITTI-360 cam0_to_world.txt."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from vggt_slam.trajectory_metrics import align_similarity


def load_reference(path):
    rows = np.loadtxt(path, ndmin=2)
    if rows.shape[1] != 17 or not np.isfinite(rows).all():
        raise ValueError("Expected KITTI-360 frame ID followed by a 4x4 camera-to-world matrix")
    ids = np.rint(rows[:, 0]).astype(int)
    if not np.array_equal(ids, rows[:, 0]) or len(np.unique(ids)) != len(ids):
        raise ValueError("Reference frame IDs must be unique integers")
    matrices = rows[:, 1:].reshape(-1, 4, 4)
    if not np.allclose(matrices[:, 3], [0, 0, 0, 1], atol=1e-8):
        raise ValueError("Reference poses must be homogeneous 4x4 matrices")
    return ids, matrices


def match_frames(estimated, reference_ids, reference_matrices):
    if estimated.ndim != 2 or estimated.shape[1] != 8 or not np.isfinite(estimated).all():
        raise ValueError("Expected finite frame_id XYZ quaternion XYZW rows")
    frame_ids = np.rint(estimated[:, 0]).astype(int)
    if not np.array_equal(frame_ids, estimated[:, 0]) or len(np.unique(frame_ids)) != len(frame_ids):
        raise ValueError("Estimated frame IDs must be unique integers")
    lookup = {int(frame): index for index, frame in enumerate(reference_ids)}
    keep = np.array([frame in lookup for frame in frame_ids])
    matched = estimated[keep]
    target = reference_matrices[[lookup[int(frame)] for frame in frame_ids[keep]], :3, 3]
    return matched, target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimated_poses", type=Path, required=True)
    parser.add_argument("--reference_poses", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    args = parser.parse_args()
    estimated = np.loadtxt(args.estimated_poses, ndmin=2)
    reference_ids, reference_matrices = load_reference(args.reference_poses)
    matched, target = match_frames(estimated, reference_ids, reference_matrices)
    aligned, scale, rotation, translation, singular = align_similarity(matched[:, 1:4], target)
    errors = np.linalg.norm(aligned - target, axis=1)
    aligned_all = scale * (estimated[:, 1:4] @ rotation.T) + translation
    reference_up = rotation.T @ np.array([0., 0., 1.])
    metrics = {"estimated_frames": len(estimated), "reference_frames": len(reference_ids),
               "matched_frames": len(matched), "unmatched_estimated_frames": len(estimated) - len(matched),
               "matched_frame_range": [int(matched[0, 0]), int(matched[-1, 0])],
               "full_reference_path_length_m": float(np.linalg.norm(np.diff(reference_matrices[:, :3, 3], axis=0), axis=1).sum()),
               "alignment": "Proper Sim(3) fitted to all matched camera positions",
               "meters_per_reconstruction_unit": scale,
               "rotation_reconstruction_to_reference": rotation.tolist(),
               "translation_reconstruction_to_reference_m": translation.tolist(),
               "reference_world_up_in_reconstruction": reference_up.tolist(),
               "alignment_singular_values": singular.tolist(),
               "ate_rmse_m": float(np.sqrt(np.mean(errors ** 2))),
               "ate_median_m": float(np.median(errors)), "ate_max_m": float(errors.max()),
               "estimated_input": str(args.estimated_poses.resolve()),
               "reference_input": str(args.reference_poses.resolve()),
               "limitations": ["Alignment and scale are fitted on the evaluated trajectory",
                               "Missing reference frame IDs are excluded, not interpolated",
                               "ATE is not the official KITTI segment-drift benchmark",
                               "No independent terrain-height or LiDAR geometry validation"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "trajectory_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    aligned_rotations = Rotation.from_matrix(rotation) * Rotation.from_quat(estimated[:, 4:8])
    np.savetxt(args.output_dir / "aligned_poses.txt",
               np.column_stack([estimated[:, 0], aligned_all, aligned_rotations.as_quat()]),
               fmt="%.10f", header="frame_id XYZ quaternion XYZW; fitted reference-world Sim(3)")
    np.savetxt(args.output_dir / "frame_errors.csv", np.column_stack([matched[:, 0], errors]),
               delimiter=",", header="frame_id,position_error_m", comments="")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)
    offset = target[0]
    axes[0].plot(target[:, 0] - offset[0], target[:, 1] - offset[1], label="KITTI-360 reference", lw=1)
    axes[0].plot(aligned[:, 0] - offset[0], aligned[:, 1] - offset[1], label="Aligned estimate", lw=1)
    axes[0].set(xlabel="Relative world X (m)", ylabel="Relative world Y (m)", title="Camera trajectory")
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[0].legend(fontsize=8)
    axes[1].plot(matched[:, 0], errors, lw=0.8, color="#e55c35")
    axes[1].set(xlabel="Source frame ID", ylabel="Position error (m)", title=f"Aligned ATE RMSE: {metrics['ate_rmse_m']:.2f} m")
    axes[2].plot(matched[:, 0], target[:, 2] - offset[2], label="Reference", lw=1)
    axes[2].plot(matched[:, 0], aligned[:, 2] - offset[2], label="Aligned estimate", lw=1)
    axes[2].set(xlabel="Source frame ID", ylabel="Relative camera Z (m)", title="Camera height")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.2)
    fig.suptitle("KITTI-360 0000 | trajectory comparison after fitted Sim(3) alignment")
    fig.savefig(args.output_dir / "trajectory_comparison.png", dpi=160)
    plt.close(fig)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
