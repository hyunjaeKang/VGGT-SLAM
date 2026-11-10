import asyncio,base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websockets
OUT=Path(__file__).parent
RUN=Path('logs/demo_runs/video_20261109T193118_668535000')
def get(path):
    with urllib.request.urlopen('http://localhost:8108'+path,timeout=30) as r:return json.load(r)
def act(action,**values):
    req=urllib.request.Request('http://localhost:8108/api/action',data=json.dumps({'action':action,**values}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:assert r.status==200
async def main():
    act('pause');act('frame',frame=141)
    with urllib.request.urlopen('http://localhost:8108/rgb.jpg',timeout=20) as r:(OUT/'rgb_before.jpg').write_bytes(r.read())
    checks={};existing=set((RUN/'evidence/query_jobs').glob('search_*'))
    with tempfile.TemporaryDirectory(prefix='v5-search-') as profile:
        process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1600,1100','--remote-debugging-port=9573','--user-data-dir='+profile,'http://localhost:8108'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen('http://localhost:9573/json',timeout=1) as r:targets=json.load(r)
                    if targets:break
                except OSError:pass
                await asyncio.sleep(.2)
            target=next(t for t in targets if t['type']=='page')
            async with websockets.connect(target['webSocketDebuggerUrl'],max_size=32*1024**2) as ws:
                serial=0;errors=[]
                async def call(method,params=None):
                    nonlocal serial
                    serial+=1;ident=serial;await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
                    while True:
                        r=json.loads(await asyncio.wait_for(ws.recv(),30))
                        if r.get('method')=='Runtime.exceptionThrown':errors.append(r)
                        if r.get('id')==ident:
                            if 'error' in r:raise RuntimeError(r['error'])
                            return r.get('result',{})
                async def js(expr,context=None):
                    params={'expression':expr,'returnByValue':True,'awaitPromise':True}
                    if context:params['contextId']=context
                    r=await call('Runtime.evaluate',params)
                    if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
                    return r['result'].get('value')
                async def shot(name):
                    r=await call('Page.captureScreenshot',{'format':'png'});(OUT/name).write_bytes(base64.b64decode(r['data']))
                await call('Runtime.enable');await call('Page.enable');await asyncio.sleep(5)
                tree=(await call('Page.getFrameTree'))['frameTree'];ctx=(await call('Page.createIsolatedWorld',{'frameId':tree['childFrames'][0]['frame']['id'],'worldName':'controls'}))['executionContextId']
                checks['search_tab']=await js("[...document.querySelectorAll('[role=tab]')].some(e=>e.innerText.includes('Search'))",ctx)
                await js("[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes('Search')).click()",ctx)
                await asyncio.sleep(.3)
                checks['search_enabled']=await js("![...document.querySelectorAll('button')].find(e=>e.innerText==='Search').disabled",ctx)
                await js("[...document.querySelectorAll('button')].find(e=>e.innerText==='Search').click()",ctx)
                job=None;deadline=time.monotonic()+300
                while time.monotonic()<deadline:
                    found=set((RUN/'evidence/query_jobs').glob('search_*'))-existing
                    if found:job=sorted(found)[-1]
                    if job and (job/'status.json').exists():
                        status=json.loads((job/'status.json').read_text())
                        if status['state']=='failed':raise RuntimeError(status)
                        if status['state']=='completed':break
                    await asyncio.sleep(1)
                else:raise TimeoutError('Actual SAM3 search did not finish')
                (OUT/'search_status.json').write_text(json.dumps(status,indent=2)+'\n')
                checks['actual_search_completed']=status['state']=='completed'
                checks['current_scope_one_frame']=status['attempted_frames']==1
                result=json.loads((RUN/status['result']).read_text())
                checks['new_frame_not_old_query_reused']=result['search']['current_frame_index']==141
                checks['valid_3d_boxes']=status['valid_boxes']>0
                for _ in range(40):
                    meta=get('/api/frame')
                    if meta.get('selected_query'):break
                    await asyncio.sleep(.3)
                checks['result_selected']=meta['selected_query']
                checks['rgb_mask_and_boxes_on']=meta['mask_rgb'] and meta['box_rgb']
                for _ in range(40):
                    debug=await js('window.vggtRGBDebug')
                    if debug and debug['mode']=='frames':break
                    await asyncio.sleep(.2)
                checks['rgb_shows_query_image']=debug['mode']=='frames'
                pixels_match=False
                for _ in range(60):
                    pixels_match=await js("(async()=>{const actual=document.getElementById('rgb'),expected=new Image();expected.src='/rgb.jpg?audit='+Date.now();await expected.decode();if(!actual.complete||actual.naturalWidth!==expected.naturalWidth)return false;const a=document.createElement('canvas'),b=document.createElement('canvas');a.width=b.width=expected.naturalWidth;a.height=b.height=expected.naturalHeight;const x=a.getContext('2d'),y=b.getContext('2d');x.drawImage(actual,0,0);y.drawImage(expected,0,0);const p=x.getImageData(0,0,a.width,a.height).data,q=y.getImageData(0,0,b.width,b.height).data;return p.every((v,i)=>v===q[i])})()")
                    if pixels_match:break
                    await asyncio.sleep(.2)
                checks['displayed_rgb_matches_annotated_pixels']=pixels_match
                with urllib.request.urlopen('http://localhost:8108/rgb.jpg',timeout=20) as r:(OUT/'rgb_query.jpg').write_bytes(r.read())
                checks['rgb_overlay_changed']=(OUT/'rgb_before.jpg').read_bytes()!=(OUT/'rgb_query.jpg').read_bytes()
                checks['mask_buttons_visible']=await js("['mask-3d','mask-rgb','box-rgb','mask-bev','box-bev'].every(id=>getComputedStyle(document.getElementById(id)).display!=='none')")
                await shot('search_result.png')
                act('box_bev');act('mask_bev');meta=get('/api/frame');checks['bev_box_mask_toggles']=meta['box_bev'] and meta['mask_bev']
                act('box_rgb');act('mask_rgb');meta=get('/api/frame');checks['rgb_toggles_off']=not meta['box_rgb'] and not meta['mask_rgb']
                act('box_rgb');act('mask_rgb')
                await js("[...document.querySelectorAll('button')].find(e=>e.innerText==='Clear object boxes').click()",ctx)
                for _ in range(40):
                    if not get('/api/frame')['selected_query']:break
                    await asyncio.sleep(.2)
                meta=get('/api/frame');checks['clear_removes_selected_overlay']=not meta['selected_query']
                checks['js_exceptions']=not errors
                (OUT/'checks.json').write_text(json.dumps({'checks':checks,'query_job':str(job),'status':status,'final_meta':meta,'errors':errors},indent=2)+'\n')
                print(checks);assert all(checks.values()),checks
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
asyncio.run(main())
