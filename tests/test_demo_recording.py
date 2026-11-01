import json

import numpy as np
import pytest
from PIL import Image

from vggt_slam.demo.prepare import prepare
from vggt_slam.demo.recording import Recorder


def test_record_submap_preserves_pixel_mapping_and_overlap(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (2, 2)).save(source / "1.png")
    run = prepare({"run_id": "record", "image_dir": str(source)}, tmp_path / "runs")
    recorder = Recorder(run)
    predictions = {"images": np.ones((2, 3, 2, 2)), "depth": np.array([[[[1], [2]], [[3], [np.nan]]]] * 2),
                   "depth_conf": np.ones((2, 2, 2)), "intrinsic": np.tile(np.eye(3), (2, 1, 1))}
    recorder.record_submap(7, ["frame1", "frame2"], predictions, overlap_count=1)
    recorder.close()
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    assert [event["seq"] for event in events] == [0, 1, 2]
    assert events[1]["payload"]["overlap"] and not events[2]["payload"]["overlap"]
    saved = np.load(run / events[1]["asset_paths"]["depth"])
    assert saved["depth"][0, 1] == 2 and not saved["valid"][1, 1]
    assert np.asarray(Image.open(run / events[1]["asset_paths"]["rgb"])).shape == (2, 2, 3)
    with pytest.raises(FileExistsError):
        Recorder(run)


def test_loop_candidate_saves_images_and_link_id(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (2, 2), "red").save(source / "1.png")
    Image.new("RGB", (2, 2), "blue").save(source / "2.png")
    run = prepare({"run_id": "loop", "image_dir": str(source)}, tmp_path / "runs")
    recorder = Recorder(run)
    recorder.loop_candidate("7_0_1_2", source / "1.png", source / "2.png", 7,
                            {"retrieval_distance": 0.2})
    recorder.close()
    event = json.loads((run / "events.jsonl").read_text())
    assert event["payload"]["match_id"] == "7_0_1_2"
    assert Image.open(run / event["asset_paths"]["query"]).getpixel((0, 0)) == (255, 0, 0)
    assert Image.open(run / event["asset_paths"]["candidate"]).getpixel((0, 0)) == (0, 0, 255)
