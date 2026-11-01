import json
import sys

import numpy as np
import pytest
from PIL import Image

from vggt_slam.demo.prepare import prepare


@pytest.mark.parametrize("fail", [False, True])
def test_demo_entrypoint_records_lifecycle(tmp_path, monkeypatch, fail):
    import main

    source = tmp_path / "images"
    source.mkdir()
    Image.new("RGB", (2, 2)).save(source / "1.png")
    run = prepare({"run_id": "entry", "image_dir": str(source)}, tmp_path / "runs")
    monkeypatch.setattr(sys, "argv", ["main.py", "--headless", "--device", "cpu", "--demo_run", str(run)])

    def fake_pipeline(args, recorder):
        assert args.log_path == str(run / "poses.txt")
        recorder.record_submap(0, [{"frame_id": 1, "timestamp": None}],
                               {"images": np.ones((1, 3, 2, 2)), "depth": np.ones((1, 2, 2, 1)),
                                "depth_conf": np.ones((1, 2, 2)), "intrinsic": np.eye(3)[None]})
        if fail:
            raise RuntimeError("synthetic failure")

    monkeypatch.setattr(main, "run_pipeline", fake_pipeline)
    if fail:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            main.main()
    else:
        main.main()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["status"] == ("failed" if fail else "completed")
    assert manifest["environment"]["device"] == "cpu"
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    assert events[-1]["event_type"] == ("run_failed" if fail else "run_completed")
    assert events[1]["source_frame_id"] == "1"
