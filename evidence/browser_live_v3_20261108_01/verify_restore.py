import hashlib,json,time,urllib.request
from pathlib import Path
root=Path('/Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map')
run=root/'logs/demo_runs/video_20261108T173307_231634000'
before={name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in ['events.jsonl','poses.txt','poses_points.pcd']}
def get(port,path='/'):
 with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=10) as response:return response.read()
checks={}
for port in [8100,8101,8102,8103]:
 body=get(port).decode();checks[str(port)]=len(body)>100
 if port==8100:checks['picker_v3']='localhost:8103' in body
req=urllib.request.Request('http://127.0.0.1:8103/api/open?id=live_20261108T093304_c6cbb885',method='POST')
with urllib.request.urlopen(req,timeout=5) as response:assert response.status==202
for _ in range(80):
 state=json.loads(get(8103,'/api/live'))
 if state['job']['state']=='completed':break
 if state['job']['state']=='failed':raise RuntimeError(state)
 time.sleep(.25)
else:raise TimeoutError('Restore')
meta=json.loads(get(8104,'/api/frame'));clock=json.loads(get(8104,'/api/smooth'))
checks.update(restored=state['job']['viewer_ready'] and state['job']['search_ready'],
 same_run=state['job']['run']==str(run),road=meta['road_points']>0,
 native_media=bool(clock.get('media')),v3_title='Live V3' in get(8104).decode(),
 preserved=before=={name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in before})
report={'checks':checks,'state':state,'meta':meta,'smooth':clock,'preserved_sha256':before}
(root/'evidence/browser_live_v3_20261108_01/restore.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(checks));assert all(checks.values())
