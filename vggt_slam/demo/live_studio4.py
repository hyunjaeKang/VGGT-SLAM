"""Live V4: independent geometry and resident semantic workers; preserves V1-3."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
from urllib.parse import parse_qs,urlsplit

from vggt_slam.demo.live_studio import (ROOT,LiveStudio,configuration,probe_video,read_json,
                                        complete_events,committed_events,snapshot_run,TERMINAL)
from vggt_slam.demo.status import write_json_atomic


def v4_configuration(query):
    geo=configuration({**{'submap_size':['4'],'min_disparity':['45'],'max_loops':['0']},**query})
    names=[s.strip().lower() for s in query.get('objects',['car,person,bicycle'])[0].split(',') if s.strip()]
    if not 1<=len(names)<=12 or len(set(names))!=len(names) or any(not re.fullmatch(r'[a-z0-9 _-]{1,50}',n) for n in names):
        raise ValueError('사전 대상은 중복 없는 영어 이름 1~12개로 입력하세요')
    backend=query.get('backend',['yolo26'])[0]
    if backend not in ('yolo26','yolo11','yoloe','sam3'):raise ValueError('Unknown model backend')
    hz=float(query.get('detect_hz',['10'])[0])
    if not 1<=hz<=30:raise ValueError('검출 빈도는 1~30Hz')
    return {**geo,'classes':names,'backend':backend,'detect_hz':hz,'surfaces':backend!='sam3' and query.get('surfaces',['true'])[0]!='false',
            'semantic_device':query.get('semantic_device',['cpu'])[0]}


class LiveStudioV4(LiveStudio):
    def __init__(self,viewer_port=8106,jobs_root=None):super().__init__(viewer_port,jobs_root or ROOT/'logs/demo_v4_runs')
    def reserve(self,filename,options):
        semantic={k:options[k] for k in ('classes','backend','detect_hz','surfaces','semantic_device')}
        target=super().reserve(filename,{k:options[k] for k in ('submap_size','max_frames','min_disparity','max_loops')})
        self.update(version='live-v4',semantic_config=semantic,semantic_frames=0,model_loads=0,geometry_done=False)
        return target
    def spawn(self,command,log):
        with self.lock:
            if self.cancelled.is_set() or self.closed:raise InterruptedError('작업 중지')
            with Path(log).open('ab') as stream:
                process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,
                    env={**os.environ,'PYTHONUNBUFFERED':'1','PYTORCH_ENABLE_MPS_FALLBACK':'1','HF_HUB_OFFLINE':'1'})
            process._v4_group=True;self.children.append(process);return process
    @staticmethod
    def stop_child(child):
        if child is None or child.poll() is not None:return
        if getattr(child,'_v4_group',False):
            try:os.killpg(child.pid,signal.SIGINT)
            except ProcessLookupError:return
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=4)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=4)
        else:LiveStudio.stop_child(child)
    def launch_viewer(self,run,control=None):
        self.stop_child(self.viewer);self.update(viewer_ready=False)
        command=[str(ROOT/'.venv/bin/python'),'-u','demo.py','view','--version','live4','--run',str(run),
                 '--port',str(self.viewer_port),'--source-fps',str(self.job['probe']['fps'])]
        if control:command+=['--live-control',str(control)]
        self.viewer=self.spawn(command,Path(self.job['folder'])/'viewer.log')
        import urllib.request
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if self.cancelled.wait(.2):raise InterruptedError('작업 중지')
            if self.viewer.poll() is not None:raise RuntimeError('V4 viewer failed; viewer.log')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.viewer_port}/api/frame',timeout=.5) as r:
                    if json.load(r).get('version',0):break
            except (OSError,ValueError):pass
        else:raise RuntimeError('V4 viewer readiness timeout')
        self.viewer_revision+=1;self.update(viewer_ready=True,viewer_revision=self.viewer_revision)
    def run(self):
        folder=Path(self.job['folder']);timing=(folder/'controller_timings.jsonl').open('a')
        def log(stage,**values):timing.write(json.dumps({'stage':stage,'at':time.time(),'elapsed':time.time()-self.job['created_at'],**values})+'\n');timing.flush()
        try:
            self.stop_child(self.viewer);self.viewer=None
            self.update(state='loading',message='V4 모델·영상 준비 중')
            probe=probe_video(self.job['input']);self.update(probe=probe)
            cfg=self.job['semantic_config'];models=ROOT/'logs/demo_models/v4'
            checkpoint={'yolo26':'yolo26n-seg.pt','yolo11':'yolo11n-seg.pt','yoloe':'yoloe-26s-seg.pt','sam3':'sam3.pt'}[cfg['backend']]
            semantic_config={'id':self.job['id'],'input':self.job['input'],'source_fps':probe['fps'],
                'max_frames':self.job['options']['max_frames'],'checkpoint':str(models/checkpoint),
                'surface_checkpoint':str(models/'segformer-b0-cityscapes'),'classes':cfg['classes'],'backend':cfg['backend'],
                'device':cfg['semantic_device'],'detect_hz':cfg['detect_hz'],'surfaces':cfg['surfaces']}
            if cfg['backend']!='sam3' and not (models/checkpoint).is_file():raise ValueError(f'모델 준비가 필요합니다: {models/checkpoint}')
            write_json_atomic(folder/'semantic_config.json',semantic_config)
            write_json_atomic(folder/'semantic_control.json',{'geometry_done':False})
            python=ROOT/('.venv-open-set/bin/python' if cfg['backend']=='sam3' else '.venv-v4/bin/python')
            semantic=self.spawn([str(python),'-u','scripts/demo_semantic_worker_v4.py','--config',str(folder/'semantic_config.json')],folder/'semantic.log')
            command=[str(ROOT/'.venv/bin/python'),'-u','main_realtime.py','--camera','video_file','--video',self.job['input'],
                     '--headless','--no_video_window','--video_pacing','offline','--device','auto']
            for name,value in self.job['options'].items():command+=['--'+name,str(value)]
            write_json_atomic(folder/'command.json',command)
            geometry=self.spawn(command,folder/'inference.log');log('workers_started')
            run=None;last_step=None;last_sem=-1;revision=0;geometry_done=False
            mirror=folder/'live_run';control=folder/'live_control.json'
            while not self.cancelled.wait(.25):
                stats=read_json(folder/'semantic_status.json',{})
                if stats.get('state')=='failed':raise RuntimeError('의미 worker 실패: '+stats.get('message','semantic.log'))
                if run is None:
                    for m in sorted((ROOT/'logs/demo_runs').glob('video_*/manifest.json'),reverse=True):
                        if read_json(m,{}).get('config',{}).get('video')==self.job['input']:
                            run=m.parent;self.update(run=str(run));log('run_created',run=str(run));break
                if run:
                    events=committed_events(run);step=int(events[-1]['payload']['step']) if events else None
                    changed=step is not None and step!=last_step
                    if changed:
                        snapshot_run(run,mirror,events);(run/'evidence').mkdir(exist_ok=True)
                        if not (mirror/'evidence').exists():(mirror/'evidence').symlink_to(run/'evidence',target_is_directory=True)
                        last_step=step;log('map_commit',step=step)
                        write_json_atomic(folder/'semantic_control.json',{'run':str(mirror),'step':step,'geometry_done':geometry_done})
                        self.update(state='inference',message='VGGT 지도 생성 + 사전 객체 검출·추적 동시 실행',
                            map_frames=len({e['source_frame_id'] for e in events if e['event_type']=='frame_selected'}),
                            steps=sum(e['event_type']=='optimization_finished' for e in events))
                    results=read_json(folder/'semantic_results.json',{})
                    sem_revision=results.get('revision',0)
                    if step is not None and (changed or sem_revision!=last_sem):
                        revision+=1;last_sem=sem_revision
                        write_json_atomic(control,{'revision':revision,'map_revision':step,'allow_search':True,'geometry_done':geometry_done,
                            'semantic_results':results.get('results',{}),'sky_groups':results.get('sky_groups',{}),'sky_frames':results.get('sky_frames',{}),'road_result':results.get('results',{}).get('road')})
                        if self.viewer is None:self.launch_viewer(mirror,control)
                    self.update(decoded_frames=len(complete_events(run/'keyframes/video_frames.jsonl')),
                        semantic_frames=stats.get('archive_inspected',0),road_frames=stats.get('archive_inspected',0) if cfg['surfaces'] else 0,
                        model_loads=stats.get('model_loads',0),live_frames=stats.get('live_inspected',0),live_skipped=stats.get('live_skipped',0),
                        semantic_device=stats.get('device'),search_ready=bool(last_step is not None))
                if geometry.poll() is not None and not geometry_done:
                    if geometry.returncode:raise RuntimeError('VGGT 추론 실패: inference.log')
                    if run is None or last_step is None:raise ValueError('키프레임이 부족합니다')
                    geometry_done=True;log('geometry_done')
                    self.update(state='semantic',geometry_done=True,message='지도 사용 가능 · 미완료 의미 관측만 보충 중')
                    write_json_atomic(folder/'semantic_control.json',{'run':str(mirror),'step':last_step,'geometry_done':True})
                if semantic.poll() is not None:
                    if semantic.returncode:raise RuntimeError('의미 worker 실패: semantic.log')
                    if geometry_done:break
            else:raise InterruptedError('작업 중지')
            self.update(state='finalizing',message='정밀 검색·재생용 최종 지도 연결 중')
            log('semantic_done',stats=read_json(folder/'semantic_status.json',{}))
            # Canonical semantic queries were produced under the mirror's evidence link.
            # Their relative paths are equally valid in the original run.
            sky=ROOT/'logs/demo_models/skyseg.onnx'
            if sky.exists():self.wait(self.spawn([str(ROOT/'.venv/bin/python'),'scripts/demo_prepare_sky.py','--run',str(run),
                '--model',str(sky),'--output',str(run/'evidence/sky_v4')],folder/'sky.log'))
            self.prepare_media(run)
            self.launch_viewer(run)
            stats=read_json(folder/'semantic_status.json',{})
            self.update(state='completed',message='V4 생성 완료 · 사전 객체·ROAD 및 임의 텍스트 정밀 검색 가능',search_ready=True,
                        semantic_frames=stats.get('archive_inspected',0),model_loads=stats.get('model_loads',0),elapsed_seconds=time.time()-self.job['created_at'])
            log('completed');write_json_atomic(folder/'report.json',{'job':self.job,'semantic':stats,'status':'functional demo validated separately; latency/GT targets not implied'})
        except BaseException as exc:
            for child in list(self.children):self.stop_child(child)
            self.update(state='cancelled' if self.cancelled.is_set() else 'failed',message=str(exc),viewer_ready=False)
            log('failed',error=str(exc))
        finally:
            timing.close()
            with self.lock:self.history.insert(0,dict(self.job))
    def state(self):
        data=super().state()
        if self.job:
            folder=Path(self.job['folder']);data['semantic']=read_json(folder/'semantic_status.json',{});data['latest']=read_json(folder/'live_latest.json',{})
        data['version']='live-v4';return data


def serve_v4(port=8105,viewer_port=8106):
    if port==viewer_port:raise ValueError('Use separate controller/viewer ports')
    studio=LiveStudioV4(viewer_port)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,code,value,kind='application/json'):
            body=json.dumps(value,ensure_ascii=False).encode() if kind=='application/json' else value
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':self.send(200,(Path(__file__).parent/'web/studio_live4.html').read_bytes(),'text/html; charset=utf-8')
            elif path=='/api/live':self.send(200,studio.state())
            elif path=='/live_rgb.jpg' and studio.job:
                p=Path(studio.job['folder'])/'live_rgb.jpg';self.send(200,p.read_bytes(),'image/jpeg') if p.exists() else self.send(404,{'error':'Waiting for live frame'})
            elif path=='/api/log' and studio.job:self.send(200,{p.name:p.read_text(errors='replace')[-10000:] for p in Path(studio.job['folder']).glob('*.log')})
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            host=self.headers.get('Host');origin=self.headers.get('Origin')
            if host not in (f'127.0.0.1:{port}',f'localhost:{port}') or (origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}')):
                self.send(403,{'error':'Local origin required'});return
            url=urlsplit(self.path);query=parse_qs(url.query)
            if url.path=='/api/cancel':threading.Thread(target=studio.stop,daemon=True).start();self.send(202,{});return
            if url.path=='/api/open':
                try:studio.open_completed(query.get('id',[''])[0]);self.send(202,studio.state())
                except (ValueError,RuntimeError) as exc:self.send(409,{'error':str(exc)})
                return
            if url.path!='/api/upload':self.send(404,{});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4*1024**3:raise ValueError('Video must be 1 byte to 4 GiB')
                with studio.lock:
                    target=studio.reserve(query.get('name',['video.mp4'])[0],v4_configuration(query));studio.upload_active=True
            except (ValueError,RuntimeError) as exc:self.send(409,{'error':str(exc)});return
            try:
                self.connection.settimeout(120)
                with target.open('xb') as stream:
                    while length:
                        if studio.cancelled.is_set():raise InterruptedError('Upload cancelled')
                        chunk=self.rfile.read(min(length,1024*1024))
                        if not chunk:raise ValueError('Incomplete upload')
                        stream.write(chunk);length-=len(chunk)
                studio.start();self.send(202,studio.state())
            except Exception as exc:studio.update(state='failed',message=str(exc));self.send(400,{'error':str(exc)})
            finally:
                with studio.lock:studio.upload_active=False
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Live V4: http://localhost:{port} · viewer {viewer_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:studio.close();server.server_close()
