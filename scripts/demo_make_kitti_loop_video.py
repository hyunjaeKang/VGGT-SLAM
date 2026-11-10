"""Create new, non-overwriting test videos from the preserved V2 KITTI run."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import hashlib


def make(run,output,fps=10.):
    manifest=json.loads((run/'manifest.json').read_text());cfg=manifest['config']
    selection=json.loads((run/'selection.json').read_text())['frames']
    folder=Path(cfg['image_dir']);start,end=int(cfg['start']),int(cfg['end'])
    originals=[folder/f'{i:010d}.png' for i in range(start,end+1)]
    missing=[str(p) for p in originals if not p.is_file()]
    if missing:raise FileNotFoundError(f'Missing {len(missing)} frames, first: {missing[0]}')
    output.mkdir(parents=True,exist_ok=False)
    ffmpeg=shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    common=['-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart']
    full=output/'kitti_closed_loop_full_10fps.mp4'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-n','-framerate',str(fps),'-start_number',str(start),'-i',str(folder/'%010d.png'),'-frames:v',str(len(originals)),*common,str(full)],check=True)
    links=output/'selected_sources';links.mkdir()
    for i,row in enumerate(selection):(links/f'{i:06d}.png').symlink_to(Path(row['source']).resolve())
    selected=output/'kitti_closed_loop_v2_selected_10fps.mp4'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-n','-framerate',str(fps),'-i',str(links/'%06d.png'),'-frames:v',str(len(selection)),*common,str(selected)],check=True)
    result={'source_run':str(run.resolve()),'source_range_inclusive':[start,end],'source_image_directory':str(folder),'fps':fps,
      'timing_note':'10Hz replay assumption; original KITTI timestamps not imported. Selected clip is a compressed-time test, not original driving speed.',
      'full':{'path':str(full.resolve()),'frames':len(originals),'duration_seconds':len(originals)/fps,'video_sha256':hashlib.sha256(full.read_bytes()).hexdigest()},
      'selected':{'path':str(selected.resolve()),'frames':len(selection),'duration_seconds':len(selection)/fps,'video_sha256':hashlib.sha256(selected.read_bytes()).hexdigest(),'frame_ids':[r['frame_id'] for r in selection]},
      'source_modified':False}
    (output/'source_manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,default=Path('logs/demo_runs/s03_kitti_loop_on_20261031_01'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(make(a.run,a.output),indent=2))
