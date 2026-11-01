import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from vggt_slam.slam_utils import decompose_camera


@pytest.mark.parametrize("sign", [-1, 1])
@pytest.mark.parametrize("homogeneous", [False, True])
@pytest.mark.parametrize("no_inverse", [False, True])
def test_camera_decomposition_is_invariant_to_projective_sign(sign, homogeneous, no_inverse):
    calibration = np.array([[600., 0., 320.], [0., 620., 180.], [0., 0., 1.]])
    rotation = Rotation.from_euler("xyz", [.2, -.3, .4]).as_matrix()
    center = np.array([2., -3., 5.])
    translation = -rotation @ center
    projection = sign * calibration @ np.column_stack([rotation, translation])
    if homogeneous:
        full = np.eye(4)
        full[:3] = projection
        projection = full
    recovered_k, recovered_r, recovered_t, _ = decompose_camera(projection, no_inverse=no_inverse)
    np.testing.assert_allclose(recovered_k, calibration, atol=1e-10)
    np.testing.assert_allclose(recovered_r, rotation if no_inverse else rotation.T, atol=1e-12)
    np.testing.assert_allclose(recovered_t, translation if no_inverse else center, atol=1e-12)
    assert np.linalg.det(recovered_r) == pytest.approx(1)


def test_headless_solver_does_not_start_a_viewer(monkeypatch):
    from unittest.mock import Mock
    import vggt_slam.solver as module
    viewer = Mock(side_effect=AssertionError('viewer must not start'))
    monkeypatch.setattr(module, 'Viewer', viewer)
    monkeypatch.setattr(module, 'ImageRetrieval', Mock())
    solver = module.Solver(init_conf_threshold=25, device='cpu', enable_viewer=False)
    assert solver.viewer is None
    viewer.assert_not_called()


def test_headless_export_keeps_cloud_and_raw_cameras_if_pose_conversion_fails(monkeypatch, tmp_path):
    from pathlib import Path
    from unittest.mock import Mock
    import main as entry
    image_folder = tmp_path / 'images'
    image_folder.mkdir()
    (image_folder / 'frame_0.jpg').touch()
    output = tmp_path / 'output' / 'poses.txt'
    args = entry.parser.parse_args(['--image_folder', str(image_folder), '--device', 'cpu',
                                    '--headless', '--log_results', '--log_path', str(output)])
    monkeypatch.setattr(entry.parser, 'parse_args', lambda: args)
    solver = Mock()
    solver.flow_tracker.compute_disparity.return_value = True
    solver.run_predictions.return_value = {'detected_loops': []}
    for timer in (solver.vggt_timer, solver.loop_closure_timer, solver.clip_timer):
        timer.total_time = 1.
    submap = Mock()
    submap.get_lc_status.return_value = False
    submap.get_frame_ids.return_value = [0.]
    solver.map.ordered_submaps_by_key.return_value = [submap]
    solver.map.get_all_cam_matricies.return_value = np.eye(4)[None]
    solver.map.write_points_to_file.side_effect = lambda graph, path: Path(path).write_bytes(b'preserved point cloud')
    solver.map.write_poses_to_file.side_effect = RuntimeError('pose conversion failed')
    factory = Mock(return_value=solver)
    monkeypatch.setattr(entry, 'Solver', factory)
    monkeypatch.setattr(entry, 'VGGT', Mock())
    monkeypatch.setattr(entry.torch.hub, 'load_state_dict_from_url', lambda *a, **kw: {})
    monkeypatch.setattr(entry.cv2, 'imread', lambda *a: np.zeros((16, 16, 3), dtype=np.uint8))
    with pytest.raises(RuntimeError, match='pose conversion'):
        entry.main()
    assert not factory.call_args.kwargs['enable_viewer']
    solver.update_all_submap_vis.assert_not_called()
    assert output.with_name('poses_points.pcd').read_bytes() == b'preserved point cloud'
    with np.load(output.with_name('poses_camera_matrices.npz')) as backup:
        np.testing.assert_allclose(backup['projection_matrices'], np.eye(4)[None])
        np.testing.assert_array_equal(backup['frame_ids'], [0.])
