import json

import numpy as np
import pytest

from scripts.demo_validate_video import validate


def fixture_run(root):
    (root / "keyframes").mkdir()
    for name, rows in {
        "video_frames": [{"source_frame_id": i} for i in (10, 11, 12)],
        "video_keyframes": [{"source_frame_id": i} for i in (10, 11, 12)],
        "video_drops": [{"source_frame_id": 11}],
    }.items():
        (root / "keyframes" / f"{name}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    events = []
    for pose_id, source_id, pts in ((1, 10, 3.0), (3, 12, 3.2)):
        name = f"meta_{pose_id}.json"
        (root / name).write_text(json.dumps({"source_path": f"frame_{pose_id:06d}.png", "source_timestamp": pts}))
        events.append({"event_type": "frame_selected", "source_frame_id": source_id,
                       "asset_paths": {"metadata": name}})
    (root / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
    (root / "video_summary.json").write_text(json.dumps({"pacing": "realtime", "decoded_frames": 3,
                                                          "keyframe_backlog_dropped": 1, "submaps": 1}))
    np.savetxt(root / "poses.txt", [[1, 0, 0, 0, 0, 0, 0, 1], [3, 1, 0, 0, 0, 0, 0, 1]])


def test_pts_export_uses_sidecar_not_pose_frame_index(tmp_path):
    fixture_run(tmp_path)
    result, tum = validate(tmp_path)
    assert result["processed_unique"] == 2 and result["dropped"] == 1
    np.testing.assert_allclose(tum[:, 0], [3.0, 3.2])


def test_integrity_rejects_processed_frame_also_marked_dropped(tmp_path):
    fixture_run(tmp_path)
    (tmp_path / "keyframes/video_drops.jsonl").write_text('{"source_frame_id":10}\n')
    with pytest.raises(ValueError, match="partition"):
        validate(tmp_path)


def test_integrity_rejects_nonmonotonic_timestamps(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / "meta_3.json"
    meta = json.loads(path.read_text()); meta["source_timestamp"] = 2.0
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="strictly increasing"):
        validate(tmp_path)


def test_fps_approximation_is_not_exported_as_observed_pts(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / "meta_3.json"
    meta = json.loads(path.read_text())
    meta["source_timestamp_type"] = "video_frame_index_over_fps_seconds"
    path.write_text(json.dumps(meta))
    result, _ = validate(tmp_path)
    assert result["timestamps_approximate"]
    assert result["estimated_trajectory_file"] == "estimated_approximate.tum"
