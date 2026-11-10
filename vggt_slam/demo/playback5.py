"""Play all decoded RGB frames; hold the last estimated camera in the tail."""
import json
import math
from vggt_slam.demo.smooth_runtime import PlaybackClock


def playback_clock(run,times):
    clock=PlaybackClock(times)
    if run.manifest.get('status')!='completed' or not run.frames:return clock
    path=run.path/'keyframes/video_frames.jsonl'
    if not path.is_file():return clock
    meta=json.loads((run.path/run.frames[0]['asset_paths']['metadata']).read_text())
    origin=meta.get('source_timestamp')
    if not isinstance(origin,(int,float)) or not math.isfinite(origin):return clock
    for line in path.read_text().splitlines():
        try:value=json.loads(line).get('source_timestamp_seconds')
        except json.JSONDecodeError:continue
        if isinstance(value,(int,float)) and math.isfinite(value):clock.duration=max(clock.duration,value-origin)
    return clock
