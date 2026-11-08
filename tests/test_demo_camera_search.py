import numpy as np
from scipy.spatial.transform import Rotation

from vggt_slam.demo.camera_view import rgb_camera, raster_camera
from vggt_slam.demo.search_policy import candidate_order, model_query, outcome_text


def test_camera_pose_matches_recorded_rgb_axes():
    rotation = Rotation.from_euler('xyz', [10, -20, 30], degrees=True).as_matrix()
    center = np.array([3., -2., 5.])
    k = np.array([[100., 15., 30.], [0., 80., 25.], [0., 0., 1.]])
    projection = k @ np.column_stack([rotation, -rotation @ center])
    camera = rgb_camera(projection, (60, 80))
    np.testing.assert_allclose(camera['position'], center)
    np.testing.assert_allclose(camera['forward'], rotation.T[:, 2])
    np.testing.assert_allclose(camera['up'], -rotation.T[:, 1])
    world_camera = Rotation.from_quat(camera['wxyz'][[1, 2, 3, 0]]).as_matrix()
    np.testing.assert_allclose(world_camera[:, 2], camera['forward'])
    np.testing.assert_allclose(-world_camera[:, 1], camera['up'])
    np.testing.assert_allclose(camera['intrinsic'], k)
    assert np.isclose(camera['fov'], 2*np.arctan(30/80))


def test_exact_camera_raster_handles_skew_lens_shift_and_occlusion():
    k = np.array([[10., 5., 30.], [0., 10., 20.], [0., 0., 1.]])
    projection = np.column_stack([k, np.zeros(3)])
    points = np.array([[2., 2., 2.], [1., 1., 1.], [0., 0., -1.]])
    colors = np.array([[255, 0, 0], [0, 255, 0], [255, 255, 255]], np.uint8)
    image, stats = raster_camera(points, colors, projection, (60, 80), point_scale=0)
    np.testing.assert_array_equal(image[60, 90], [0, 255, 0])
    assert stats['projected_points'] == 2
    assert stats['occupied_pixels'] == 1


def test_camera_raster_empty_is_valid():
    image, stats = raster_camera(np.empty((0, 3)), np.empty((0, 3), np.uint8), np.eye(4), (10, 20))
    assert image.shape == (20, 40, 3)
    assert stats['projected_points'] == 0


def test_search_retries_ranked_candidates_and_deduplicates_current_frame():
    frames = [{'source_frame_id': str(i)} for i in range(6)]
    ordered = candidate_order(frames, [.9, .8, .7, .6, .5, .4], current=frames[1], limit=5)
    assert [f['source_frame_id'] for f in ordered] == ['1', '0', '2', '3', '4']
    assert model_query('자동차') == 'car'
    assert model_query('red truck') == 'red truck'


def test_search_distinguishes_no_mask_from_no_depth_support():
    assert '깊이점' in outcome_text(3, 0, 5)
    assert '부재를 의미하지' in outcome_text(0, 0, 5)
    assert '3D 박스 1개' in outcome_text(3, 1, 2)


def test_viser_camera_setter_keeps_rgb_forward_and_up():
    """Exercise Viser's real public setter, which already handles GL conversion."""
    from types import SimpleNamespace
    import viser
    handle = viser.CameraHandle(SimpleNamespace(_websock_connection=SimpleNamespace(queue_message=lambda _: None)))
    handle._state.look_at = np.array([0., 0., 1.])
    handle._state.up_direction = np.array([0., -1., 0.])
    handle._state.wxyz = np.array([1., 0., 0., 0.])
    handle._state.update_timestamp = 1.
    rotation = Rotation.from_euler('xyz', [10, -20, 30], degrees=True).as_matrix()
    center = np.array([3., -2., 5.])
    k = np.diag([100., 100., 1.])
    camera = rgb_camera(k @ np.column_stack([rotation, -rotation @ center]), (60, 80))
    handle.position = camera['position']
    handle.up_direction = camera['up']
    handle.look_at = camera['position'] + camera['forward'] * 3
    handle.wxyz = camera['wxyz']
    direction = handle.look_at - handle.position
    np.testing.assert_allclose(direction / np.linalg.norm(direction), camera['forward'])
    assert np.dot(handle.up_direction / np.linalg.norm(handle.up_direction), camera['up']) > .999


def test_overview_fits_bounding_sphere_for_wide_and_tall_viewports():
    from vggt_slam.demo.camera_view import overview_distance
    radius = 5.
    fov = np.radians(60)
    for aspect in [.4, 1., 3.6]:
        distance = overview_distance(radius*2, fov, aspect)
        angular_radius = np.arcsin(radius / distance)
        assert angular_radius < fov/2
        assert angular_radius < np.arctan(np.tan(fov/2)*aspect)
