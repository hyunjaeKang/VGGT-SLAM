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
    events = [{"event_type": "frame_selected", "submap_id": 0, "asset_paths": {"metadata": "meta0.json"}},
              {"event_type": "frame_selected", "submap_id": 0, "asset_paths": {"metadata": "meta1.json"}},
              {"event_type": "submap_preview_saved", "submap_id": 0, "asset_paths": {"preview": "submaps/0/preview.npz"}}]
    (run / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    snapshot = run / "snapshots/1"
    snapshot.mkdir(parents=True)
    H = np.eye(4)
    H[3, 0] = 0.5
    for phase in ("before", "after"):
        np.savez(snapshot / f"{phase}.npz", node_ids=np.array([0]), homographies=H[None],
                 projection_matrices=np.eye(4)[None])
    cache = CachedRun(run)
    result = cache.render(step=1, frame_index=1, budget=10)
    np.testing.assert_allclose(result["points"], [[1., 0., 0.]])
    assert result["nodes"] == [0]
    np.testing.assert_array_equal(result["colors"], [[255, 0, 0]])
