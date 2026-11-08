import json

import numpy as np
from PIL import Image

from vggt_slam.demo.cache import CachedRun
from vggt_slam.demo.prepare import prepare


def test_cached_snapshot_uses_projective_transform_and_no_future_nodes(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    Image.new("RGB", (2, 2)).save(source / "0.png")
    run = prepare({"run_id": "cache", "image_dir": str(source)}, tmp_path / "runs")
    previews = run / "submaps/0"
    previews.mkdir(parents=True)
    np.savez(previews / "preview.npz", points=np.array([[2., 0., 0.], [10., 0., 0.]]),
             colors=np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8), node_ids=np.array([0, 1]))
    (run / "meta0.json").write_text('{"submap_frame_index": 0}')
    (run / "meta1.json").write_text('{"submap_frame_index": 1}')
    events = [{"event_type": "frame_selected", "submap_id": 0, "source_frame_id": "10",
               "asset_paths": {"metadata": "meta0.json"}},
              {"event_type": "frame_selected", "submap_id": 0, "source_frame_id": "11",
               "asset_paths": {"metadata": "meta1.json"}},
              {"event_type": "submap_preview_saved", "submap_id": 0,
               "asset_paths": {"preview": "submaps/0/preview.npz"}},
              {"event_type": "loop_constraint_added", "payload": {"from_node": 0, "to_node": 1}},
              {"event_type": "optimization_finished", "payload": {"step": 1}},
              {"event_type": "object_query_result", "asset_paths": {"result": "object_queries/q/result.json"}}]
    (run / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    snapshot = run / "snapshots/1"
    snapshot.mkdir(parents=True)
    H = np.eye(4)
    H[3, 0] = 0.5
    H1 = np.eye(4)
    H1[0, 3] = 3
    for phase in ("before", "after"):
        np.savez(snapshot / f"{phase}.npz", node_ids=np.array([0, 1]), homographies=np.stack([H, H1]),
                 projection_matrices=np.stack([np.eye(4), np.eye(4)]))
    evaluation = run / "evaluation"
    evaluation.mkdir()
    (evaluation / "trajectory_metrics.json").write_text(json.dumps({"ate_rmse_m": 0.25, "matched_frames": 2}))
    query_dir = run / "object_queries/q"
    query_dir.mkdir(parents=True)
    (query_dir / "result.json").write_text(json.dumps({"query_id": "q", "query": "printer",
        "retrieval_score": 0.8, "submap_id": 0, "frame_index": 0, "frame_image": "frame.png",
        "detections": [{"index": 0, "valid": True, "center": [0, 0, 0], "extent": [1, 1, 1],
                        "rotation": np.eye(3).tolist()}]}))
    cache = CachedRun(run)
    result = cache.render(step=1, frame_index=0, budget=10)
    np.testing.assert_allclose(result["points"], [[1., 0., 0.]])
    assert result["nodes"] == [0]
    assert result["edges"].shape == (0, 2, 3)
    np.testing.assert_array_equal(result["colors"], [[255, 0, 0]])
    result = cache.render(step=1, frame_index=1, budget=10)
    assert result["edges"].shape == (1, 2, 3)
    np.testing.assert_array_equal(result["edge_colors"], [[230, 70, 70]])
    assert cache.evaluations[0]["matched_frames"] == 2
    assert cache.object_queries[0]["query"] == "printer"
    assert cache.object_queries[0]["snapshot"]["step"] == 1
    limited = cache.render(step=1, frame_index=1, budget=1)
    assert len(limited["points"]) == 1
    assert limited["nodes"] == [0, 1]
    assert limited["edges"].shape == (1, 2, 3)
    np.testing.assert_allclose(limited["points"], [[1., 0., 0.]])
    foreground, _ = cache.camera_preview(0, 1)
    np.testing.assert_allclose(foreground, [[1., 0., 0.]])

    overlay = run / 'evidence/sky_test'
    overlay.mkdir(parents=True)
    (overlay / 'index.json').write_text(json.dumps({'status': 'completed', 'source_run': str(run.resolve())}))
    np.savez(overlay / 'submap_0.npz', scores=np.array([255, 0], np.uint8))
    filtered = CachedRun(run)
    early = filtered.render(step=1, frame_index=0, hide_sky=True)
    assert len(early['points']) == 0
    assert early['nodes'] == [0]  # Sky filtering must never remove camera poses.
    assert len(filtered.camera_preview(0, 1, hide_sky=True)[0]) == 0
    later = filtered.render(step=1, frame_index=1, hide_sky=True)
    np.testing.assert_allclose(later['points'], [[13., 0., 0.]])
    assert later['nodes'] == [0, 1]
    assert later['edges'].shape == (1, 2, 3)
    assert len(filtered.render(step=1, hide_sky=False)['points']) == 2
