"""Position alignment shared by dataset evaluation tools."""

import numpy as np


def align_similarity(source, target):
    """Least-squares proper Sim(3), mapping source XYZ to target XYZ."""
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    if source.shape != target.shape or source.ndim != 2 or source.shape[1] != 3 or len(source) < 3:
        raise ValueError("Expected matching Nx3 positions, with at least three matches")
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("Positions must be finite")
    source_mean, target_mean = source.mean(axis=0), target.mean(axis=0)
    centered_source, centered_target = source - source_mean, target - target_mean
    variance = np.mean(np.sum(centered_source ** 2, axis=1))
    if variance < 1e-12:
        raise ValueError("Estimated trajectory has no usable displacement")
    covariance = centered_target.T @ centered_source / len(source)
    left, singular, right = np.linalg.svd(covariance)
    sign = np.ones(3)
    sign[-1] = 1 if np.linalg.det(left @ right) >= 0 else -1
    rotation = left @ np.diag(sign) @ right
    scale = float(np.dot(singular, sign) / variance)
    if scale <= 0:
        raise ValueError("Cannot estimate a positive similarity scale")
    translation = target_mean - scale * rotation @ source_mean
    aligned = scale * (source @ rotation.T) + translation
    return aligned, scale, rotation, translation, singular
