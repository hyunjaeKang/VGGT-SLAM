"""Export local RGB BEV, surface elevation, and ground-proxy contour rasters."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from vggt_slam.pcd_io import read_cloud


def local_basis(poses, up_vector=None):
    if up_vector is None:
        rotations = Rotation.from_quat(poses[:, 4:8])
        up = rotations.apply(np.tile([0., -1., 0.], (len(poses), 1))).mean(axis=0)
    else:
        up = np.asarray(up_vector, dtype=float).copy()
        if up.shape != (3,) or not np.isfinite(up).all():
            raise ValueError("Up vector must contain three finite values")
    if np.linalg.norm(up) < 1e-6:
        raise ValueError("Camera orientations do not define a consistent up direction")
    up /= np.linalg.norm(up)
    forward = poses[-1, 1:4] - poses[0, 1:4]
    forward -= np.dot(forward, up) * up
    horizontal_positions = poses[:, 1:4] - np.outer(poses[:, 1:4] @ up, up)
    path_length = np.linalg.norm(np.diff(horizontal_positions, axis=0), axis=1).sum()
    # A closed route has no useful endpoint direction; use its principal axis.
    if np.linalg.norm(forward) < max(1e-6, 0.05 * path_length):
        centered = horizontal_positions - horizontal_positions.mean(axis=0)
        _, singular, axes = np.linalg.svd(centered, full_matrices=False)
        if len(singular) == 0 or singular[0] < 1e-6:
            raise ValueError("Trajectory must have a nonzero horizontal displacement")
        forward = axes[0]
        deltas = np.diff(horizontal_positions, axis=0)
        moving = deltas[np.linalg.norm(deltas, axis=1) > 1e-6]
        if len(moving) and np.dot(forward, moving[:10].mean(axis=0)) < 0:
            forward = -forward
        forward -= np.dot(forward, up) * up
    if np.linalg.norm(forward) < 1e-6:
        raise ValueError("Trajectory must have a nonzero horizontal displacement")
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, up)
    return np.stack([right, forward, up])


def grouped_quantiles(cells, heights, size, quantiles):
    """Lower order-statistic quantiles and counts; empty cells remain NaN."""
    if len(cells) == 0:
        raise ValueError("No points available for rasterization")
    order = np.lexsort((heights, cells))
    sorted_cells = cells[order]
    starts = np.r_[0, np.flatnonzero(np.diff(sorted_cells)) + 1]
    counts = np.diff(np.r_[starts, len(order)])
    unique_cells = sorted_cells[starts]
    count_grid = np.zeros(size, dtype=np.int32)
    count_grid[unique_cells] = counts
    rasters, samples = {}, {}
    for quantile in quantiles:
        indices = order[starts + np.floor((counts - 1) * quantile).astype(np.int64)]
        raster = np.full(size, np.nan, dtype=np.float32)
        raster[unique_cells] = heights[indices]
        rasters[quantile] = raster
        samples[quantile] = (unique_cells, indices)
    return count_grid, rasters, samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--point_cloud", type=Path, required=True)
    parser.add_argument("--poses", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, default=Path("logs/640_car_bev"))
    parser.add_argument("--cell_size", type=float, help="Grid cell width in output coordinate units")
    parser.add_argument("--meters_per_unit", type=float, help="Optional independently measured scale")
    parser.add_argument("--max_points", type=int, help="Optional uniform sample cap for large PCD files")
    parser.add_argument("--up_vector", type=float, nargs=3,
                        help="Optional known up direction in reconstruction coordinates")
    parser.add_argument("--surface_only", action="store_true",
                        help="Contour the upper surface instead of estimating ground")
    parser.add_argument("--clip_percentile", type=float, default=0,
                        help="Explicitly remove this percentile at each XYZ tail for visualization")
    args = parser.parse_args()
    if not 0 <= args.clip_percentile < 10:
        parser.error("--clip_percentile must be in [0, 10)")
    if args.meters_per_unit is not None and args.meters_per_unit <= 0:
        parser.error("--meters_per_unit must be positive")
    if args.cell_size is not None and args.cell_size <= 0:
        parser.error("--cell_size must be positive")
    if args.max_points is not None and args.max_points < 1000:
        parser.error("--max_points must be at least 1000")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cloud = read_cloud(args.point_cloud)
    input_point_count = len(cloud)
    if args.max_points is not None and len(cloud) > args.max_points:
        cloud = cloud[np.linspace(0, len(cloud) - 1, args.max_points, dtype=np.int64)]
    poses = np.loadtxt(args.poses, ndmin=2)
    if poses.shape[1] != 8 or len(poses) < 2 or not np.isfinite(poses).all():
        parser.error("Expected at least two finite TUM poses (timestamp, XYZ, quaternion XYZW)")
    basis = local_basis(poses, args.up_vector)
    origin = poses[0, 1:4].copy()
    scale = args.meters_per_unit or 1.0
    xyz = ((cloud["xyz"] - origin.astype(np.float32)) @ basis.astype(np.float32).T) * scale
    trajectory = ((poses[:, 1:4] - origin) @ basis.T) * scale
    if not np.isfinite(xyz).all():
        parser.error("The input point cloud contains NaN/Inf coordinates")
    sampled_points = len(xyz)
    clip_bounds = None
    if args.clip_percentile:
        bounds = np.percentile(xyz, [args.clip_percentile, 100 - args.clip_percentile], axis=0)
        keep = ((xyz >= bounds[0]) & (xyz <= bounds[1])).all(axis=1)
        xyz, cloud = xyz[keep], cloud[keep]
        clip_bounds = bounds.tolist()
    print(f"Rasterizing {len(xyz):,} points...", flush=True)

    road_offset = 0.0
    ground_tolerance = ground_width = None
    ground_mask = np.zeros(len(xyz), dtype=bool)
    if not args.surface_only:
        # Estimate camera-to-road offset from gray points close to the camera path.
        sample_ids = np.arange(0, len(xyz), max(1, len(xyz) // 250_000))
        sample = xyz[sample_ids]
        packed = cloud["rgb"][sample_ids]
        rgb = np.stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255], axis=1)
        tree = cKDTree(trajectory[:, :2])
        distance, nearest = tree.query(sample[:, :2])
        relative = sample[:, 2] - trajectory[nearest, 2]
        path_length = np.linalg.norm(np.diff(trajectory[:, :2], axis=0), axis=1).sum()
        gray = ((np.ptp(rgb.astype(np.float32), axis=1) < 30)
                & (rgb.mean(axis=1) > 40) & (rgb.mean(axis=1) < 200))
        candidates = gray & (distance < path_length * 0.01) & (relative < 0)
        if candidates.sum() < 100:
            parser.error("Insufficient road-like points to estimate a ground proxy")
        road_offset = float(np.median(relative[candidates]))
        mad = float(np.median(np.abs(relative[candidates] - road_offset)))
        ground_tolerance = max(4 * 1.4826 * mad, abs(road_offset) * 0.25)
        ground_width = 8 * abs(road_offset)
        ground_mask = np.zeros(len(xyz), dtype=bool)
        for start in range(0, len(xyz), 500_000):
            batch = xyz[start:start + 500_000]
            distance, nearest = tree.query(batch[:, :2])
            relative = batch[:, 2] - trajectory[nearest, 2]
            ground_mask[start:start + len(batch)] = ((distance <= ground_width)
                & (np.abs(relative - road_offset) <= ground_tolerance))

    # Fixed camera-up heights: do not flatten the road or remove its long-range grade.
    heights = xyz[:, 2] - road_offset
    cell = args.cell_size or float(np.ptp(xyz[:, 1]) / 1400)
    lower = np.floor(xyz[:, :2].min(axis=0) / cell) * cell
    shape = np.floor((xyz[:, :2].max(axis=0) - lower) / cell).astype(int) + 1
    rows, cols = int(shape[0]), int(shape[1])
    if rows * cols > 4_000_000:
        parser.error("Grid exceeds four million cells; increase --cell_size")
    row_ids = np.floor((xyz[:, 0] - lower[0]) / cell).astype(np.int64)
    col_ids = np.floor((xyz[:, 1] - lower[1]) / cell).astype(np.int64)
    cells = row_ids * cols + col_ids
    counts, surfaces, representatives = grouped_quantiles(cells, heights, rows * cols, [0.1, 0.5, 0.9])
    if args.surface_only:
        ground_counts = np.zeros(rows * cols, dtype=np.int64)
        grounds = {0.5: np.full(rows * cols, np.nan)}
    else:
        ground_counts, grounds, _ = grouped_quantiles(cells[ground_mask], heights[ground_mask], rows * cols, [0.5])
    ground = grounds[0.5].reshape(rows, cols)
    ground_counts = ground_counts.reshape(rows, cols)
    supported = ground_counts >= 5
    ground[~supported] = np.nan
    if not args.surface_only and supported.sum() < 20:
        parser.error("Insufficient supported ground cells; increase --cell_size")
    # Smooth only within observed cells, with normalized weights; no gap filling.
    weights = gaussian_filter(supported.astype(float), 1.0)
    smooth = gaussian_filter(np.nan_to_num(ground), 1.0) / np.maximum(weights, 1e-12)
    smooth[~supported] = np.nan
    color_grid = np.ones((rows * cols, 3), dtype=np.float32)
    ids, indices = representatives[0.9]
    packed = cloud["rgb"][indices]
    color_grid[ids] = np.stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255], axis=1) / 255
    color_grid = color_grid.reshape(rows, cols, 3)
    surface = surfaces[0.9].reshape(rows, cols)
    surface[counts.reshape(rows, cols) < 5] = np.nan
    ground_smooth = smooth.copy()
    if args.surface_only:
        supported_surface = np.isfinite(surface)
        if supported_surface.sum() < 20:
            parser.error("Insufficient supported surface cells; increase --cell_size")
        weights = gaussian_filter(supported_surface.astype(float), 1.0)
        smooth = gaussian_filter(np.nan_to_num(surface), 1.0) / np.maximum(weights, 1e-12)
        smooth[~supported_surface] = np.nan
    forward = lower[1] + (np.arange(cols) + 0.5) * cell
    right = lower[0] + (np.arange(rows) + 0.5) * cell
    extent = [lower[1], lower[1] + cols * cell, lower[0], lower[0] + rows * cell]
    unit = "m" if args.meters_per_unit else "unscaled units"
    levels = np.linspace(float(np.nanpercentile(smooth, 1)), float(np.nanpercentile(smooth, 99)), 13)
    if levels[-1] - levels[0] < 1e-8:
        parser.error("Ground height is nearly constant; contour levels are undefined")

    def draw(ax, kind):
        if kind == "rgb":
            ax.imshow(color_grid, origin="lower", extent=extent, interpolation="nearest")
            ax.set_title("RGB bird's-eye view | upper-surface color")
        elif kind == "surface":
            image = ax.imshow(surface, origin="lower", extent=extent, cmap="terrain", interpolation="nearest")
            ax.set_title("Surface elevation | per-cell 90th percentile, includes vegetation")
            ax.figure.colorbar(image, ax=ax, shrink=0.8, label=f"Relative height ({unit})")
        else:
            image = ax.imshow(smooth, origin="lower", extent=extent, cmap="terrain", interpolation="nearest")
            contour = ax.contour(forward, right, np.ma.masked_invalid(smooth), levels=levels,
                                 colors="#283c32", linewidths=0.6, corner_mask=False)
            ax.clabel(contour, inline=True, fontsize=7, fmt="%.2f")
            ax.set_title("Surface contours | includes buildings and vegetation; NOT terrain" if args.surface_only
                         else "Estimated ground contours | road-corridor proxy, observed support only")
            ax.figure.colorbar(image, ax=ax, shrink=0.8, label=f"Relative height ({unit})")
        ax.plot(trajectory[:, 1], trajectory[:, 0], color="#e05240", lw=0.8, alpha=0.8)
        ax.scatter(trajectory[0, 1], trajectory[0, 0], c="limegreen", s=18, zorder=5, label="Start")
        ax.scatter(trajectory[-1, 1], trajectory[-1, 0], c="red", s=18, zorder=5, label="End")
        ax.set(xlabel=f"Forward ({unit})", ylabel=f"Right ({unit})", xlim=extent[:2], ylim=extent[2:])
        ax.set_aspect("equal")
        return contour if kind == "ground" else None

    for kind, filename in (("rgb", "bev_rgb"), ("surface", "surface_elevation"), ("ground", "surface_contours" if args.surface_only else "ground_contours")):
        fig, ax = plt.subplots(figsize=(15, 4.8), constrained_layout=True)
        contour = draw(ax, kind)
        fig.text(0.5, 0.01, "Local reconstruction coordinates; no geographic reference or verified terrain accuracy.",
                 ha="center", fontsize=8, color="#555555")
        fig.savefig(args.output_dir / f"{filename}.png", dpi=180)
        if kind == "ground":
            fig.savefig(args.output_dir / f"{filename}.svg")
            with (args.output_dir / "contour_lines.csv").open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["height", "segment_id", "vertex_id", "forward", "right"])
                segment_id = 0
                for level, segments in zip(contour.levels, contour.allsegs):
                    for segment in segments:
                        if len(segment) < 2:
                            continue
                        for index, vertex in enumerate(segment):
                            writer.writerow([level, segment_id, index, *vertex])
                        segment_id += 1
        plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), constrained_layout=True)
    for ax, kind in zip(axes, ("rgb", "surface", "ground")):
        draw(ax, kind)
    fig.savefig(args.output_dir / "overview.png", dpi=160)
    plt.close(fig)
    np.savez_compressed(args.output_dir / "rasters.npz", forward=forward, right=right,
                        rgb=color_grid, point_count=counts.reshape(rows, cols),
                        surface_p10=surfaces[0.1].reshape(rows, cols),
                        surface_p50=surfaces[0.5].reshape(rows, cols), surface_p90=surface,
                        ground_elevation=ground, ground_smoothed=ground_smooth, ground_count=ground_counts,
                        contour_elevation=smooth,
                        trajectory=trajectory, world_to_local_basis=basis, world_origin=origin,
                        meters_per_unit=args.meters_per_unit or np.nan,
                        reference_height_before_scale=road_offset / scale)
    metadata = {"source_point_cloud": str(args.point_cloud.resolve()), "source_poses": str(args.poses.resolve()),
                "input_points": input_point_count, "rasterized_points": len(xyz),
                "sampling": "uniform index sample" if sampled_points < input_point_count else "all points",
                "sampled_points_before_clip": sampled_points,
                "clip_percentile_per_tail": args.clip_percentile, "clip_bounds_xyz": clip_bounds,
                "contour_source": "upper surface P90" if args.surface_only else "estimated ground",
                "grid_rows": rows, "grid_columns": cols, "cell_size": cell,
                "units": unit, "georeferenced": False, "meters_per_unit": args.meters_per_unit,
                "up_estimation": ("Provided up vector in reconstruction coordinates" if args.up_vector
                                  else "Mean camera negative-Y axis; gravity is not measured"),
                "up_vector_override": args.up_vector,
                "horizontal_axis_estimation": "Endpoint direction; principal trajectory axis for nearly closed routes",
                "world_to_local_basis": basis.tolist(), "world_origin": origin.tolist(),
                "road_camera_height_offset": road_offset, "ground_tolerance": ground_tolerance,
                "ground_corridor_half_width": ground_width, "ground_candidate_points": int(ground_mask.sum()),
                "supported_ground_cells": int(supported.sum()), "minimum_ground_points_per_cell": 5,
                "ground_support_fraction": float(supported.mean()), "ground_smoothing_sigma_cells": 1,
                "quantile_method": "lower order statistic (floor((n - 1) * q))",
                "contour_interval": float(levels[1] - levels[0]), "contour_levels": levels.tolist(),
                "height_reference": ("First camera height" if args.surface_only else
                                     "Fixed estimated road height at first camera; road grade is retained"),
                "limitations": ["Monocular reconstruction has unverified absolute scale and height drift",
                                ("Surface contours include objects and are not ground terrain" if args.surface_only else
                                 "Ground is a trajectory-relative heuristic, not verified bare-earth terrain"),
                                "Unsupported cells are unknown and remain NaN; no gap extrapolation"]}
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    print(f"Saved maps to {args.output_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
