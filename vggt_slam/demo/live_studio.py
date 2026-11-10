"""Local video upload, real VGGT/SAM3 workers, and committed live map previews.

Owns only children it starts. Originals, completed runs, and V1/V2 are untouched.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import json
import math
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid

from vggt_slam.demo.status import write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
EXTENSIONS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}
TERMINAL = {'completed', 'failed', 'cancelled'}


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def complete_events(path):
    """A concurrent writer may be midway through the last JSONL record."""
    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in raw.split(b'\n')[:-1] if line]


def committed_events(run):
    events = complete_events(Path(run)/'events.jsonl')
    end = max((i for i,e in enumerate(events) if e['event_type']=='optimization_finished'), default=-1)
    return events[:end+1]


def snapshot_run(run, target, events):
    """Publish a prefix ending AFTER optimization; never expose a partial NPZ."""
    run, target = Path(run).resolve(), Path(target)
    if not events or events[-1]['event_type'] != 'optimization_finished':
        raise ValueError('A completed optimization is required')
    target.mkdir(parents=True, exist_ok=True)
    manifest = read_json(run/'manifest.json')
    manifest['assets'] = {'events':'events.jsonl'}
    manifest['live_source_run'] = str(run)
    write_json_atomic(target/'manifest.json', manifest)
    temporary = target/'events.tmp'
    temporary.write_text(''.join(json.dumps(e)+'\n' for e in events))
    os.replace(temporary,target/'events.jsonl')
    for name in ('submaps','keyframes'):
        if not (target/name).exists(): (target/name).symlink_to(run/name, target_is_directory=True)
    (target/'snapshots').mkdir(exist_ok=True)
    for event in events:
        if event['event_type']=='optimization_finished':
            step=str(event['payload']['step'])
            if not (target/'snapshots'/step).exists():
                (target/'snapshots'/step).symlink_to(run/'snapshots'/step,target_is_directory=True)
    return int(events[-1]['payload']['step'])


def configuration(query):
    values = {'submap_size':int(query.get('submap_size',['8'])[0]),
              'max_frames':int(query.get('max_frames',['0'])[0]),
              'min_disparity':float(query.get('min_disparity',['10'])[0]),
              'max_loops':int(query.get('max_loops',['1'])[0])}
    if not (2<=values['submap_size']<=32 and 0<=values['max_frames']<=100000
            and math.isfinite(values['min_disparity']) and 0<=values['min_disparity']<=200
            and 0<=values['max_loops']<=3):
        raise ValueError('Invalid processing settings')
    return values


def probe_video(path):
    probe = subprocess.run([shutil.which('ffprobe') or 'ffprobe','-v','error','-select_streams','v:0',
                            '-show_entries','stream=width,height,avg_frame_rate:format=duration',
                            '-of','json',str(path)],capture_output=True,text=True,timeout=30,check=True)
    data=json.loads(probe.stdout)
    stream=data['streams'][0]
    n,d=map(float,stream['avg_frame_rate'].split('/'));fps=n/d
    if not math.isfinite(fps) or fps<=0 or stream['width']<2 or stream['height']<2:
        raise ValueError('Invalid video stream')
    return dict(width=stream['width'],height=stream['height'],fps=fps,duration=float(data.get('format',{}).get('duration') or 0))


class LiveStudio:
    def __init__(self, viewer_port=8104, jobs_root=None):
        self.viewer_port=viewer_port
        self.jobs_root=Path(jobs_root or ROOT/'logs/demo_v3_jobs')
        self.jobs_root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.job=None
        self.children=[]
        self.viewer=None
        self.cancelled=threading.Event()
        self.closed=False
        self.upload_active=False
        self.worker_thread=None
        self.viewer_revision=0
        # Retain completed jobs across service restarts; restore their final map on demand.
        self.history=[s for p in self.jobs_root.glob('*/job.json') if (s:=read_json(p))]
        self.history.sort(key=lambda s:s.get('created_at',0),reverse=True)

    def update(self, **fields):
        with self.lock:
            self.job.update(fields,updated_at=time.time())
            write_json_atomic(Path(self.job['folder'])/'job.json',self.job)

    def reserve(self, filename, options):
        filename=Path(filename.replace('\\','/')).name
        suffix=Path(filename).suffix.lower()
        if suffix not in EXTENSIONS:raise ValueError('지원 영상: mp4, mov, mkv, avi, webm, m4v')
        with self.lock:
            if self.closed:raise RuntimeError('Service is shutting down')
            if self.upload_active or (self.job and self.job['state'] not in TERMINAL) or (self.worker_thread and self.worker_thread.is_alive()):
                raise RuntimeError('이미 생성 작업이 실행 중입니다')
            self.cancelled.clear()
            ident='live_'+time.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]
            folder=self.jobs_root/ident;folder.mkdir(exist_ok=False)
            self.job={'id':ident,'folder':str(folder),'filename':filename,'input':str(folder/('input'+suffix)),
                      'created_at':time.time(),'state':'uploading','message':'영상 업로드 중',
                      'options':options,'run':None,'decoded_frames':0,'map_frames':0,'steps':0,'road_frames':0,
                      'viewer_ready':False,'viewer_revision':self.viewer_revision,'search_ready':False}
            self.update()
            return Path(self.job['input'])

    def start(self):
        self.worker_thread=threading.Thread(target=self.run,daemon=True)
        self.worker_thread.start()

    def spawn(self, command, log):
        with self.lock:
            if self.cancelled.is_set() or self.closed:raise InterruptedError('사용자가 작업을 중지했습니다')
            with Path(log).open('ab') as stream:
                child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                    env={**os.environ,'PYTHONUNBUFFERED':'1','PYTORCH_ENABLE_MPS_FALLBACK':'1'})
            self.children.append(child)
            return child

    @staticmethod
    def stop_child(child):
        if child is None or child.poll() is not None:return
        child.send_signal(signal.SIGINT)
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=4)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=4)

    def stop(self):
        self.cancelled.set()
        with self.lock:
            children=list(self.children)
            job_id=self.job['id'] if self.job else None
        for child in children:self.stop_child(child)
        if self.job and self.job['id']==job_id and self.job['state'] not in TERMINAL:
            self.update(state='cancelled',message='작업 중지 · 생성된 파일과 결과는 보존했습니다',viewer_ready=False)

    def close(self):
        self.closed=True
        self.stop()

    def launch_viewer(self, run, control=None):
        self.stop_child(self.viewer)
        self.update(viewer_ready=False)
        command=[str(ROOT/'.venv/bin/python'),'-u','demo.py','view','--version','smooth',
                 '--run',str(run),'--port',str(self.viewer_port),'--source-fps',str(self.job['probe']['fps']),
                 '--studio-label','Live V3']
        if control:command+=['--live-control',str(control)]
        self.viewer=self.spawn(command,Path(self.job['folder'])/'viewer.log')
        # TCP readiness alone precedes the first rendered frame; wait for frame metadata.
        import urllib.request
        for _ in range(180):
            if self.cancelled.wait(.25):raise InterruptedError('작업 중지')
            if self.viewer.poll() is not None:raise RuntimeError('뷰어 시작 실패: viewer.log 확인')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.viewer_port}/api/frame',timeout=.5) as response:
                    if json.load(response).get('version',0)>0:break
            except (OSError, ValueError):pass
        else:raise RuntimeError('뷰어 시작 시간 초과: viewer.log 확인')
        self.viewer_revision+=1
        self.update(viewer_ready=True,viewer_revision=self.viewer_revision)

    def prepare_media(self, run):
        folder=run/'evidence'/'smooth_media_v3';folder.mkdir(exist_ok=False)
        command=[shutil.which('ffmpeg') or 'ffmpeg','-v','error','-i',self.job['input'],'-an']
        if self.job['options']['max_frames']:command+=['-frames:v',str(self.job['options']['max_frames'])]
        command+=['-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(folder/'rgb.mp4')]
        process=self.spawn(command,Path(self.job['folder'])/'media.log')
        self.wait(process)
        write_json_atomic(folder/'index.json',{'status':'completed','source_run':str(run.resolve()),
            'source_fps':self.job['probe']['fps'],'video':'rgb.mp4','source':'uploaded input; no frame interpolation'})

    def wait(self, process):
        while process.poll() is None:
            if self.cancelled.wait(.2):raise InterruptedError('작업 중지')
        if process.returncode:raise RuntimeError(f'Worker failed (exit {process.returncode}); 작업 로그 확인')

    def run(self):
        try:
            folder=Path(self.job['folder'])
            self.stop_child(self.viewer)
            self.viewer=None
            self._road_signature=None
            self.update(state='loading',message='영상 검증 및 VGGT 모델 로딩 중')
            self.update(probe=probe_video(self.job['input']))
            python=str(ROOT/'.venv/bin/python')
            command=[python,'-u','main_realtime.py','--camera','video_file','--video',self.job['input'],
                     '--headless','--no_video_window','--video_pacing','offline','--device','auto']
            for name,value in self.job['options'].items():command+=['--'+name,str(value)]
            write_json_atomic(folder/'command.json',command)
            process=self.spawn(command,folder/'inference.log')
            run=None;step=None;road=None;road_step=None;finished_road=None;revision=0;road_pointer=None
            control=folder/'live_control.json';mirror=folder/'live_run'
            while True:
                if self.cancelled.wait(.4):raise InterruptedError('작업 중지')
                if run is None:
                    for manifest_path in sorted((ROOT/'logs/demo_runs').glob('video_*/manifest.json'),reverse=True):
                        manifest=read_json(manifest_path,{})
                        if manifest.get('config',{}).get('video')==self.job['input']:
                            run=manifest_path.parent;self.update(run=str(run));break
                if run:
                    events=committed_events(run)
                    latest=int(events[-1]['payload']['step']) if events else None
                    if latest is not None and latest!=step:
                        step=snapshot_run(run,mirror,events)
                        # Live mirror owns its events; evidence references resolve to the actual run.
                        (run/'evidence').mkdir(exist_ok=True)
                        if not (mirror/'evidence').exists():(mirror/'evidence').symlink_to(run/'evidence',target_is_directory=True)
                        revision+=1
                        write_json_atomic(control,{'revision':revision,'allow_search':False,'road_result':road_pointer})
                        self.update(state='inference',message='실제 VGGT 지도 갱신 · ROAD는 별도 계산 중',
                                    steps=sum(e['event_type']=='optimization_finished' for e in events),
                                    map_frames=len({e['source_frame_id'] for e in events if e['event_type']=='frame_selected'}))
                        if self.viewer is None or self.viewer.poll() is not None:self.launch_viewer(mirror,control)
                    self.update(decoded_frames=len(complete_events(run/'keyframes/video_frames.jsonl')))
                    if road:
                        status=read_json(road_folder/'status.json',{})
                        partial=status.get('partial_result')
                        if partial:
                            partial_path=road_snapshot/partial
                            signature=(str(partial_path),status.get('completed_frames',0))
                            if signature!=getattr(self,'_road_signature',None) and partial_path.exists():
                                self._road_signature=signature
                                road_pointer=str(partial_path.relative_to(run))
                                revision+=1
                                write_json_atomic(control,{'revision':revision,'allow_search':False,'road_result':road_pointer})
                                self.update(road_frames=max(self.job['road_frames'],status.get('completed_frames',0)))
                        if road.poll() is not None:
                            if road.returncode or status.get('state')!='completed':
                                raise RuntimeError('ROAD 분할 실패: road_*.log 확인 (3D 지도는 보존됨)')
                            result=road_snapshot/status['result']
                            registered=run/'evidence/query_jobs'/f'v3_road_step_{road_step}'
                            registered.mkdir(parents=True,exist_ok=False)
                            write_json_atomic(registered/'status.json',{**status,'result':str(result.relative_to(run))})
                            road_pointer=str(result.relative_to(run));finished_road=road_step;road=None
                            self.update(road_frames=max(self.job['road_frames'],status.get('attempted_frames',0)))
                            revision+=1
                            write_json_atomic(control,{'revision':revision,'allow_search':False,'road_result':road_pointer})
                    if step is not None and road is None and finished_road!=step:
                        road_step=step
                        road_snapshot=run/'evidence/v3_snapshots'/str(step)
                        snapshot_run(run,road_snapshot,events)
                        cache=run/'evidence/segmentation_cache_v3';cache.mkdir(exist_ok=True)
                        (road_snapshot/'evidence').mkdir(exist_ok=True)
                        (road_snapshot/'evidence/segmentation_cache_v3').symlink_to(cache,target_is_directory=True)
                        road_folder=road_snapshot/'evidence/query_jobs/road'
                        road=self.spawn([str(ROOT/'.venv-open-set/bin/python'),'-u','scripts/demo_search_cached.py',
                            '--run',str(road_snapshot),'--output',str(road_folder),'--query','road','--mode','all','--stream-results'],folder/f'road_{step}.log')
                if process.poll() is not None:
                    if process.returncode:raise RuntimeError('VGGT 추론 실패: inference.log 확인')
                    if run is None or step is None:raise RuntimeError('지도를 생성할 키프레임이 부족합니다. 더 긴 영상 또는 작은 서브맵을 사용하세요')
                    if road is None and finished_road==step:break
                    self.update(state='road',message='3D 지도 완료 · 전체 키프레임 ROAD 분할 중')
            self.update(state='finalizing',message='하늘 필터와 재생 영상 준비 중')
            model=ROOT/'logs/demo_models/skyseg.onnx'
            if model.exists():
                self.wait(self.spawn([python,'scripts/demo_prepare_sky.py','--run',str(run),'--model',str(model),
                    '--output',str(run/'evidence/sky_v3')],folder/'sky.log'))
            self.prepare_media(run)
            self.launch_viewer(run)
            self.update(state='completed',message='지도 생성 완료 · 오른쪽 검색 패널에서 전체 구간 검색 가능',search_ready=True,
                        elapsed_seconds=time.time()-self.job['created_at'])
        except Exception as exc:
            for child in list(self.children):self.stop_child(child)
            self.update(state='cancelled' if self.cancelled.is_set() else 'failed',message=str(exc),viewer_ready=False)
        finally:
            with self.lock:
                if self.job:self.history.insert(0,dict(self.job))

    def open_completed(self, ident):
        with self.lock:
            if self.upload_active or (self.job and self.job['state'] not in TERMINAL) or (self.worker_thread and self.worker_thread.is_alive()):
                raise RuntimeError('현재 생성 작업이 끝난 후 열어주세요')
            saved=next((j for j in self.history if j['id']==ident and j['state']=='completed'),None)
            if saved is None:raise ValueError('완료된 작업을 찾을 수 없습니다')
            self.cancelled.clear()
            self.job=dict(saved)
            events=committed_events(Path(self.job['run']))
            self.job['steps']=sum(e['event_type']=='optimization_finished' for e in events)
            self.job['map_frames']=len({e['source_frame_id'] for e in events if e['event_type']=='frame_selected'})
            for path in (Path(self.job['run'])/'evidence/query_jobs').glob('v3_road_*/status.json'):
                self.job['road_frames']=max(self.job['road_frames'],read_json(path,{}).get('attempted_frames',0))
            self.update(state='opening',message='완료된 지도 여는 중',viewer_ready=False)
            def open_view():
                try:
                    self.launch_viewer(Path(self.job['run']))
                    self.update(state='completed',message='저장된 V3 지도 · 전체 구간 검색 가능',search_ready=True)
                except Exception as exc:self.update(state='failed',message=str(exc),viewer_ready=False)
            self.worker_thread=threading.Thread(target=open_view,daemon=True)
            self.worker_thread.start()

    def state(self):
        with self.lock:
            return {'job':dict(self.job) if self.job else None,'viewer_port':self.viewer_port,
                    'history':[{k:j.get(k) for k in ('id','filename','state','run')} for j in self.history[:20]]}


def serve_live(port=8103, viewer_port=8104):
    if port==viewer_port:raise ValueError('Use different controller and viewer ports')
    studio=LiveStudio(viewer_port)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,value,kind='application/json'):
            body=json.dumps(value,ensure_ascii=False).encode() if kind=='application/json' else value
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def same_origin(self):
            # File upload/compute must originate from this local UI, never another website.
            origin=self.headers.get('Origin')
            host=self.headers.get('Host','')
            return host in (f'localhost:{port}',f'127.0.0.1:{port}') and (origin is None or origin in (f'http://localhost:{port}',f'http://127.0.0.1:{port}'))
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':self.send(200,(Path(__file__).parent/'web/studio_live.html').read_bytes(),'text/html; charset=utf-8')
            elif path=='/api/live':self.send(200,studio.state())
            elif path=='/api/log' and studio.job:
                folder=Path(studio.job['folder']);logs={p.name:p.read_text(errors='replace')[-12000:] for p in folder.glob('*.log')}
                self.send(200,logs)
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.same_origin():self.send(403,{'error':'Local origin required'});return
            url=urlsplit(self.path)
            if url.path=='/api/open':
                try:
                    studio.open_completed(parse_qs(url.query).get('id',[''])[0])
                    self.send(202,studio.state())
                except (ValueError,RuntimeError) as exc:self.send(409,{'error':str(exc)})
                return
            if url.path=='/api/cancel':
                threading.Thread(target=studio.stop,daemon=True).start();self.send(202,{'message':'Stopping'});return
            if url.path!='/api/upload':self.send(404,{'error':'Not found'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 1<=length<=4*1024**3:raise ValueError('영상 크기는 1 byte–4 GB 범위여야 합니다')
                query=parse_qs(url.query);options=configuration(query)
                with studio.lock:
                    target=studio.reserve(query.get('name',['video.mp4'])[0],options)
                    studio.upload_active=True
            except (ValueError,RuntimeError) as exc:self.send(409 if isinstance(exc,RuntimeError) else 400,{'error':str(exc)});return
            try:
                self.connection.settimeout(120)
                with target.open('xb') as output:
                    remaining=length
                    while remaining:
                        if studio.cancelled.is_set():raise InterruptedError('Upload cancelled')
                        chunk=self.rfile.read(min(1024*1024,remaining))
                        if not chunk:raise ValueError('Incomplete upload')
                        output.write(chunk);remaining-=len(chunk)
                studio.update(state='queued',message='업로드 완료 · 추론 시작 중')
                studio.start();self.send(202,studio.state())
            except Exception as exc:
                studio.update(state='cancelled' if studio.cancelled.is_set() else 'failed',message=str(exc))
                self.send(400,{'error':str(exc)})
            finally:
                with studio.lock:studio.upload_active=False
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Live V3: http://localhost:{port} (map workspace: {viewer_port})',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.close();server.server_close()
