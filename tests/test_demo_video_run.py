import json

from vggt_slam.demo.video_run import create_video_run, finish_video_run, start_video_run


def test_video_run_manifest_records_input_and_finishes(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video fixture bytes")
    run = create_video_run(video, {"pacing": "offline"}, tmp_path / "runs")
    before = json.loads((run / "manifest.json").read_text())
    assert before["source_mode"] == "video_file_incremental"
    assert before["config"]["video_size_bytes"] == len(b"video fixture bytes")
    assert len(before["config"]["video_sha256"]) == 64
    start_video_run(run, "cpu")
    finish_video_run(run)
    after = json.loads((run / "manifest.json").read_text())
    assert after["status"] == "completed"
    assert after["source_mode"] == "video_file_incremental"


def test_video_run_records_failure(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"bad video")
    run = create_video_run(video, {}, tmp_path / "runs")
    finish_video_run(run, error="decoder error")
    status = json.loads((run / "status.json").read_text())
    assert status["status"] == "failed"
    assert status["error"] == "decoder error"
