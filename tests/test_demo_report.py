import json

from scripts.demo_report import collect, render


def test_demo_report_summarizes_manifest_events_assets_and_metrics(tmp_path):
    run = tmp_path / "run-a"
    run.mkdir()
    (run / "manifest.json").write_text(json.dumps({
        "run_id": "run-a", "source_mode": "video_file_incremental", "status": "completed",
        "assets": {"point_cloud": "points.pcd"}}))
    (run / "events.jsonl").write_text("\n".join([
        json.dumps({"event_type": "frame_selected"}),
        json.dumps({"event_type": "submap_created"}),
        json.dumps({"event_type": "loop_candidate"}),
        json.dumps({"event_type": "loop_validation", "payload": {"accepted": True}}), ""]))
    (run / "points.pcd").write_bytes(b"# .PCD\nPOINTS 123\n")
    (run / "video_summary.json").write_text(json.dumps({"decoded_frames": 8, "selected_keyframes": 4,
                                                         "pacing": "offline"}))
    evidence = run / "evidence"
    evidence.mkdir()
    (evidence / "proof.json").write_text("{}")

    rows = collect(tmp_path)
    assert rows[0]["frames"] == 1
    assert rows[0]["submaps"] == 1
    assert rows[0]["loop_accepted"] == 1
    assert rows[0]["point_count"] == 123
    report = render(rows)
    assert "run-a" in report
    assert "8 decoded" in report
    assert "proof.json" in report
