"""Explicit sky probabilities and pixel-to-preview correspondence (no model imports)."""
import numpy as np
from scipy.ndimage import maximum_filter


def sky_scores_for_points(points, projection, probability, margin=2):
    """Project camera-local preview points onto their recorded RGB pixel grid.

    probability uses 0=non-sky, 255=sky. Unprojectable points are preserved,
    rather than misclassified as sky. A pixel margin removes boundary halos.
    """
    points = np.asarray(points)
    image = maximum_filter(np.asarray(probability, np.uint8), size=2 * margin + 1)
    homogeneous = points @ projection[:3, :3].T + projection[:3, 3]
    valid = np.isfinite(homogeneous).all(axis=1) & (homogeneous[:, 2] > 1e-8)
    uv = np.zeros((len(points), 2), dtype=np.int64)
    uv[valid] = np.rint(homogeneous[valid, :2] / homogeneous[valid, 2:3]).astype(np.int64)
    h, w = image.shape
    valid &= (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h)
    scores = np.zeros(len(points), dtype=np.uint8)
    scores[valid] = image[uv[valid, 1], uv[valid, 0]]
    return scores, int(valid.sum())
