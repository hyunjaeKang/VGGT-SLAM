"""Thread-safe Viser command queue consumed by the video capture loop."""

import queue

import numpy as np


class VideoControls:
    def __init__(self, server):
        self.commands = queue.Queue()
        self.status = server.gui.add_markdown("Video state: Preparing · decoded=0")
        self.pause = server.gui.add_button("Pause / Resume video")
        self.step = server.gui.add_button("Step video")
        self.stop = server.gui.add_button("Stop video")
        self.pause.on_click(lambda _: self.commands.put(ord("p")))
        self.step.on_click(lambda _: self.commands.put(ord("n")))
        self.stop.on_click(lambda _: self.commands.put(ord("q")))
        self.image = server.gui.add_image(np.zeros((24, 32, 3), dtype=np.uint8), label="Video RGB")

    def drain(self):
        while True:
            try:
                yield self.commands.get_nowait()
            except queue.Empty:
                return

    def update(self, state, decoded, busy=False, image=None):
        self.status.content = f"Video state: {state} · decoded={decoded} · worker={'busy' if busy else 'idle'}"
        self.step.disabled = state != "Paused"
        if image is not None:
            self.image.image = image[..., ::-1].copy()
        if state in {"Stopping", "Completed", "Failed"}:
            self.pause.disabled = self.step.disabled = self.stop.disabled = True
