from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.spatial.transform import Rotation

from scripts.export_bev_maps import grouped_quantiles, local_basis
import pytest


def test_bev_basis_is_rotation_invariant():
    poses = np.array([[0, 0, 0, 0, 0, 0, 0, 1], [1, 0, 0, 2, 0, 0, 0, 1]], dtype=float)
    baseline = local_basis(poses)
    rotation = Rotation.from_euler("xyz", [0.2, 0.1, 0.3])
    poses[:, 1:4] = rotation.apply(poses[:, 1:4])
    poses[:, 4:] = rotation.as_quat()
    basis = local_basis(poses)
    np.testing.assert_allclose(basis @ rotation.as_matrix(), baseline, atol=1e-12)
    np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-12)
    assert np.linalg.det(basis) > 0


def test_quantile_raster_preserves_empty_cells_and_representatives():
    cells = np.array([2, 0, 2, 0, 2])
    heights = np.array([9., 3., 1., 7., 5.])
    counts, rasters, samples = grouped_quantiles(cells, heights, 4, [0.1, 0.5, 0.9])
    np.testing.assert_array_equal(counts, [2, 0, 3, 0])
    for quantile, raster in rasters.items():
        for cell in (0, 2):
            assert raster[cell] == np.quantile(heights[cells == cell], quantile, method="lower")
        assert np.isnan(raster[[1, 3]]).all()
        represented_cells, indices = samples[quantile]
        np.testing.assert_array_equal(cells[indices], represented_cells)
        np.testing.assert_array_equal(heights[indices], raster[represented_cells])


def test_bev_basis_handles_closed_routes():
    angle = np.linspace(0, 2 * np.pi, 101)
    poses = np.zeros((len(angle), 8))
    poses[:, 0] = np.arange(len(angle))
    poses[:, 1] = np.cos(angle)
    poses[:, 3] = 3 * np.sin(angle)
    poses[:, 7] = 1
    basis = local_basis(poses)
    np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-12)
    assert abs(basis[1, 2]) == pytest.approx(1)
    assert np.linalg.det(basis) > 0


def test_bev_basis_rejects_stationary_poses():
    poses = np.zeros((3, 8))
    poses[:, 7] = 1
    with pytest.raises(ValueError, match="displacement"):
        local_basis(poses)


def test_bev_basis_can_use_an_external_vertical_reference():
    poses = np.zeros((3, 8))
    poses[:, 1] = [0, 1, 2]
    poses[:, 7] = 1
    basis = local_basis(poses, [0, 0, 2])
    np.testing.assert_allclose(basis[2], [0, 0, 1])
    np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-12)
    with pytest.raises(ValueError):
        local_basis(poses, [0, 0, 0])


@pytest.mark.parametrize("sample_cap", [None, 10000])
def test_bev_export_recovers_synthetic_sloping_road(tmp_path, sample_cap):
    # A gray road at Y=0.1+0.02*Z, viewed from a camera 0.1 units above it.
    right, forward = np.meshgrid(np.linspace(-0.6, 0.6, 61), np.linspace(0, 10, 501))
    xyz = np.column_stack([right.ravel(), 0.1 + 0.02 * forward.ravel(), forward.ravel()])
    cloud = np.empty(len(xyz), dtype=[("xyz", "<f4", (3,)), ("rgb", "<u4")])
    cloud["xyz"] = xyz
    cloud["rgb"] = (100 << 16) | (100 << 8) | 100
    path = tmp_path / "road.pcd"
    header = ("VERSION 0.7\nFIELDS x y z rgb\nSIZE 4 4 4 4\nTYPE F F F U\nCOUNT 1 1 1 1\n"
              f"WIDTH {len(cloud)}\nHEIGHT 1\nPOINTS {len(cloud)}\nDATA binary\n")
    path.write_bytes(header.encode() + cloud.tobytes())
    poses = np.zeros((101, 8))
    poses[:, 0] = np.arange(101)
    poses[:, 3] = np.linspace(0, 10, 101)
    poses[:, 2] = 0.02 * poses[:, 3]
    poses[:, 7] = 1
    pose_path = tmp_path / "poses.txt"
    np.savetxt(pose_path, poses)
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "maps"
    command = [sys.executable, str(root / "scripts/export_bev_maps.py"),
               "--point_cloud", str(path), "--poses", str(pose_path),
               "--cell_size", "0.2", "--output_dir", str(output)]
    if sample_cap is not None:
        command += ["--max_points", str(sample_cap)]
    subprocess.run(command,
                   check=True, capture_output=True, text=True, timeout=30)
    with np.load(output / "rasters.npz") as raster:
        ground = raster["ground_elevation"]
        expected = np.broadcast_to(-0.02 * raster["forward"][None, :], ground.shape)
        valid = np.isfinite(ground)
        assert valid.sum() > 20
        np.testing.assert_allclose(ground[valid], expected[valid], atol=0.005)
        assert np.isnan(ground[raster["ground_count"] < 5]).all()
        assert np.isnan(raster["meters_per_unit"])
        assert raster["point_count"].sum() == (sample_cap or len(cloud))
    assert (output / "bev_rgb.png").is_file()
    assert (output / "ground_contours.svg").is_file()
    assert (output / "contour_lines.csv").stat().st_size > 100


def test_surface_only_does_not_invent_ground(tmp_path):
    # Saturated red elevated surface has no gray road candidates.
    x, z = np.meshgrid(np.linspace(-1, 1, 101), np.linspace(0, 10, 501))
    xyz = np.column_stack([x.ravel(), -2 - 0.1 * z.ravel(), z.ravel()])
    from vggt_slam.pcd_io import write_cloud_chunks
    path = tmp_path / 'surface.pcd'
    write_cloud_chunks(path, [(xyz, np.tile([255, 0, 0], (len(xyz), 1)))])
    poses = np.zeros((101, 8))
    poses[:, 0] = np.arange(101)
    poses[:, 3] = np.linspace(0, 10, 101)
    poses[:, 7] = 1
    pose_path = tmp_path / 'poses.txt'
    np.savetxt(pose_path, poses)
    output = tmp_path / 'maps'
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'scripts/export_bev_maps.py'),
                    '--point_cloud', str(path), '--poses', str(pose_path),
                    '--surface_only', '--clip_percentile', '0.1',
                    '--cell_size', '0.2', '--output_dir', str(output)],
                   check=True, capture_output=True, text=True, timeout=30)
    with np.load(output / 'rasters.npz') as raster:
        assert np.isnan(raster['ground_elevation']).all()
        assert np.isnan(raster['ground_smoothed']).all()
        assert (raster['ground_count'] == 0).all()
        assert np.isfinite(raster['contour_elevation']).sum() > 20
    assert (output / 'surface_contours.svg').is_file()
    assert not (output / 'ground_contours.png').exists()
