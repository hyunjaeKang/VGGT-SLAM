"""Encode an existing contiguous source image interval for V2 native RGB playback."""
import argparse,json,re,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vggt_slam.demo.search_assets import segmentation_source

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-fps',type=float,required=True,help='Explicit playback FPS; never inferred from filename spacing')
    args=parser.parse_args();run=args.run.resolve();out=args.output.resolve()
    if not out.is_relative_to(run/'evidence') or not 0<args.source_fps<=120:parser.error('Invalid output or FPS')
    out.mkdir(exist_ok=False,parents=True);start=time.monotonic()
    events=[json.loads(l) for l in (run/'events.jsonl').read_text().splitlines()]
    frames=[e for e in events if e['event_type']=='frame_selected']
    metas=[json.loads((run/e['asset_paths']['metadata']).read_text()) for e in frames]
    first,last=Path(metas[0]['source_path']),Path(metas[-1]['source_path'])
    match=re.fullmatch(r'(\d+)(\.[^.]+)',first.name)
    if not match or first.parent!=last.parent:parser.error('Contiguous numbered source images required')
    lower,upper=int(first.stem),int(last.stem);digits=len(match[1]);suffix=match[2]
    for n in range(lower,upper+1):
        if not (first.parent/f'{n:0{digits}d}{suffix}').is_file():parser.error(f'Missing original frame {n}')
    for i in sorted(set([0,len(frames)//2,len(frames)-1])):
        _,mapping,reason=segmentation_source(run,frames[i],metas[i])
        if mapping is None:parser.error(f'Native RGB verification failed: {reason}')
    pattern=first.parent/f'%0{digits}d{suffix}'
    cmd=['ffmpeg','-nostdin','-v','error','-framerate',str(args.source_fps),'-start_number',str(lower),'-i',str(pattern),'-frames:v',str(upper-lower+1),'-vf','scale=1280:-2','-c:v','libx264','-threads','4','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'rgb.mp4')]
    subprocess.run(cmd,check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,width,height,duration,avg_frame_rate','-of','json',str(out/'rgb.mp4')]))['streams'][0]
    if int(probe['nb_frames'])!=upper-lower+1:raise RuntimeError('Encoded frame count mismatch')
    index={'status':'completed','source_run':str(run),'source_first':lower,'source_last':upper,'source_fps':args.source_fps,'timing':'explicit FPS; source timestamps unavailable','video':'rgb.mp4','probe':probe,'seconds':time.monotonic()-start}
    (out/'index.json').write_text(json.dumps(index,indent=2));print(json.dumps(index,indent=2))
