"""Export recorded RGB timestamps and run evo APE on a single TUM sequence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from evo.core import sync
from evo.tools import file_interface


def export_estimate(run):
    selection = json.loads((run / "selection.json").read_text())
    timestamps = {int(frame["frame_id"]): frame["timestamp"] for frame in selection["frames"]}
    poses = np.loadtxt(run / "poses.txt", ndmin=2)
    ids = poses[:, 0].astype(int)
    if poses.shape[1] != 8 or not np.isfinite(poses).all() or len(set(ids)) != len(ids):
        raise ValueError("poses require unique IDs and eight finite columns")
    if not np.array_equal(ids, poses[:, 0]) or any(index not in timestamps for index in ids):
        raise ValueError("pose frame ID is missing from selection")
    if any(timestamps[index] is None for index in ids):
        raise ValueError("timestamps are unavailable")
    result = poses.copy()
    result[:, 0] = [timestamps[index] for index in ids]
    if np.any(np.diff(result[:, 0]) <= 0):
        raise ValueError("estimate timestamps must strictly increase")
    if not np.allclose(np.linalg.norm(result[:, 4:8], axis=1), 1, atol=1e-4):
        raise ValueError("estimate quaternions must be normalized")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--groundtruth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-difference", type=float, default=0.02)
    args = parser.parse_args()
    if args.max_difference <= 0:
        parser.error("max-difference must be positive")
    estimate = export_estimate(args.run)
    args.output.mkdir(parents=True, exist_ok=False)
    estimated = args.output / "estimated.tum"
    np.savetxt(estimated, estimate, fmt="%.9f")
    reference = file_interface.read_tum_trajectory_file(str(args.groundtruth))
    trajectory = file_interface.read_tum_trajectory_file(str(estimated))
    matched_ref, matched_est = sync.associate_trajectories(reference, trajectory, max_diff=args.max_difference)
    command = [str(Path(sys.executable).parent / "evo_ape"), "tum", str(args.groundtruth), str(estimated),
               "-as", "--t_max_diff", str(args.max_difference), "--save_results", str(args.output / "evo_results.zip")]
    env = dict(os.environ, MPLBACKEND="Agg", MPLCONFIGDIR=str((args.output / "mpl_cache").resolve()))
    (args.output / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    with (args.output / "stdout.log").open("w") as log:
        subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, env=env)
    result = file_interface.load_res_file(str(args.output / "evo_results.zip"))
    import evo
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(8, 3), constrained_layout=True)
    axis.plot(matched_est.timestamps - matched_est.timestamps[0], result.np_arrays["error_array"])
    axis.set(xlabel="Seconds since first associated RGB", ylabel="Position APE (m)",
             title="TUM selected RGB subset · evo Sim(3) alignment")
    axis.grid(alpha=0.25)
    fig.savefig(args.output / "ape_errors.png", dpi=160)
    plt.close(fig)

    with args.groundtruth.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    metrics = {"ate_rmse_m": result.stats["rmse"], "statistics": result.stats,
               "matched_frames": matched_est.num_poses, "estimated_frames": len(estimate),
               "excluded_estimate_frames": len(estimate) - matched_est.num_poses,
               "reference_frames": reference.num_poses, "max_timestamp_difference_seconds": args.max_difference,
               "matched_timestamp_differences_seconds": np.abs(matched_ref.timestamps - matched_est.timestamps).tolist(),
               "alignment": "evo Sim(3) Umeyama fitted on all associated positions (-as)",
               "reference": str(args.groundtruth.resolve()), "reference_sha256": digest,
               "source_run": str(args.run.resolve()), "evo_version": evo.__version__,
               "limitations": ["Selected RGB subset of one sequence; not full benchmark",
                               "Scale and alignment fitted to evaluated GT positions; not absolute localization",
                               "Ground truth used only after inference"]}
    (args.output / "trajectory_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
