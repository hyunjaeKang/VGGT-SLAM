from unittest.mock import Mock

import numpy as np
import pytest
import torch

from vggt_slam.frame_overlap import FrameTracker
from vggt_slam.graph import PoseGraph
from vggt_slam.loop_closure import ImageRetrieval, LoopMatch, LoopMatchQueue
from vggt_slam.map import GraphMap
from vggt_slam.runtime import model_dtype, select_device
from vggt_slam.scale_solver import estimate_scale_pairwise
from vggt_slam.solver import Solver
from vggt_slam.submap import Submap


def test_cpu_selection_does_not_query_cuda_capability(monkeypatch):
    monkeypatch.setattr(torch.cuda, 'get_device_capability', Mock(side_effect=AssertionError))
    assert select_device('cpu') == torch.device('cpu')
    assert model_dtype(torch.device('cpu')) == torch.float32
    assert model_dtype(torch.device('mps')) == torch.float32


def test_graph_projection_and_optimization():
    graph = PoseGraph()
    transform = np.eye(4)
    transform[0, 3] = 2
    graph.add_homography(0, transform)
    graph.add_prior_factor(0, transform)
    graph.optimize()
    np.testing.assert_allclose(graph.get_projection_matrix(0), np.linalg.inv(transform), atol=1e-12)


def test_loop_queue_keeps_lowest_distances():
    queue = LoopMatchQueue(2)
    for score in (0.7, 0.2, 0.9, 0.1):
        queue.add(LoopMatch(score, 0, 0, 1, 0))
    assert [m.similarity_score for m in queue.get_matches()] == [0.1, 0.2]


def test_disabled_loops_do_not_search():
    retrieval = ImageRetrieval.__new__(ImageRetrieval)
    assert retrieval.find_loop_closures(None, None, max_loop_closures=0) == []


def test_semantic_search_accepts_negative_similarity():
    mapping = GraphMap()
    submap = Submap(4)
    submap.set_all_semantic_vectors(np.array([[-1., 0.], [-0.5, 0.5]]))
    mapping.add_submap(submap)
    score, submap_id, frame_id = mapping.retrieve_best_semantic_frame(np.array([[1., 0.]]))
    assert score < 0 and submap_id == 4 and frame_id == 1


def test_empty_semantic_search_reports_missing_embeddings():
    with pytest.raises(ValueError, match='No semantic embeddings'):
        GraphMap().retrieve_best_semantic_frame(np.array([[1., 0.]]))


def test_pose_export_deduplicates_overlap(tmp_path):
    mapping = GraphMap()
    for submap_id, frame_ids in ((0, [1., 2.]), (2, [2., 3.])):
        submap = Submap(submap_id)
        submap.frame_ids = frame_ids
        submap.get_all_poses_world = Mock(return_value=np.tile(np.eye(4), (2, 1, 1)))
        mapping.add_submap(submap)
    output = tmp_path / 'poses.txt'
    mapping.write_poses_to_file(output, None)
    poses = np.loadtxt(output)
    np.testing.assert_array_equal(poses[:, 0], [1., 2., 3.])
    assert np.isfinite(poses).all()


def test_scale_ignores_degenerate_points():
    points = np.array([[0., 0., 0.], [1., 2., 3.], [np.nan, 0., 0.]])
    assert estimate_scale_pairwise(points, points * 3)[0] == pytest.approx(3.)
    with pytest.raises(ValueError, match='correspondences'):
        estimate_scale_pairwise(np.zeros((2, 3)), np.zeros((2, 3)))


def test_failed_optical_flow_reinitializes(monkeypatch):
    tracker = FrameTracker()
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    tracker.last_kf = image
    tracker.kf_gray = image[:, :, 0]
    tracker.kf_pts = np.zeros((20, 1, 2), dtype=np.float32)
    monkeypatch.setattr('cv2.calcOpticalFlowPyrLK', lambda *a, **kw: (None, None, None))
    assert tracker.compute_disparity(image, 50)


def test_loop_edge_uses_matched_frame_intrinsics():
    solver = Solver.__new__(Solver)
    solver.map = GraphMap()
    solver.graph = Mock()
    solver.graph.get_homography.return_value = np.eye(4)
    for submap_id in (0, 3):
        submap = Submap(submap_id)
        submap.proj_mats = np.tile(np.eye(4), (3, 1, 1))
        submap.conf_masks = np.full((3, 10, 10), 10.)
        submap.conf_threshold = 1.
        submap.pointclouds = np.ones((3, 10, 10, 3))
        solver.map.add_submap(submap)
    prior = solver.map.get_submap(0)
    current = solver.map.get_submap(3)
    prior.proj_mats[1, :3, :3] *= 2
    current.proj_mats[2, :3, :3] *= 6
    Solver.add_edge(solver, 3, 2, 0, 1, is_loop_closure=True)
    relative = solver.graph.add_between_factor.call_args.args[2]
    # The calibration ratio is 3 and the estimated point scale is 1/3.
    np.testing.assert_allclose(relative, np.eye(4))


@pytest.mark.parametrize('frame_count,selected,expected_sizes', [
    (5, [True] * 5, [3, 3]),
    (4, [True, True, True, False], [3]),
    (4, [True] * 4, [3, 2]),
])
def test_offline_submap_batches(monkeypatch, tmp_path, frame_count, selected, expected_sizes):
    import main as entry
    from types import SimpleNamespace
    for i in range(frame_count):
        (tmp_path / f'frame_{i:04d}.jpg').touch()
    solver = Mock()
    solver.flow_tracker.compute_disparity.side_effect = selected
    solver.run_predictions.side_effect = lambda *a: {'detected_loops': []}
    for timer in (solver.vggt_timer, solver.loop_closure_timer, solver.clip_timer):
        timer.total_time = 1.
    solver.map.get_num_submaps.return_value = len(expected_sizes)
    solver.graph.get_num_loops.return_value = 0
    args = entry.parser.parse_args(['--image_folder', str(tmp_path), '--submap_size', '2', '--device', 'cpu'])
    monkeypatch.setattr(entry.parser, 'parse_args', lambda: args)
    monkeypatch.setattr(entry, 'Solver', lambda **kw: solver)
    monkeypatch.setattr(entry, 'VGGT', Mock())
    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', lambda *a, **kw: {})
    monkeypatch.setattr(entry.cv2, 'imread', lambda *a: np.zeros((16, 16, 3), dtype=np.uint8))
    entry.main()
    assert [len(call.args[0]) for call in solver.run_predictions.call_args_list] == expected_sizes


def test_empty_input_fails_before_loading_models(monkeypatch, tmp_path):
    import main as entry
    args = entry.parser.parse_args(['--image_folder', str(tmp_path)])
    monkeypatch.setattr(entry.parser, 'parse_args', lambda: args)
    model_factory = Mock(side_effect=AssertionError('must not load models'))
    monkeypatch.setattr(entry, 'Solver', model_factory)
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 2
    model_factory.assert_not_called()


def test_realtime_short_capture_flushes_pending_frames(monkeypatch, tmp_path):
    import main_realtime as entry
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    camera = Mock()
    camera.capture.return_value = image
    solver = Mock()
    solver.flow_tracker.compute_disparity.return_value = True
    solver.run_predictions.return_value = {'detected_loops': []}
    solver.map.get_num_submaps.return_value = 1
    args = entry.parser.parse_args(['--keyframe_folder', str(tmp_path), '--device', 'cpu'])
    monkeypatch.setattr(entry.parser, 'parse_args', lambda: args)
    monkeypatch.setattr(entry, 'Solver', lambda **kw: solver)
    monkeypatch.setitem(entry.BACKENDS, 'realsense', lambda: camera)
    monkeypatch.setattr(entry, 'VGGT', Mock())
    monkeypatch.setattr(torch.hub, 'load_state_dict_from_url', lambda *a, **kw: {})
    monkeypatch.setattr(entry.cv2, 'imshow', lambda *a: None)
    monkeypatch.setattr(entry.cv2, 'destroyAllWindows', lambda: None)
    keys = iter([0, ord('q')])
    monkeypatch.setattr(entry.cv2, 'waitKey', lambda *a: next(keys))
    entry.main()
    camera.stop.assert_called_once()
    assert len(solver.run_predictions.call_args.args[0]) == 1
    assert not entry.solver_lock.locked()


def test_vggt_fork_returns_camera_local_points():
    from vggt.utils.geometry import unproject_depth_map_to_point_map
    depth = np.ones((1, 2, 2, 1), dtype=np.float32)
    intrinsics = np.eye(3)[None]
    extrinsics = np.eye(4)[None, :3].copy()
    extrinsics[0, 0, 3] = 5
    points = unproject_depth_map_to_point_map(depth, extrinsics, intrinsics)
    # The SPARK fork intentionally returns camera coordinates despite its docstring.
    # Installing upstream VGGT here would double-transform the map's points.
    np.testing.assert_allclose(points[0, 0, 0], [0, 0, 1])


def test_realtime_worker_reports_errors_and_releases_lock():
    import queue
    import main_realtime as entry
    solver = Mock()
    failure = RuntimeError('inference failed')
    solver.run_predictions.side_effect = failure
    errors = queue.Queue()
    entry.solver_lock.acquire()
    entry.threaded_process_submap(['frame_1.jpg'], solver, None, Mock(), None, None, errors)
    assert errors.get_nowait() is failure
    assert not entry.solver_lock.locked()
    solver.add_points.assert_not_called()


@pytest.mark.parametrize('evo_body', [
    'exit 1',
    'echo "no metric available"',
    'echo "rmse nan"',
])
def test_tum_evaluation_does_not_record_failed_metrics(tmp_path, evo_body):
    import os
    import subprocess
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    tools = tmp_path / 'bin'
    tools.mkdir()
    dataset = tmp_path / 'tum'
    dataset.mkdir()
    python_wrapper = (
        f'#!{sys.executable}\nimport os, sys\n'
        'if sys.argv[1] == "main.py":\n    sys.exit(0)\n'
        f'os.execv({sys.executable!r}, [{sys.executable!r}] + sys.argv[1:])\n'
    )
    for name, source in {
        'python': python_wrapper,
        'evo_ape': '#!/bin/sh\n' + evo_body + '\n',
        'bc': '#!/bin/sh\necho 0\n',
    }.items():
        path = tools / name
        path.write_text(source)
        path.chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'], TUM_DATASET_PATH=str(dataset))
    result = subprocess.run(['bash', str(repo / 'evals/eval_tum.sh'), '32'], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert (tmp_path / 'logs/tum_results_w32.txt').read_text().strip() == 'Run,Dataset,RMSE'
