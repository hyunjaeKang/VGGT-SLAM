import json

import numpy as np
from PIL import Image
import pytest

from vggt_slam.demo.object_query import boxes_from_masks, save_query_evidence
from vggt_slam.slam_utils import compute_obb_from_points
from vggt_slam.submap import Submap


def test_obb_is_finite_right_handed_and_has_positive_extents():
    points = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
    points[1, 1] = np.nan
    center, extent, rotation = compute_obb_from_points(points)
    assert np.isfinite(center).all()
    assert np.isfinite(extent).all() and np.all(extent > 0)
    assert np.linalg.det(rotation) > 0.999
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-7)


def test_submap_mask_resizes_and_filters_confidence_and_nonfinite_points():
    submap = Submap.__new__(Submap)
    points = np.zeros((4, 4, 3), dtype=float)
    points[..., 0] = np.arange(16).reshape(4, 4)
    points[0, 1] = np.nan
    confidence = np.ones((4, 4), dtype=bool)
    confidence[0, 0] = False
    submap.get_points_list_in_world_frame = lambda graph: ([points], ["frame"], [confidence])

    selected = submap.get_points_in_mask(0, np.ones((2, 2), dtype=bool), graph=None)
    assert selected.shape == (14, 3)
    assert np.isfinite(selected).all()


class PointSubmap:
    def __init__(self, points):
        self.points = points
        self.mask = None

    def get_points_in_mask(self, frame_index, mask, graph):
        self.mask = mask
        return self.points


def test_mask_boxes_skip_insufficient_points_and_keep_box_evidence(tmp_path):
    points = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
    submap = PointSubmap(points)
    mask = np.ones((4, 5), dtype=bool)
    detections = boxes_from_masks(submap, 3, graph=None, masks=[mask], scores=[0.91])
    assert detections[0]["valid"]
    assert detections[0]["point_count"] == 8
    assert detections[0]["score"] == 0.91
    assert submap.mask.shape == mask.shape
    np.testing.assert_allclose(np.linalg.det(detections[0]["rotation"]), 1.0, atol=1e-7)

    too_small = boxes_from_masks(PointSubmap(points[:3]), 0, None, [mask])[0]
    assert not too_small["valid"]
    assert "need 8" in too_small["reason"]

    run = tmp_path / "run"
    recorder = type("Recorder", (), {"run_dir": run,
                                     "event": lambda self, kind, **kwargs: setattr(self, "last", (kind, kwargs))})()
    image = Image.new("RGB", (5, 4), (10, 20, 30))
    result_path = save_query_evidence("printer", 0.7, 4, 3, image, detections,
                                      run_dir=run, recorder=recorder)
    saved = json.loads(result_path.read_text())
    assert saved["query"] == "printer"
    assert saved["detections"][0]["mask_path"] == "mask_00.png"
    assert (result_path.parent / saved["detections"][0]["mask_path"]).is_file()
    assert recorder.last[0] == "object_query_result"


@pytest.mark.parametrize("rank", [0, 1, 2])
def test_query_rejects_degenerate_support_and_retains_mask(tmp_path, rank):
    points = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
    points[:, rank:] = 0
    mask = np.ones((4, 5), dtype=bool)
    detection = boxes_from_masks(PointSubmap(points), 0, None, [mask])[0]
    assert not detection["valid"] and detection["geometry_rank"] == rank
    assert "degenerate" in detection["reason"]
    path = save_query_evidence("object", .5, 0, 0, Image.new("RGB", (5, 4)), [detection], run_dir=tmp_path)
    saved = json.loads(path.read_text())
    assert (path.parent / saved["detections"][0]["mask_path"]).is_file()


def test_query_without_optional_scores_succeeds():
    points = np.array([[x, y, z] for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=float)
    detection = boxes_from_masks(PointSubmap(points), 0, None, [np.ones((3, 3), bool)])[0]
    assert detection["valid"] and detection["score"] is None
