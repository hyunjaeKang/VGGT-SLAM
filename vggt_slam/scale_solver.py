import numpy as np
import open3d as o3d

def debug_visualize(pcd1_points, pcd2_points):
    pcd1 = o3d.geometry.PointCloud()
    pcd1.points = o3d.utility.Vector3dVector(pcd1_points)
    pcd1.paint_uniform_color([1, 0, 0])  # red

    pcd2 = o3d.geometry.PointCloud()
    pcd2.points = o3d.utility.Vector3dVector(pcd2_points)
    pcd2.paint_uniform_color([0, 0, 1])  # blue

    o3d.visualization.draw_geometries([pcd1, pcd2], window_name="Pairwise Point Clouds")

def estimate_scale_pairwise(X, Y, DEBUG=False):
    assert X.shape == Y.shape
    x_dists = np.linalg.norm(X, axis=1)
    y_dists = np.linalg.norm(Y, axis=1)
    valid = np.isfinite(x_dists) & np.isfinite(y_dists) & (x_dists > 1e-8) & (y_dists > 1e-8)
    if not np.any(valid):
        raise ValueError("No finite, nonzero correspondences available to estimate scale")
    scales = y_dists[valid] / x_dists[valid]
    scale = np.median(scales)

    if DEBUG:
        debug_visualize(X*scale, Y)

    return scale, None
