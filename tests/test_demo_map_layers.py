import numpy as np
import pytest

from vggt_slam.demo.bev import raster_bev
from vggt_slam.demo.sky import sky_scores_for_points


def test_sky_projection_preserves_unprojectable_points_and_boundary_margin():
    probability = np.zeros((7, 7), np.uint8)
    probability[1, 3] = 240
    points = np.array([[3, 1, 1], [3, 3, 1], [3, 5, 1], [90, 90, 1], [3, 1, -1], [0, 0, 0]])
    scores, count = sky_scores_for_points(points, np.eye(4), probability, margin=2)
    assert scores.tolist() == [240, 240, 0, 0, 0, 0]
    assert count == 3


def test_sky_pixel_correspondence_uses_recorded_projective_camera():
    probability = np.zeros((8, 8), np.uint8)
    probability[3, 5] = 255
    projection = np.eye(4)
    projection[:3, :3] = [[2, 0, 3], [0, 2, 3], [0, 0, 1]]
    scores, count = sky_scores_for_points(np.array([[1, 0, 1], [0, 0, 1]]), projection, probability, margin=0)
    assert scores.tolist() == [255, 0]
    assert count == 2


def test_bev_unknown_cells_remain_dark_and_current_position_is_visible():
    points = np.array([[0., 0., 0.], [1., 0., 1.], [np.nan, 0., 0.]])
    colors = np.array([[220, 220, 220], [100, 150, 200], [255, 255, 255]], np.uint8)
    image, stats = raster_bev(points, colors, np.array([[0., 0., 0.], [.5, 0., .5]]))
    assert stats['visible_points'] == 2
    assert stats['trajectory_points'] == 2
    assert stats['occupied_cells'] == 2
    assert np.count_nonzero(np.all(image == [15, 23, 42], axis=2)) > 200000
    assert np.any(np.all(image == [34, 211, 238], axis=2))
    assert np.isfinite(stats['span'])


def test_bev_empty_and_degenerate_maps_have_finite_bounds():
    for points in (np.empty((0, 3)), np.zeros((10, 3))):
        image, stats = raster_bev(points, np.zeros(points.shape, np.uint8), np.zeros((1, 3)))
        assert image.shape == (480, 480, 3)
        assert 0 < stats['span'] < float('inf')
    with pytest.raises(ValueError):
        raster_bev(np.empty((0, 3)), np.empty((0, 3)), [], plane='bad')
