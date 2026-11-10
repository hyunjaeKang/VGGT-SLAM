import json,time,urllib.request
from pathlib import Path
url='http://localhost:8108';checks={};samples=[]
def get(path):
    with urllib.request.urlopen(url+path,timeout=20) as r:return json.load(r)
def action(name,**values):
    r=urllib.request.Request(url+'/api/action',data=json.dumps({'action':name,**values}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(r,timeout=30) as response:assert response.status==200
    time.sleep(.15)
    meta=get('/api/frame');samples.append({'action':name,'frame':meta['frame_index'],'playing':meta['playing'],'follow_rgb':meta['follow_rgb']});return meta
meta=action('frame',frame=2);checks['frame_seek']=meta['frame_index']==2
meta=action('free');checks['free_camera']=meta['follow_rgb'] is False
meta=action('reset');checks['reset_rgb_camera']=meta['follow_rgb'] is True
meta=action('bev_view',zoom=1.75,pan=[.2,.1]);checks['bev_zoom_pan']=meta['bev_zoom']==1.75 and meta['bev_pan']==[.2,.1]
meta=action('zoom_reset');checks['bev_reset']=meta['bev_zoom']==1 and meta['bev_pan']==[0.,0.]
action('frame',frame=0)
action('play');meta=action('pause');checks['pause']=meta['playing'] is False
meta=action('frame',frame=0);checks['final_geometry_only']=meta['viewer_version']=='slam-v5' and meta['road_points']==0 and not meta['selected_query']
checks['camera_available']=meta['camera_available']
checks['resolution_378']=meta['raster']['shape_hw'][1]==378
with urllib.request.urlopen('http://localhost:8100',timeout=5) as r:checks['chooser_v5_link']=b'8107' in r.read()
with urllib.request.urlopen('http://localhost:8107/guide',timeout=5) as r:checks['guide_served']=r.status==200 and 'V1'.encode() in r.read()
Path(__file__).with_name('checks.json').write_text(json.dumps({'checks':checks,'actions':samples,'final_meta':meta},indent=2)+'\n')
print(checks);assert all(checks.values()),checks
