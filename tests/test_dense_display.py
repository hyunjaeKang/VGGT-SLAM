import numpy as np

from vggt_slam.demo.camera_view import display_resolution, raster_camera
from vggt_slam.demo.dense_display import depth_display_points


def test_dense_unprojection_full_projective_camera_and_sky_alignment():
    projection = np.array([[2., .2, .3, 1], [0, 3, .4, -1], [0, 0, 1, .2], [.01, 0, 0, 1.]])
    depth = np.full((4, 5), 2.)
    confidence = np.ones((4, 5))
    valid = np.ones((4, 5), bool)
    valid[0, 0] = False
    confidence[1, 1] = 0
    rgb = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
    sky = np.zeros((4, 5), np.uint8)
    sky[0, 0] = 255
    pts, colors, scores = depth_display_points(depth, confidence, valid, projection, .5, rgb, 100, sky)
    q = np.column_stack([pts, np.ones(len(pts))]) @ projection.T
    uv = np.rint(q[:, :2] / q[:, 2:3]).astype(int)
    assert len(pts) == 18
    assert not any((uv == [0, 0]).all(axis=1))
    assert not any((uv == [1, 1]).all(axis=1))
    np.testing.assert_array_equal(colors, rgb[uv[:, 1], uv[:, 0]])
    np.testing.assert_array_equal(scores, np.where((uv[:, 0] <= 2) & (uv[:, 1] <= 2), 255, 0))


def test_adaptive_resolution_retains_aspect_and_caps_retina_cost():
    assert display_resolution((140, 518), (1000, 700, 1)) == (270, 1000)
    h, w = display_resolution((140, 518), (4000, 3000, 3))
    assert w <= 1920 and h <= 1080
    assert abs(w / h - 518 / 140) < .01


def test_adaptive_raster_depth_order_and_antialias_dimensions():
    pts = np.array([[5., 5., 1.], [10., 10., 2.]])
    colors = np.array([[255, 0, 0], [0, 255, 0]], np.uint8)
    image, stats = raster_camera(pts, colors, np.eye(4), (10, 10), point_scale=1,
                                 output_shape=(80, 80), antialias=1.5)
    assert image.shape == (80, 80, 3)
    assert image[40, 40, 0] > 200 and image[40, 40, 1] < 30
    assert stats['output_shape_hw'] == [80, 80]
    assert stats['antialias'] == 1.5


def test_dense_cache_integration_uses_snapshot_transform_and_timeline(tmp_path):
    import json
    from PIL import Image
    from vggt_slam.demo.cache import CachedRun
    from vggt_slam.demo.dense_display import prepare_dense_display
    (tmp_path / 'manifest.json').write_text(json.dumps({'execution_args': {'conf_threshold': 0}}))
    events = []
    for index in range(2):
        folder = tmp_path / 'submaps/0/frames' / str(index)
        folder.mkdir(parents=True)
        Image.fromarray(np.full((3, 4, 3), 100 + index, np.uint8)).save(folder / 'rgb.png')
        (folder / 'meta.json').write_text(json.dumps({'submap_frame_index': index}))
        np.savez(folder / 'depth.npz', depth=np.full((3, 4), 2.), valid=np.ones((3, 4), bool),
                 confidence=np.arange(12).reshape(3, 4) + 1.)
        events.append({'event_type': 'frame_selected', 'submap_id': 0, 'source_frame_id': str(index),
                       'asset_paths': {k: str((folder / v).relative_to(tmp_path))
                                       for k, v in {'rgb': 'rgb.png', 'depth': 'depth.npz', 'metadata': 'meta.json'}.items()}})
    np.savez(tmp_path / 'submaps/0/preview.npz', points=np.zeros((2, 3)), colors=np.zeros((2, 3), np.uint8), node_ids=[0, 1])
    events.append({'event_type': 'submap_preview_saved', 'submap_id': 0, 'asset_paths': {'preview': 'submaps/0/preview.npz'}})
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    snap = tmp_path / 'snapshots/1'
    snap.mkdir(parents=True)
    before = np.eye(4)
    after = np.eye(4)
    after[0, 3] = 10
    for name, matrix in [('before', before), ('after', after)]:
        np.savez(snap / (name + '.npz'), node_ids=[0, 1], homographies=[matrix, matrix],
                 projection_matrices=[np.linalg.inv(matrix), np.linalg.inv(matrix)])
    prepare_dense_display(tmp_path, tmp_path / 'evidence/dense_test')
    run = CachedRun(tmp_path)
    assert run.dense_index is not None
    a = run.render(step=1, phase='before', frame_index=0, budget=100)['points']
    b = run.render(step=1, phase='after', frame_index=0, budget=100)['points']
    assert len(a) == 11
    np.testing.assert_allclose(b - a, np.tile([10, 0, 0], (11, 1)))
    assert len(run.render(step=1, frame_index=1, budget=100)['points']) == 22
    assert CachedRun(tmp_path, use_dense=False).dense_index is None
