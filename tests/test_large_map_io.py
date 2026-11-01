from unittest.mock import Mock

import numpy as np
import open3d as o3d
import pytest
import torch

from vggt_slam.map import GraphMap
from vggt_slam.pcd_io import read_cloud, unpack_rgb, write_cloud_chunks
from vggt_slam.submap import Submap


def test_streamed_pcd_is_readable_by_open3d_and_memory_map(tmp_path):
    path = tmp_path / 'map.pcd'
    first = np.array([[1., 2., 3.], [np.nan, 0, 0]])
    second = np.array([[4., 5., 6.]])
    count = write_cloud_chunks(path, [(first, [[255, 10, 30], [0, 0, 0]]), (second, [[0, 100, 200]])])
    assert count == 2
    cloud = read_cloud(path)
    assert isinstance(cloud, np.memmap)
    np.testing.assert_allclose(cloud['xyz'], [[1, 2, 3], [4, 5, 6]])
    np.testing.assert_array_equal(unpack_rgb(cloud['rgb']), [[255, 10, 30], [0, 100, 200]])
    external = o3d.io.read_point_cloud(str(path))
    np.testing.assert_allclose(external.points, cloud['xyz'])
    np.testing.assert_allclose(np.asarray(external.colors) * 255, unpack_rgb(cloud['rgb']))


def test_stream_failure_preserves_previous_file(tmp_path):
    path = tmp_path / 'map.pcd'
    path.write_bytes(b'previous result')
    def chunks():
        yield np.ones((2, 3)), np.zeros((2, 3), dtype=np.uint8)
        raise RuntimeError('interrupted export')
    with pytest.raises(RuntimeError, match='interrupted'):
        write_cloud_chunks(path, chunks())
    assert path.read_bytes() == b'previous result'
    assert not list(tmp_path.glob('*.tmp'))


def test_frame_stream_export_matches_projective_submap_transform(tmp_path):
    mapping = GraphMap()
    submap = Submap(0)
    submap.pointclouds = np.arange(24, dtype=float).reshape(2, 2, 2, 3) / 10
    submap.colors = np.arange(24, dtype=np.uint8).reshape(2, 2, 2, 3)
    submap.conf_masks = np.array([[[0., 1.], [1., 1.]], [[1., 0.], [1., 1.]]])
    submap.conf = submap.conf_masks.copy()
    submap.conf_threshold = 0.5
    submap.poses = np.tile(np.eye(4), (2, 1, 1))
    mapping.add_submap(submap)
    homography = np.eye(4)
    homography[:3, 3] = [1, 2, 3]
    homography[3, 0] = 0.1
    graph = Mock()
    graph.get_homography.return_value = homography
    expected = submap.get_points_in_world_frame(graph)
    colors = submap.get_points_colors()
    output = tmp_path / 'map.pcd'
    mapping.write_points_to_file(graph, output)
    cloud = read_cloud(output)
    np.testing.assert_allclose(cloud['xyz'], expected, rtol=1e-6)
    np.testing.assert_array_equal(unpack_rgb(cloud['rgb']), colors)


def test_vectorized_retrieval_matches_brute_force_and_exclusions():
    mapping = GraphMap()
    generator = torch.Generator().manual_seed(3)
    query = torch.randn(8, generator=generator)
    expected = []
    for submap_id in (0, 20, 40, 60):
        submap = Submap(submap_id)
        vectors = torch.randn((17, 8), generator=generator)
        submap.set_all_retrieval_vectors(vectors)
        if submap_id == 40:
            submap.set_lc_status(True)
        mapping.add_submap(submap)
        if submap_id in (0, 20):
            expected.extend((torch.linalg.norm(v-query).item(), submap_id, i) for i, v in enumerate(vectors))
    result = mapping.retrieve_best_score_frame(query, current_submap_id=60, ignore_last_submap=True)
    best = min(expected)
    assert result[0] == pytest.approx(best[0], abs=1e-6)
    assert result[1:] == best[1:]
