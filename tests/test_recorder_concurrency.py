import json
from concurrent.futures import ThreadPoolExecutor

from vggt_slam.demo.recording import Recorder


def test_recorder_serializes_event_sequences_across_threads(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"run_id": "threaded"}))
    recorder = Recorder(tmp_path)
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda worker: [recorder.event("test", payload={"worker": worker, "i": i})
                                          for i in range(30)], range(6)))
    finally:
        recorder.close()
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert len(events) == 180
    assert [event["seq"] for event in events] == list(range(180))
