"""Camera backends for real-time SLAM."""

from abc import ABC, abstractmethod
import time
from typing import Optional

import numpy as np


class Camera(ABC):
    """Abstract camera that produces BGR uint8 frames."""

    @abstractmethod
    def start(self) -> None:
        """Open the device and begin streaming."""
        ...

    @abstractmethod
    def capture(self) -> Optional[np.ndarray]:
        """Return a BGR uint8 (H, W, 3) frame, or None if unavailable."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Release the device."""
        ...


class RealSenseCamera(Camera):
    """Intel RealSense color stream via pyrealsense2."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        self._width = width
        self._height = height
        self._fps = fps
        self._pipeline = None

    def start(self) -> None:
        import pyrealsense2 as rs

        self._pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, self._width, self._height, rs.format.bgr8, self._fps)
        self._pipeline.start(config)

    def capture(self) -> Optional[np.ndarray]:
        frames = self._pipeline.wait_for_frames()
        color = frames.get_color_frame()
        return np.asanyarray(color.get_data()) if color else None

    def stop(self) -> None:
        if self._pipeline is not None:
            self._pipeline.stop()
            self._pipeline = None


class EndOfStream(EOFError):
    """Raised when a finite file source has been consumed."""


class VideoFileCamera(Camera):
    """BGR frame source backed by OpenCV, with explicit EOF and optional pacing."""

    def __init__(self, path: str, *, start_frame: int = 0, end_frame: Optional[int] = None,
                 pacing: str = "offline", read_timeout: float = 10.0):
        if start_frame < 0 or (end_frame is not None and end_frame < start_frame):
            raise ValueError("invalid video frame range")
        if pacing not in {"offline", "realtime"}:
            raise ValueError("pacing must be offline or realtime")
        self.path = str(path)
        self.start_frame = int(start_frame)
        self.end_frame = None if end_frame is None else int(end_frame)
        self.pacing = pacing
        self.read_timeout = float(read_timeout)
        self._capture = None
        self._fps = 0.0
        self._next_frame = self.start_frame
        self._started_at = None
        self._timestamp = None
        self._timestamp_type = "unavailable"
        self._timestamp_reason = None
        self._raw_timestamp = None
        self._last_timestamp = None
        self._pacing_origin_timestamp = None
        self._rebase_on_next_capture = False
        self._eof = False

    @property
    def eof(self):
        return self._eof

    @property
    def source_frame_id(self):
        return self._next_frame - 1

    @property
    def source_timestamp(self):
        return self._timestamp

    @property
    def source_timestamp_type(self):
        return self._timestamp_type

    @property
    def source_timestamp_reason(self):
        return self._timestamp_reason

    @property
    def raw_source_timestamp(self):
        return self._raw_timestamp

    def start(self) -> None:
        import cv2

        self._capture = cv2.VideoCapture(self.path)
        if not self._capture.isOpened():
            self._capture.release()
            self._capture = None
            raise OSError(f"cannot open video file: {self.path}")
        reported_fps = float(self._capture.get(cv2.CAP_PROP_FPS))
        self._fps = reported_fps if np.isfinite(reported_fps) and reported_fps > 0 else 0.0
        # AVFoundation reports MOV display rotation but often leaves AUTO off.
        # Disable automatic rotation when supported, then apply it once ourselves.
        rotation = float(self._capture.get(cv2.CAP_PROP_ORIENTATION_META))
        self._orientation_degrees = int(round(rotation)) % 360 if np.isfinite(rotation) else 0
        if self._orientation_degrees not in (0, 90, 180, 270):
            self._orientation_degrees = 0
        self._capture.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
        self._rotate_manually = self._capture.get(cv2.CAP_PROP_ORIENTATION_AUTO) != 1
        self._capture.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)
        self._next_frame = self.start_frame
        self._started_at = time.monotonic()
        self._eof = False
        self._timestamp = self._last_timestamp = self._pacing_origin_timestamp = None
        self._timestamp_type = "unavailable"
        self._raw_timestamp = self._timestamp_reason = None
        self._rebase_on_next_capture = False

    def capture(self) -> Optional[np.ndarray]:
        if self._capture is None:
            raise RuntimeError("video source is not started")
        if self._eof:
            raise EndOfStream(self.path)
        if self.end_frame is not None and self._next_frame > self.end_frame:
            self._eof = True
            raise EndOfStream(self.path)
        ok, frame = self._capture.read()
        if not ok or frame is None:
            self._eof = True
            raise EndOfStream(self.path)
        import cv2

        if self._rotate_manually and self._orientation_degrees:
            frame = cv2.rotate(frame, {90: cv2.ROTATE_90_CLOCKWISE,
                                     180: cv2.ROTATE_180,
                                     270: cv2.ROTATE_90_COUNTERCLOCKWISE}[self._orientation_degrees])
        timestamp = float(self._capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
        self._raw_timestamp = timestamp if np.isfinite(timestamp) else None
        valid_pts = (np.isfinite(timestamp) and timestamp >= 0
                     and (self._last_timestamp is None or timestamp > self._last_timestamp))
        self._timestamp_reason = None
        if valid_pts:
            self._timestamp = timestamp
            self._timestamp_type = "video_pts_seconds"
        else:
            self._timestamp_reason = "PTS missing, negative, repeated or non-increasing"
            if self._fps > 0:
                self._timestamp = self._next_frame / self._fps
                self._timestamp_type = "video_frame_index_over_fps_seconds"
                if self._last_timestamp is not None and self._timestamp <= self._last_timestamp:
                    self._timestamp = self._last_timestamp + 1.0 / self._fps
                    self._timestamp_type = "video_fps_extrapolated_seconds"
            else:
                self._timestamp = None
                self._timestamp_type = "unavailable"
                self._timestamp_reason += "; no finite positive FPS for approximation"
        if self._timestamp is not None:
            self._last_timestamp = self._timestamp
        if self.pacing == "realtime":
            if self._timestamp is None:
                raise ValueError("realtime pacing requires increasing PTS or finite positive FPS")
            if self._pacing_origin_timestamp is None or self._rebase_on_next_capture:
                self._pacing_origin_timestamp = self._timestamp
                self._started_at = time.monotonic()
                self._rebase_on_next_capture = False
            deadline = self._started_at + self._timestamp - self._pacing_origin_timestamp
            delay = deadline - time.monotonic()
            if delay > 0:
                if delay > self.read_timeout:
                    raise TimeoutError(f"video pacing delay exceeded {self.read_timeout}s")
                time.sleep(delay)
        self._next_frame += 1
        return frame

    def stop(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def resume_pacing(self):
        """Resume from the next frame without catching up over paused wall time."""
        self._rebase_on_next_capture = True

BACKENDS = {
    "realsense": RealSenseCamera,
    "video_file": VideoFileCamera,
}
