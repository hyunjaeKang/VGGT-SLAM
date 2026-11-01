import json
from types import SimpleNamespace

import numpy as np

from vggt_slam.demo.graph_recording import optimize_recorded, record_preview
from vggt_slam.demo.prepare import prepare
from vggt_slam.demo.recording import Recorder
from vggt_slam.graph import PoseGraph
from PIL import Image


def test_snapshot_records_real_graph_before_and_after(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (2, 2)).save(source / "0.png")
    run = prepare({"run_id": "graph", "image_dir": str(source)}, tmp_path / "runs")
    graph = PoseGraph()
    graph.add_homography(0, np.eye(4))
    initial = np.eye(4)
    initial[0, 3] = 2
    graph.add_homography(1, initial)
    graph.add_prior_factor(0, np.eye(4))
    expected = np.eye(4)
    expected[0, 3] = 1
    graph.add_between_factor(0, 1, expected, graph.inner_submap_noise)
    submap = SimpleNamespace(get_all_poses=lambda: [None, None], get_id=lambda: 0,
                             proj_mats=[np.eye(4), np.eye(4)])
    graph_map = SimpleNamespace(ordered_submaps_by_key=lambda: [submap])
    recorder = Recorder(run)
    optimize_recorded(graph, graph_map, recorder, 1)
    recorder.close()
    before = np.load(run / "snapshots/1/before.npz")
    after = np.load(run / "snapshots/1/after.npz")
    np.testing.assert_array_equal(before["node_ids"], after["node_ids"])
    assert not np.allclose(before["homographies"][1], after["homographies"][1])
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    assert events[1]["payload"]["final_error"] < events[1]["payload"]["initial_error"]
    assert events[1]["payload"]["factor_count"] == 2


def test_preview_preserves_local_points_and_node_ids(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (2, 2)).save(source / "0.png")
    run = prepare({"run_id": "preview", "image_dir": str(source)}, tmp_path / "runs")
    (run / "submaps/7").mkdir(parents=True)
    submap = SimpleNamespace(get_id=lambda: 7, pointclouds=[np.array([[[1., 2., 3.], [4., 5., 6.]]])],
                             colors=[np.array([[[1, 2, 3], [4, 5, 6]]])],
                             get_conf_masks_frame=lambda i: np.array([[1., 0.]]),
                             get_conf_threshold=lambda: 0.5)
    recorder = Recorder(run)
    record_preview(submap, recorder)
    recorder.close()
    saved = np.load(run / "submaps/7/preview.npz")
    np.testing.assert_array_equal(saved["points"], [[1, 2, 3]])
    np.testing.assert_array_equal(saved["node_ids"], [7])
    assert str(saved["coordinate_system"]) == "camera_local"
