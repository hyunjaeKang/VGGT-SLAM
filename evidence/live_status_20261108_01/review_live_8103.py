import json,time,urllib.request,subprocess
from pathlib import Path
from datetime import datetime,timezone
out={'at':datetime.now(timezone.utc).isoformat()}
for port,path in [(8103,'/api/live'),(8104,'/api/frame'),(8104,'/api/smooth')]:
 try:
  with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=15) as r:d=json.load(r)
  if path=='/api/live':out['live']=d
  elif path=='/api/frame':out['frame']=d
  else:out['smooth']={k:v for k,v in d.items() if k not in ['camera_path','gpu_scene']}
 except Exception as e:out[str(port)+path]={'error':str(e)}
job=Path(out['live']['job']['folder']);run=Path(out['live']['job']['run'])
summary=json.loads((run/'video_summary.json').read_text());out['summary']=summary
out['file_sizes']={name:(run/name).stat().st_size for name in ['manifest.json','poses.txt','poses_points.pcd']}
road=[]
for p in run.glob('evidence/v3_snapshots/*/evidence/query_jobs/road/status.json'):
 s=json.loads(p.read_text());road.append({'step':p.parts[-6], 'status':s, 'mtime':p.stat().st_mtime})
out['road']=road;out['elapsed_job_seconds']=time.time()-out['live']['job']['created_at']
out['processes']=subprocess.check_output(['ps','-axo','pid,ppid,%cpu,%mem,rss,etime,command'],text=True)
out['processes']='\n'.join(l for l in out['processes'].splitlines() if any(x in l for x in ['demo.py live','demo.py view','demo_search_cached.py','main_realtime.py','demo_prepare_sky.py']))
folder=Path('evidence/live_status_20261108_01');folder.mkdir(parents=True,exist_ok=True);(folder/'status.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['live','summary','road']},indent=2,ensure_ascii=False))
print('summary keys:',summary.keys())
print('summary:',{k:v for k,v in summary.items() if not isinstance(v,(dict,list))})
