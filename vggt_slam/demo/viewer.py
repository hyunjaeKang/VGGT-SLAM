"""Read-only Viser browser for cached demo runs."""
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import viser
from PIL import Image
from scipy.linalg import rq
from scipy.spatial.transform import Rotation

from vggt_slam.demo.cache import CachedRun


def _image(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def _frustum(camera):
    P = camera[:3, :]
    M = P[:, :3]
    if np.linalg.det(M) < 0:
        P, M = -P, -M
    K, R = rq(M)
    signs = np.where(np.diag(K) < 0, -1., 1.)
    K, R = K @ np.diag(signs), np.diag(signs) @ R
    center = -np.linalg.solve(M, P[:, 3])
    quat = Rotation.from_matrix(R.T).as_quat()
    return center, quat[[3, 0, 1, 2]]


def serve(run_dir, port=8090):
    run_dir = Path(run_dir).resolve()
    runs = {p.name: p for p in run_dir.parent.iterdir() if (p / "manifest.json").is_file()}
    if run_dir.name not in runs:
        raise ValueError(f"run manifest not found: {run_dir}")
    server = viser.ViserServer(host="127.0.0.1", port=port)
    server.gui.configure_theme(control_layout="collapsible")
    run_select = server.gui.add_dropdown("Run", options=sorted(runs), initial_value=run_dir.name)
    state_text = server.gui.add_markdown("")
    frame = server.gui.add_slider("Frame", min=0, max=1, step=1, initial_value=0)
    play = server.gui.add_button("Play / Pause")
    step = server.gui.add_dropdown("Optimization step", options=["Unavailable"], initial_value="Unavailable")
    phase = server.gui.add_dropdown("Optimization view", options=["after", "before"], initial_value="after")
    colors = server.gui.add_dropdown("Colors", options=["RGB", "Submaps"], initial_value="RGB")
    budget = server.gui.add_slider("Displayed point limit", min=50_000, max=2_000_000, step=50_000, initial_value=300_000)
    fit = server.gui.add_button("Fit map")
    info = server.gui.add_markdown("")
    blank = np.full((80, 140, 3), 220, dtype=np.uint8)
    rgb_gui = server.gui.add_image(blank, label="RGB")
    depth_gui = server.gui.add_image(blank, label="Relative depth")
    loop_select = server.gui.add_dropdown("Loop candidate", options=["Unavailable"], initial_value="Unavailable")
    loop_info = server.gui.add_markdown("")
    loop_query = server.gui.add_image(blank, label="Loop query")
    loop_candidate = server.gui.add_image(blank, label="Loop candidate")
    state = {"run": None, "cloud": None, "lines": None, "frustum": None,
             "center": np.zeros(3), "radius": 1.0, "loading": False, "playing": False}
    stopped = threading.Event()
    render_lock = threading.RLock()

    def fit_all():
        for client in server.get_clients().values():
            client.camera.up_direction = (0, -1, 0)
            client.camera.position = state["center"] + state["radius"] * np.array([0.35, -0.5, -0.65])
            client.camera.look_at = state["center"]

    def _update():
        if state["loading"] or state["run"] is None:
            return
        run = state["run"]
        chosen_step = None if step.value == "Unavailable" else int(step.value)
        result = run.render(step=chosen_step, phase=phase.value,
                            frame_index=int(frame.value) if run.frames else None,
                            budget=int(budget.value), color_mode=colors.value)
        pts, trajectory = result["points"], result["trajectory"]
        for key in ("cloud", "lines", "frustum"):
            if state[key] is not None:
                state[key].remove()
                state[key] = None
        if len(pts):
            sample = pts[np.linspace(0, len(pts) - 1, min(len(pts), 50000), dtype=np.int64)]
            low, high = np.quantile(sample, [0.02, 0.98], axis=0)
            state["center"] = (low + high) / 2
            state["radius"] = max(float(np.linalg.norm(high - low)), 0.1)
            state["cloud"] = server.scene.add_point_cloud("/map", points=pts, colors=result["colors"],
                                                          point_size=state["radius"] / 2000, point_shape="square")
        if len(trajectory) > 1:
            state["lines"] = server.scene.add_line_segments("/trajectory", points=np.stack([trajectory[:-1], trajectory[1:]], axis=1),
                                                           colors=(255, 120, 40), line_width=2)
        current = run.frame(int(frame.value))
        rgb_gui.image = blank
        depth_gui.image = blank
        if current:
            paths = current["asset_paths"]
            for widget, key in ((rgb_gui, "rgb"), (depth_gui, "depth_preview")):
                if key in paths and (run.path / paths[key]).is_file():
                    widget.image = _image(run.path / paths[key])
            meta = json.loads((run.path / paths["metadata"]).read_text())
            node = int(current["submap_id"]) + int(meta["submap_frame_index"])
            if node in result["cameras"]:
                try:
                    pos, quat = _frustum(result["cameras"][node])
                    state["frustum"] = server.scene.add_camera_frustum("/selected_camera", fov=np.radians(60), aspect=1.5,
                                                                        scale=state["radius"] / 35, position=pos, wxyz=quat)
                except (ValueError, np.linalg.LinAlgError):
                    pass
            frame_text = f"frame ID {current['source_frame_id']} · submap {current['submap_id']} · timestamp {meta.get('source_timestamp')} ({meta.get('source_timestamp_type', 'unknown')})"
            if result["step"] is not None and node not in result["cameras"]:
                frame_text += " · frame is not present in the selected snapshot"
        else:
            frame_text = "RGB / depth / timeline unavailable in this cached result."
        total = f"{len(run.cloud):,}" if run.cloud is not None else "unknown"
        info.content = (f"**{result['source']}** · displayed {len(pts):,} points · full PCD {total} points  \n"
                        f"{frame_text} · playback index {int(frame.value) + 1 if current else 0}/{len(run.frames)}  \n"
                        "Coordinates: reconstruction units (metric scale unverified). "
                        "Camera frustum is a decomposition of the projective camera; orientation is illustrative.")
        loops = [event for event in run.events if event["event_type"] == "loop_validation"]
        loop_info.content = (f"Recorded loop validations: **{len(loops)}**, accepted: **{sum(bool(x['payload']['accepted']) for x in loops)}**.  \n"
                             "Loop evidence covers the full run and is not filtered by the selected timeline or snapshot.")
        loop_query.image = blank
        loop_candidate.image = blank
        candidates = [event for event in run.events if event["event_type"] == "loop_candidate"
                      and event["payload"].get("match_id") == loop_select.value]
        if candidates:
            candidate = candidates[0]
            for widget, key in ((loop_query, "query"), (loop_candidate, "candidate")):
                path = candidate.get("asset_paths", {}).get(key)
                if path and (run.path / path).is_file():
                    widget.image = _image(run.path / path)
            decision = next((event["payload"] for event in loops
                             if event["payload"].get("match_id") == loop_select.value), None)
            info_text = f"L2 distance: {candidate['payload']['retrieval_distance']:.4f}"
            if decision:
                info_text += f" · match ratio: {decision['image_match_ratio']} · accepted: {decision['accepted']}"
            loop_info.content += f"  \n{info_text}"

    def update(_=None):
        with render_lock:
            _update()

    def load_run(_=None):
        state["loading"] = True
        try:
            run = CachedRun(runs[run_select.value])
            state["run"] = run
            frame.max = max(1, len(run.frames) - 1)
            frame.disabled = not run.frames
            frame.value = max(0, len(run.frames) - 1)
            options = [str(value) for value in run.steps] or ["Unavailable"]
            step.options = options
            step.value = options[-1]
            step.disabled = not run.steps
            phase.disabled = not run.steps
            loop_options = [event["payload"]["match_id"] for event in run.events
                            if event["event_type"] == "loop_candidate" and "match_id" in event["payload"]]
            loop_options = loop_options or ["Unavailable"]
            loop_select.options = loop_options
            loop_select.value = loop_options[0]
            loop_select.disabled = loop_options == ["Unavailable"]
            play.disabled = not run.frames
            state["playing"] = False
            start, end = run.manifest.get("started_at"), run.manifest.get("finished_at")
            elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() if start and end else None
            elapsed_text = f"{elapsed:.1f} s wall time" if elapsed is not None else "not recorded"
            state_text.content = (f"**{run.manifest.get('source_mode', 'unknown')}** · {run.manifest.get('status', 'unknown')}  \n"
                                  f"Cached result; no model inference. Recorded compute session: {elapsed_text}.  \n"
                                  "ON/OFF runs are independent; playback targets 2 frames/s, not inference speed.")
        finally:
            state["loading"] = False
        update()
        fit_all()

    run_select.on_update(load_run)
    for control in (frame, step, phase, colors, budget, loop_select):
        control.on_update(update)
    fit.on_click(lambda _: fit_all())
    play.on_click(lambda _: state.update(playing=not state["playing"]))

    def playback():
        while not stopped.wait(0.5):
            if state["playing"] and state["run"] is not None and state["run"].frames:
                if int(frame.value) >= len(state["run"].frames) - 1:
                    state["playing"] = False
                else:
                    frame.value = int(frame.value) + 1
                    update()

    thread = threading.Thread(target=playback, daemon=True)
    thread.start()
    server.on_client_connect(lambda _: fit_all())
    load_run()
    print(f"Demo cache viewer: http://127.0.0.1:{server.get_port()}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stopped.set()
        thread.join(timeout=2)
        server.stop()
