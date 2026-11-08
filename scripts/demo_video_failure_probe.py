"""Inject a labelled decoder/worker error into a real loaded video pipeline."""

import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main_realtime as entry
from vggt_slam.demo import recording, video_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--mode", choices=("decoder", "worker"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    observed = {"mode": args.mode, "intentional_failure_injection": True}
    original_create, original_recorder = video_run.create_video_run, recording.Recorder
    original_camera, original_solver = entry.BACKENDS["video_file"], entry.Solver

    def create(video, config, *a, **kw):
        config = {**config, "failure_probe": args.mode, "intentional_failure_injection": True}
        run = original_create(video, config, *a, **kw)
        observed["run"] = str(run)
        return run

    class ProbeRecorder(original_recorder):
        def close(self):
            super().close()
            observed["recorder_closed"] = self._stream.closed

    class ProbeCamera(original_camera):
        def capture(self):
            if args.mode == "decoder" and self._next_frame == 5:
                observed["worker_busy_at_injection"] = entry.solver_lock.locked()
                raise OSError("injected decoder failure after five frames")
            return super().capture()

        def stop(self):
            super().stop()
            observed["camera_released"] = self._capture is None

    def solver(*a, **kw):
        instance = original_solver(*a, **kw)
        if args.mode == "worker":
            def fail(*a, **kw):
                raise RuntimeError("injected worker failure")
            instance.run_predictions = fail
        return instance

    video_run.create_video_run = create
    recording.Recorder = ProbeRecorder
    entry.BACKENDS["video_file"] = ProbeCamera
    entry.Solver = solver
    sys.argv = ["main_realtime.py", "--camera", "video_file", "--video", str(args.video),
                "--headless", "--device", args.device, "--submap_size", "4", "--max_loops", "0",
                "--min_disparity", "0"]
    try:
        entry.main()
    except RuntimeError as exc:
        observed["exception"] = str(exc)
        observed["cause"] = str(exc.__cause__)
    else:
        raise AssertionError("injected failure did not propagate")
    run = Path(observed["run"])
    events_path = run / "events.jsonl"
    size = events_path.stat().st_size
    time.sleep(0.5)
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    observed.update(manifest_status=json.loads((run / "manifest.json").read_text())["status"],
                    last_event=events[-1]["event_type"], solver_lock_released=not entry.solver_lock.locked(),
                    event_file_stable=events_path.stat().st_size == size,
                    recorded_submap_events=sum(event["event_type"] == "submap_created" for event in events),
                    completed_optimizations=sum(event["event_type"] == "optimization_finished" for event in events),
                    run_completed_events=sum(event["event_type"] == "run_completed" for event in events))
    assert observed["manifest_status"] == "failed" and observed["last_event"] == "run_failed"
    assert observed["camera_released"] and observed["recorder_closed"]
    assert observed["solver_lock_released"] and observed["event_file_stable"]
    assert observed["run_completed_events"] == 0
    if args.mode == "decoder":
        assert observed["worker_busy_at_injection"]
    (args.output / "probe.json").write_text(json.dumps(observed, indent=2) + "\n")
    print(json.dumps(observed, indent=2))


if __name__ == "__main__":
    main()
