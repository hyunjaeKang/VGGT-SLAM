import cv2
import numpy as np
import pytest
import time

from vggt_slam.cameras import EndOfStream, VideoFileCamera


def make_video(path, count=4):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (32, 24))
    if not writer.isOpened():
        pytest.skip("OpenCV MJPG video writer is unavailable")
    for index in range(count):
        writer.write(np.full((24, 32, 3), index * 40, np.uint8))
    writer.release()


def test_video_file_camera_range_and_explicit_eof(tmp_path):
    path = tmp_path / "clip.avi"
    make_video(path)
    camera = VideoFileCamera(str(path), start_frame=1, end_frame=2)
    camera.start()
    try:
        first = camera.capture()
        assert first.shape == (24, 32, 3)
        assert camera.source_frame_id == 1
        assert camera.source_timestamp is not None
        second = camera.capture()
        assert second.shape == first.shape
        assert camera.source_frame_id == 2
        with pytest.raises(EndOfStream):
            camera.capture()
        assert camera.eof
        with pytest.raises(EndOfStream):
            camera.capture()
    finally:
        camera.stop()


def test_video_file_camera_rejects_unreadable_path(tmp_path):
    camera = VideoFileCamera(str(tmp_path / "missing.avi"))
    with pytest.raises(OSError, match="cannot open video file"):
        camera.start()


def test_video_file_camera_validates_range_and_pacing():
    with pytest.raises(ValueError, match="invalid video frame range"):
        VideoFileCamera("clip.avi", start_frame=3, end_frame=2)
    with pytest.raises(ValueError, match="pacing"):
        VideoFileCamera("clip.avi", pacing="loop")


def test_video_file_camera_realtime_pacing(tmp_path):
    path = tmp_path / "clip.avi"
    make_video(path, count=3)
    camera = VideoFileCamera(str(path), pacing="realtime")
    camera.start()
    try:
        camera.capture()
        start = time.monotonic()
        camera.capture()
        assert time.monotonic() - start >= 0.05
    finally:
        camera.stop()


def test_video_resume_rebases_clock_instead_of_catching_up(tmp_path, monkeypatch):
    path = tmp_path / "clip.avi"
    make_video(path, count=3)
    camera = VideoFileCamera(str(path), pacing="realtime")
    camera.start()
    try:
        camera.capture()
        delays = []
        monkeypatch.setattr(time, "monotonic", lambda: 100.0)
        monkeypatch.setattr(time, "sleep", delays.append)
        camera.resume_pacing()
        camera.capture()
        camera.capture()
        assert max(delays) == pytest.approx(0.1)
    finally:
        camera.stop()


def mock_timed_camera(monkeypatch, timestamps, fps, pacing="realtime"):
    class Capture:
        index = -1

        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def get(self, key):
            return fps if key == cv2.CAP_PROP_FPS else timestamps[self.index] * 1000

        def read(self):
            self.index += 1
            return True, np.zeros((2, 2, 3), dtype=np.uint8)

        def release(self):
            pass

    clock, delays = [10.0], []

    def sleep(delay):
        delays.append(delay)
        clock[0] += delay

    monkeypatch.setattr(cv2, "VideoCapture", lambda *a: Capture())
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(time, "sleep", sleep)
    camera = VideoFileCamera("mock", pacing=pacing)
    camera.start()
    return camera, delays


def test_variable_frame_rate_paces_by_pts_instead_of_average_fps(monkeypatch):
    camera, delays = mock_timed_camera(monkeypatch, [0, .04, .19], 30)
    for _ in range(3):
        camera.capture()
    np.testing.assert_allclose(delays, [.04, .15])
    assert camera.source_timestamp_type == "video_pts_seconds"


@pytest.mark.parametrize("fps", [0, -1, float("nan"), float("inf")])
def test_invalid_fps_still_allows_valid_pts_pacing(monkeypatch, fps):
    camera, delays = mock_timed_camera(monkeypatch, [0, .1, .3], fps)
    for _ in range(3):
        camera.capture()
    np.testing.assert_allclose(delays, [.1, .2])
    assert camera._fps == 0 and camera.source_timestamp == .3


def test_invalid_pts_are_explicit_fps_approximations(monkeypatch):
    camera, _ = mock_timed_camera(monkeypatch, [float("nan"), 0, -1, float("inf"), .4], 10)
    values, types = [], []
    for _ in range(5):
        camera.capture(); values.append(camera.source_timestamp); types.append(camera.source_timestamp_type)
    np.testing.assert_allclose(values, [0, .1, .2, .3, .4])
    assert types[:4] == ["video_frame_index_over_fps_seconds"] * 4
    assert types[-1] == "video_pts_seconds"


def test_backward_pts_extrapolates_from_previous_timestamp(monkeypatch):
    camera, _ = mock_timed_camera(monkeypatch, [10, 9], 10)
    camera.capture(); camera.capture()
    assert camera.source_timestamp == pytest.approx(10.1)
    assert camera.raw_source_timestamp == 9
    assert camera.source_timestamp_type == "video_fps_extrapolated_seconds"


def test_no_clock_marks_offline_unavailable_and_rejects_realtime(monkeypatch):
    camera, _ = mock_timed_camera(monkeypatch, [float("nan")], 0, "offline")
    camera.capture()
    assert camera.source_timestamp is None and camera.source_timestamp_type == "unavailable"
    camera, _ = mock_timed_camera(monkeypatch, [float("nan")], 0)
    with pytest.raises(ValueError, match="requires increasing PTS"):
        camera.capture()


@pytest.mark.parametrize('degrees', [90, 180, 270])
def test_mov_display_rotation_matches_ffmpeg_upright_frame(tmp_path, degrees):
    """Compare actual decode against ffmpeg autorotation, including portrait MOV."""
    import shutil
    import subprocess
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:pytest.skip('ffmpeg required for a real display-matrix fixture')
    source=tmp_path/'source.avi'
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10.,(64,48))
    frame=np.zeros((48,64,3),np.uint8)
    frame[:20,:25]=(10,30,230);frame[25:,30:]=(220,120,10)
    for _ in range(3):writer.write(frame)
    writer.release()
    base=tmp_path/'base.mp4';movie=tmp_path/'rotated.mov';reference=tmp_path/'reference.png'
    subprocess.run([ffmpeg,'-v','error','-i',str(source),'-c:v','libx264','-pix_fmt','yuv420p',str(base)],check=True)
    subprocess.run([ffmpeg,'-v','error','-i',str(base),'-c','copy','-metadata:s:v:0',f'rotate={degrees}',str(movie)],check=True)
    subprocess.run([ffmpeg,'-v','error','-i',str(movie),'-frames:v','1',str(reference)],check=True)
    camera=VideoFileCamera(str(movie));camera.start()
    try:
        decoded=camera.capture();upright=cv2.imread(str(reference))
        assert decoded.shape==upright.shape
        assert np.abs(decoded.astype(float)-upright).mean()<3
    finally:camera.stop()
