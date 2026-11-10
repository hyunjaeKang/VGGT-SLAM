import asyncio,base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websockets
out=Path(__file__).parent

def read(path):
    with urllib.request.urlopen('http://localhost:8108'+path,timeout=20) as r:return json.load(r)
def action(name,**extra):
    req=urllib.request.Request('http://localhost:8108/api/action',data=json.dumps({'action':name,**extra}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.status
async def main():
    meta=read('/api/frame');action('frame',frame=meta['frame_count']-1);action('zoom_reset')
    with tempfile.TemporaryDirectory(prefix='v5-quality-review-') as profile:
        process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1600,1100','--remote-debugging-port=9569','--user-data-dir='+profile,'http://localhost:8108'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen('http://localhost:9569/json',timeout=1) as r:targets=json.load(r)
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
                await call('Runtime.enable');await call('Page.enable');await asyncio.sleep(6)
                tree=(await call('Page.getFrameTree'))['frameTree'];ctx=(await call('Page.createIsolatedWorld',{'frameId':tree['childFrames'][0]['frame']['id'],'worldName':'controls'}))['executionContextId']
                r=await call('Runtime.evaluate',{'expression':"[...document.querySelectorAll('button')].find(e=>e.innerText==='Fit map').click()",'contextId':ctx,'returnByValue':True})
                if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
                await asyncio.sleep(2)
                shot=await call('Page.captureScreenshot',{'format':'png'});(out/'completed_overview.png').write_bytes(base64.b64decode(shot['data']))
                meta=read('/api/frame');checks={'last_source_frame':meta['source_frame_id']=='225','geometry_only':meta['viewer_version']=='slam-v5','camera_available':meta['camera_available'],'overview':not meta['follow_rgb'],'no_js_exceptions':not errors}
                (out/'browser_checks.json').write_text(json.dumps({'checks':checks,'meta':meta,'errors':errors},indent=2)+'\n');print(checks);assert all(checks.values())
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
asyncio.run(main())
