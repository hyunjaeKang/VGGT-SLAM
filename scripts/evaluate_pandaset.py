"""Compare exported frame-index poses with PandaSet camera reference poses."""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation


from vggt_slam.trajectory_metrics import align_similarity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimated_poses", type=Path, required=True)
    parser.add_argument("--camera_folder", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    args = parser.parse_args()
    estimated = np.loadtxt(args.estimated_poses, ndmin=2)
    reference = json.loads((args.camera_folder / "poses.json").read_text())
    timestamps = np.asarray(json.loads((args.camera_folder / "timestamps.json").read_text()))
    if estimated.shape[1] != 8 or not np.isfinite(estimated).all():
        parser.error("Expected finite rows: frame_id x y z qx qy qz qw")
    if len(reference) != len(timestamps):
        parser.error("Reference poses and timestamps have different lengths")
    ids = np.rint(estimated[:, 0]).astype(int)
    if (not np.allclose(ids, estimated[:, 0], atol=1e-6, rtol=0)
            or len(np.unique(ids)) != len(ids) or np.any(ids < 0) or np.any(ids >= len(reference))):
        parser.error("Estimated frame IDs must be unique integer indices into the reference sequence")
    target = np.array([[reference[i]["position"][key] for key in ("x", "y", "z")] for i in ids])
    aligned, scale, rotation, translation, singular = align_similarity(estimated[:, 1:4], target)
    errors = np.linalg.norm(aligned - target, axis=1)
    path_length = float(np.linalg.norm(np.diff(target, axis=0), axis=1).sum())
    metrics = {"matched_frames": len(ids), "reference_frames": len(reference),
               "capture_duration_seconds": float(timestamps[-1] - timestamps[0]),
               "matched_reference_path_length_m": path_length,
               "alignment": "Proper Sim(3) fitted to all matched positions (scale, rotation, translation)",
               "meters_per_reconstruction_unit": scale,
               "rotation_reconstruction_to_reference": rotation.tolist(),
               "translation_reconstruction_to_reference_m": translation.tolist(),
               "alignment_singular_values": singular.tolist(),
               "ate_rmse_m": float(np.sqrt(np.mean(errors ** 2))),
               "ate_median_m": float(np.median(errors)), "ate_max_m": float(errors.max()),
               "estimated_input": str(args.estimated_poses.resolve()),
               "reference_camera_folder": str(args.camera_folder.resolve()),
               "limitations": ["Scale and alignment are fitted on the evaluated frames; this is not absolute localization",
                               "Short, nearly straight routes weakly constrain rotation around the travel direction",
                               "No claim of independent depth, terrain-height, or object-search accuracy"]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "trajectory_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    aligned_rotations = Rotation.from_matrix(rotation) * Rotation.from_quat(estimated[:, 4:8])
    np.savetxt(args.output_dir / "aligned_poses.txt",
               np.column_stack([ids, aligned, aligned_rotations.as_quat()]), fmt="%.10f",
               header="frame_id x y z qx qy qz qw; world reference aligned by fitted Sim(3)")
    np.savetxt(args.output_dir / "frame_errors.csv", np.column_stack([ids, timestamps[ids], errors]),
               delimiter=",", header="frame_id,timestamp,position_error_m", comments="")

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    axes[0].plot(target[:, 0], target[:, 1], label="PandaSet reference", color="#2467a8")
    axes[0].plot(aligned[:, 0], aligned[:, 1], label="VGGT-SLAM aligned", color="#e55c35", ls="--")
    axes[0].set(xlabel="World X (m)", ylabel="World Y (m)", title="Camera trajectory (XY)")
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[0].legend(fontsize=8)
    axes[1].plot(ids, errors, color="#e55c35")
    axes[1].set(xlabel="Frame ID", ylabel="Position error (m)", title=f"Aligned ATE RMSE: {metrics['ate_rmse_m']:.3f} m")
    axes[2].plot(ids, target[:, 2], label="Reference", color="#2467a8")
    axes[2].plot(ids, aligned[:, 2], label="Aligned estimate", color="#e55c35", ls="--")
    axes[2].set(xlabel="Frame ID", ylabel="Camera world Z (m)", title="Camera height comparison")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.2)
    sequence = args.camera_folder.parent.parent.name
    fig.suptitle(f"PandaSet {sequence} | position comparison after full-trajectory Sim(3) alignment")
    fig.savefig(args.output_dir / "trajectory_comparison.png", dpi=160)
    plt.close(fig)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
