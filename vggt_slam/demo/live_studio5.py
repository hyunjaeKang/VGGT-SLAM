"""Independent V5 supervisor: VGGT-SLAM geometry, no semantic worker."""
from pathlib import Path
import json,os,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from vggt_slam.demo.live_studio import (ROOT,LiveStudio,configuration,probe_video,read_json,committed_events,snapshot_run,TERMINAL)
from vggt_slam.demo.live_studio4 import LiveStudioV4
from vggt_slam.demo.status import write_json_atomic


def v5_configuration(query):
    result=configuration({**{'submap_size':['8'],'min_disparity':['45'],'max_loops':['1']},**query})
    width=int(query.get('image_size',['378'])[0])
    if width not in (224,322,378,518):raise ValueError('추론 너비: 224/322/378/518')
    if result['max_loops'] not in (0,1):raise ValueError('루프 검출: 0(끄기) 또는 1(켜기)')
    result['image_size']=width
    import math
    gap=float(query.get('min_loop_seconds',['10'])[0])
    if not math.isfinite(gap) or not 0<=gap<=600:raise ValueError('루프 시간 간격: 0~600초')
    result['min_loop_seconds']=gap
    result['cpu_threads']=4
    return result


class LiveStudioV5(LiveStudioV4):
    def __init__(self,viewer_port=8108,jobs_root=None):
        LiveStudio.__init__(self,viewer_port,jobs_root or ROOT/'logs/demo_v5_jobs')
    def reserve(self,filename,options):
        target=LiveStudio.reserve(self,filename,options)
        self.update(version='slam-v5',semantic_enabled=False,search_ready=False)
        return target
    def state(self):return {**LiveStudio.state(self),'version':'slam-v5'}
    def launch_viewer(self,run,control=None):
        self.stop_child(self.viewer);self.update(viewer_ready=False)
        command=[str(ROOT/'.venv/bin/python'),'-u','demo.py','view','--version','slam5','--run',str(run),
                 '--port',str(self.viewer_port),'--source-fps',str(self.job['probe']['fps'])]
        if control:command+=['--live-control',str(control)]
        self.viewer=self.spawn(command,Path(self.job['folder'])/'viewer.log')
        import urllib.request
        deadline=time.monotonic()+60
        while not self.cancelled.wait(.2):
            if self.viewer.poll() is not None:raise RuntimeError('V5 뷰어 시작 실패: viewer.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.viewer_port}/api/frame',timeout=.5) as r:
                    if json.load(r).get('version',0):break
            except (OSError,ValueError):pass
            if time.monotonic()>deadline:raise RuntimeError('V5 뷰어 준비 시간 초과')
        if self.cancelled.is_set():raise InterruptedError('작업 중지')
        self.viewer_revision+=1;self.update(viewer_ready=True,viewer_revision=self.viewer_revision)
    def prepare_media(self,run):
        # Original input stays immutable and can be served by HTTP Range directly.
        # With a smoke frame limit, reuse the original RGB stream; timeline bounds
        # are the computed keyframe times, not a newly invented source FPS.
        folder=run/'evidence/smooth_media_v5';folder.mkdir(exist_ok=False,parents=True)
        (folder/'rgb.mp4').symlink_to(Path(self.job['input']).resolve()) if Path(self.job['input']).suffix.lower() in ('.mp4','.m4v') else None
        if not (folder/'rgb.mp4').exists():
            import shutil
            cmd=[shutil.which('ffmpeg') or 'ffmpeg','-nostdin','-v','error','-i',self.job['input'],'-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(folder/'rgb.mp4')]
            self.wait(self.spawn(cmd,Path(self.job['folder'])/'media.log'))
        write_json_atomic(folder/'index.json',{'status':'completed','source_run':str(run.resolve()),'source_fps':self.job['probe']['fps'],'video':'rgb.mp4','source':'original input; SLAM frame timing bounds playback'})
    def run(self):
        folder=Path(self.job['folder']);started=time.perf_counter();stages=[]
        def stage(name,**data):
            stages.append({'stage':name,'elapsed_seconds':time.perf_counter()-started,**data})
            write_json_atomic(folder/'timings.json',stages)
        try:
            self.stop_child(self.viewer);self.viewer=None
            self.update(state='loading',message='VGGT-SLAM 모델 로딩 · 객체/도로/하늘 계산 없음')
            self.update(probe=probe_video(self.job['input']))
            command=[str(ROOT/'.venv/bin/python'),'-u','scripts/demo_slam_v5.py','--video',self.job['input']]
            for key,value in self.job['options'].items():command+=['--'+key,str(value)]
            write_json_atomic(folder/'command.json',command)
            geometry=self.spawn(command,folder/'inference.log');stage('geometry_started')
            run=None;last_step=None;revision=0;mirror=folder/'live_run';control=folder/'live_control.json'
            while not self.cancelled.wait(.25):
                if run is None:
                    for m in sorted((ROOT/'logs/demo_runs').glob('video_*/manifest.json'),reverse=True):
                        if read_json(m,{}).get('config',{}).get('video')==self.job['input']:
                            run=m.parent;self.update(run=str(run));stage('run_created');break
                if run:
                    events=committed_events(run);step=int(events[-1]['payload']['step']) if events else None
                    if step is not None and step!=last_step:
                        snapshot_run(run,mirror,events);last_step=step;revision+=1
                        write_json_atomic(control,{'revision':revision,'map_revision':step,'allow_search':False,'geometry_done':False,'semantic_results':{}})
                        count=len({e['source_frame_id'] for e in events if e['event_type']=='frame_selected'})
                        summary=read_json(run/'video_summary.json',{})
                        self.update(state='inference',message=f'VGGT-SLAM 지도 갱신 · 추론 너비 {self.job["options"]["image_size"]}',map_frames=count,steps=revision,decoded_frames=summary.get('decoded_frames',count))
                        stage('map_committed',frames=count,step=step)
                        if self.viewer is None:self.launch_viewer(mirror,control)
                if geometry.poll() is not None:
                    if geometry.returncode:raise RuntimeError('VGGT-SLAM 실패: inference.log 확인')
                    # If the process exited between scanning and commit, scan once more.
                    final=committed_events(run) if run else []
                    if not final:raise RuntimeError('계산된 지도 프레임이 없습니다')
                    if int(final[-1]['payload']['step'])!=last_step:continue
                    break
            if self.cancelled.is_set():raise InterruptedError('작업 중지')
            stage('geometry_completed');self.update(state='finalizing',message='궤적·점군 저장 완료 · 뷰어 준비')
            self.prepare_media(run)
            self.launch_viewer(run)
            summary=read_json(run/'video_summary.json',{})
            elapsed=time.perf_counter()-started
            self.update(state='completed',message='V5 VGGT-SLAM 완료 · 3D / RGB / BEV',decoded_frames=summary.get('decoded_frames',self.job['map_frames']),elapsed_seconds=elapsed,search_ready=True)
            stage('completed')
            write_json_atomic(folder/'report.json',{'job':dict(self.job),'stages':stages,'video_summary':summary,'semantic_workers':0,'quality_note':'Reduced model resolution trades density/detail for speed; no independent GT accuracy assertion.'})
        except BaseException as exc:
            for child in self.children:self.stop_child(child)
            self.update(state='cancelled' if self.cancelled.is_set() or isinstance(exc,InterruptedError) else 'failed',message=str(exc) or type(exc).__name__,viewer_ready=False)
            stage('stopped',error=str(exc))
    def open_completed(self,ident):
        # The base opener manages ownership and history, then our viewer override.
        LiveStudio.open_completed(self,ident)
    def update(self,**fields):
        if fields.get('message')=='저장된 V3 지도 · 전체 구간 검색 가능':fields.update(message='저장된 V5 지도 · 검색 가능',search_ready=True)
        LiveStudio.update(self,**fields)
        if self.job.get('state') == 'completed':
            with self.lock:
                self.history = [dict(self.job)] + [j for j in self.history if j['id'] != self.job['id']]
                self.history.sort(key=lambda j:j.get('created_at',0),reverse=True)


def serve_v5(port=8107, viewer_port=8108):
    if port==viewer_port:raise ValueError('Use different controller and viewer ports')
    studio=LiveStudioV5(viewer_port)
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
            if path=='/':self.send(200,(Path(__file__).parent/'web/studio_live5.html').read_bytes(),'text/html; charset=utf-8')
            elif path=='/guide':self.send(200,(ROOT/'docs/USER_GUIDE.html').read_bytes(),'text/html; charset=utf-8')
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
                query=parse_qs(url.query);options=v5_configuration(query)
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
    print(f'SLAM V5: http://localhost:{port} (map workspace: {viewer_port})',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.close();server.server_close()
