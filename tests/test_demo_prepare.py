import json

import pytest
from PIL import Image

from vggt_slam.demo.prepare import prepare


def test_selection_and_collision(tmp_path):
    source = tmp_path / "images with spaces"
    source.mkdir()
    for frame_id in (2, 5, 10):
        Image.new("RGB", (4, 4)).save(source / f"{frame_id}.png")
    config = {"run_id": "first", "image_dir": str(source)}
    run = prepare(config, tmp_path / "runs")
    selection = json.loads((run / "selection.json").read_text())
    assert [f["frame_id"] for f in selection["frames"]] == [2, 5, 10]
    assert selection["missing_ids"] == [3, 4, 6, 7, 8, 9]
    assert selection["frames"][0]["timestamp"] is None
    with pytest.raises(FileExistsError):
        prepare(config, tmp_path / "runs")


def test_corrupt_and_duplicate_inputs_rejected(tmp_path):
    (tmp_path / "1.png").write_bytes(b"bad")
    config = {"run_id": "bad", "image_dir": str(tmp_path)}
    with pytest.raises(ValueError, match="invalid image"):
        prepare(config, tmp_path / "runs")
    Image.new("RGB", (4, 4)).save(tmp_path / "1.png")
    Image.new("RGB", (4, 4)).save(tmp_path / "01.jpg")
    config["run_id"] = "duplicate"
    with pytest.raises(ValueError, match="duplicate frame ID"):
        prepare(config, tmp_path / "runs")


def test_cached_registration_references_existing_files(tmp_path):
    cloud = tmp_path / "large cloud.pcd"
    poses = tmp_path / "poses.txt"
    cloud.write_bytes(b"original cloud")
    poses.write_text("0 0 0 0 0 0 0 1\n")
    config = {"run_id": "cached", "source_mode": "cached_playback", "pose_first_column": "frame_id",
              "existing_assets": {"point_cloud": str(cloud), "poses": str(poses)}}
    run = prepare(config, tmp_path / "runs")
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["assets"]["point_cloud"]["path"] == str(cloud.resolve())
    assert manifest["assets"]["point_cloud"]["external_read_only"]
    assert cloud.read_bytes() == b"original cloud"
    assert not list(run.glob("*.pcd"))
    assert manifest["source_mode"] == "cached_playback"
    assert manifest["coverage"]["F1"]["status"] == "NOT_RUN"
    with pytest.raises(FileExistsError):
        prepare(config, tmp_path / "runs")
    config["run_id"] = "missing"
    config["existing_assets"]["poses"] = str(tmp_path / "missing.txt")
    with pytest.raises(FileNotFoundError):
        prepare(config, tmp_path / "runs")
    failure = json.loads((tmp_path / "runs" / "missing" / "status.json").read_text())
    assert failure["status"] == "failed"
    assert failure["phase"] == "prepare"


def test_run_lifecycle(tmp_path):
    from vggt_slam.demo.status import transition

    source = tmp_path / "images"
    source.mkdir()
    Image.new("RGB", (4, 4)).save(source / "1.png")
    run = prepare({"run_id": "life", "image_dir": str(source)}, tmp_path / "runs")
    with pytest.raises(ValueError, match="requires device"):
        transition(run, "running")
    transition(run, "running", device="cpu", models={"vggt": {"checkpoint": "test.pt"}})
    transition(run, "completed")
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["status"] == "completed"
    assert manifest["environment"]["models"]["vggt"]["checkpoint"] == "test.pt"
    assert manifest["started_at"] <= manifest["finished_at"]
    with pytest.raises(ValueError, match="invalid run transition"):
        transition(run, "running", device="cpu", models={"vggt": "test"})


def test_timestamp_file_uses_original_frame_id(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    for i in (1, 3):
        Image.new("RGB", (4, 4)).save(source / f"{i}.png")
    timestamps = tmp_path / "timestamps.json"
    timestamps.write_text(json.dumps([10.0, 10.1, 10.2, 10.3]))
    config = {"run_id": "times", "image_dir": str(source), "timestamp_file": str(timestamps),
              "timestamp_type": "unix_seconds"}
    run = prepare(config, tmp_path / "runs")
    frames = json.loads((run / "selection.json").read_text())["frames"]
    assert [f["timestamp"] for f in frames] == [10.1, 10.3]
    timestamps.write_text(json.dumps([10, 9, 11, 12]))
    config["run_id"] = "bad_times"
    with pytest.raises(ValueError, match="strictly increasing"):
        prepare(config, tmp_path / "runs")


def test_explicit_selection_rejects_missing_or_unordered_ids(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    for i in range(4):
        Image.new("RGB", (4, 4)).save(source / f"{i}.png")
    selected = tmp_path / "ids.json"
    selected.write_text("[0, 2, 3]")
    config = {"run_id": "explicit", "image_dir": str(source), "frame_ids_file": str(selected)}
    run = prepare(config, tmp_path / "runs")
    selection = json.loads((run / "selection.json").read_text())
    assert [frame["frame_id"] for frame in selection["frames"]] == [0, 2, 3]
    assert selection["selection_policy"] == "explicit_frame_ids"
    selected.write_text("[0, 7]")
    config["run_id"] = "missing_selected"
    with pytest.raises(ValueError, match="missing or outside"):
        prepare(config, tmp_path / "runs")
