import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from scripts.evaluate_pandaset import align_similarity


def test_similarity_recovers_scale_rotation_and_translation():
    source = np.random.default_rng(7).normal(size=(40, 3))
    rotation = Rotation.from_euler("xyz", [0.3, -0.2, 0.6]).as_matrix()
    target = 4.2 * source @ rotation.T + np.array([3., 8., -2.])
    aligned, scale, fitted_rotation, translation, _ = align_similarity(source, target)
    np.testing.assert_allclose(aligned, target, atol=1e-12)
    assert scale == pytest.approx(4.2)
    np.testing.assert_allclose(fitted_rotation, rotation, atol=1e-12)
    np.testing.assert_allclose(translation, [3, 8, -2], atol=1e-12)


def test_similarity_does_not_allow_reflections():
    source = np.random.default_rng(8).normal(size=(40, 3))
    target = source * [-1, 1, 1]
    aligned, scale, rotation, _, _ = align_similarity(source, target)
    assert np.linalg.det(rotation) == pytest.approx(1)
    assert scale > 0
    assert np.linalg.norm(aligned - target) > 0.1


def test_similarity_rejects_stationary_estimate():
    with pytest.raises(ValueError, match="displacement"):
        align_similarity(np.zeros((4, 3)), np.ones((4, 3)))
