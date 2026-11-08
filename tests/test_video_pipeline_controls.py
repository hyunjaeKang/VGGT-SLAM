"""Exercise video orchestration with a slow worker; no model inference."""

import json
import time
import threading
from unittest.mock import Mock

import numpy as np
import pytest
import torch


@pytest.mark.parametrize("display", [False, True])
def test_video_waits_without_drops_and_pause_step_stop(monkeypatch, tmp_path, display):
    import main_realtime as entry

    class Camera:
        _fps = 10.0
        source_timestamp = 0.0
        source_frame_id = -1
        stopped = False

        def start(self):
            pass

        def capture(self):
            self.source_frame_id += 1
            if self.source_frame_id == 12:
                raise entry.EndOfStream("fixture")
            self.source_timestamp = self.source_frame_id / self._fps
            return np.zeros((24, 32, 3), dtype=np.uint8)

        def stop(self):
            self.stopped = True

    camera = Camera()
    solver = Mock()
    solver.flow_tracker.compute_disparity.return_value = True
    args = entry.parser.parse_args(["--camera", "video_file", "--video", "fixture.mp4",
                                    "--device", "cpu", "--submap_size", "2"] + ([] if display else ["--headless"]))
    args.video_run_dir = tmp_path
    args.keyframe_folder = str(tmp_path / "keyframes")
    args.demo_recorder = Mock()
    (tmp_path / "manifest.json").write_text(json.dumps({"config": {"video_sha256": "fixture"}}))
    batches = []

    def slow_worker(names, solver, model, args, clip, preprocess, errors):
        try:
            time.sleep(0.02)
            batches.append(names)
            args.submap_metrics.append({"elapsed_seconds": 0.02})
        finally:
            entry.solver_lock.release()

    monkeypatch.setattr(entry, "Solver", lambda **kw: solver)
    monkeypatch.setitem(entry.BACKENDS, "video_file", lambda *a, **kw: camera)
    monkeypatch.setattr(entry, "VGGT", Mock())
    monkeypatch.setattr(torch.hub, "load_state_dict_from_url", lambda *a, **kw: {})
    monkeypatch.setattr(entry, "threaded_process_submap", slow_worker)
    shown = Mock()
    monkeypatch.setattr(entry.cv2, "imshow", shown)
    monkeypatch.setattr(entry.cv2, "destroyAllWindows", Mock())
    keys = iter([0, ord("p"), ord("n"), 0, 0, ord("q")])
    monkeypatch.setattr(entry.cv2, "waitKey", lambda *a: next(keys))
    entry.run_camera_pipeline(args)
    summary = json.loads((tmp_path / "video_summary.json").read_text())
    assert camera.stopped and not entry.solver_lock.locked()
    assert summary["keyframe_backlog_dropped"] == 0
    if display:
        assert summary["pause_toggle_events"] == 1
        assert summary["single_step_frames"] == summary["decoded_frames"] == 1
        assert len(batches) == 1 and len(batches[0]) == 1
    else:
        shown.assert_not_called()
        assert summary["decoded_frames"] == 12
        assert len(set(name for batch in batches for name in batch)) == 12
        assert len(batches) > 1


def test_video_warmup_clock_failure_releases_opened_camera(monkeypatch, tmp_path):
    import main_realtime as entry

    camera = Mock()
    camera.capture.side_effect = ValueError("realtime pacing requires increasing PTS or finite positive FPS")
    args = entry.parser.parse_args(["--camera", "video_file", "--video", "fixture.mp4",
                                    "--headless", "--device", "cpu", "--keyframe_folder", str(tmp_path)])
    args.video_run_dir = tmp_path
    args.demo_recorder = Mock()
    monkeypatch.setattr(entry, "Solver", Mock())
    monkeypatch.setattr(entry, "VGGT", Mock())
    monkeypatch.setattr(torch.hub, "load_state_dict_from_url", lambda *a, **kw: {})
    monkeypatch.setitem(entry.BACKENDS, "video_file", lambda *a, **kw: camera)
    with pytest.raises(RuntimeError, match="video input failed"):
        entry.run_camera_pipeline(args)
    camera.stop.assert_called_once()


def test_camera_release_error_still_waits_for_worker(monkeypatch, tmp_path):
    import main_realtime as entry

    image = np.zeros((24, 32, 3), dtype=np.uint8)
    camera = Mock()
    camera.source_frame_id = 0
    camera.source_timestamp = 0.0
    camera.source_timestamp_type = "video_pts_seconds"
    camera.raw_source_timestamp = 0.0
    camera.source_timestamp_reason = None
    camera.capture.side_effect = [image, image, image, entry.EndOfStream("end")]
    camera.stop.side_effect = RuntimeError("injected release failure")
    solver = Mock()
    solver.flow_tracker.compute_disparity.return_value = True
    args = entry.parser.parse_args(["--camera", "video_file", "--video", "fixture.mp4", "--headless",
                                    "--device", "cpu", "--submap_size", "2", "--keyframe_folder", str(tmp_path)])
    args.video_run_dir, args.demo_recorder = tmp_path, Mock()
    worker_done = threading.Event()

    def worker(*args):
        try:
            time.sleep(.1)
            worker_done.set()
        finally:
            entry.solver_lock.release()

    monkeypatch.setattr(entry, "Solver", lambda **kw: solver)
    monkeypatch.setattr(entry, "VGGT", Mock())
    monkeypatch.setattr(entry, "threaded_process_submap", worker)
    monkeypatch.setattr(torch.hub, "load_state_dict_from_url", lambda *a, **kw: {})
    monkeypatch.setitem(entry.BACKENDS, "video_file", lambda *a, **kw: camera)
    with pytest.raises(RuntimeError, match="release failure"):
        entry.run_camera_pipeline(args)
    assert worker_done.is_set() and not entry.solver_lock.locked()
