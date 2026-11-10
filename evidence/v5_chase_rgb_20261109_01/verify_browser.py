import asyncio,base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websockets
import numpy as np
OUT=Path(__file__).parent

def get(path):
    with urllib.request.urlopen('http://localhost:8108'+path,timeout=20) as r:return json.load(r)
def act(action,**values):
    req=urllib.request.Request('http://localhost:8108/api/action',data=json.dumps({'action':action,**values}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:assert r.status==200
async def main():
    act('pause');act('frame',frame=0)
    checks={};samples=[]
    with tempfile.TemporaryDirectory(prefix='v5-chase-rgb-') as profile:
        chrome=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1600,1100','--remote-debugging-port=9571','--user-data-dir='+profile,'http://localhost:8108'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen('http://localhost:9571/json',timeout=1) as r:targets=json.load(r)
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
                        reply=json.loads(await asyncio.wait_for(ws.recv(),30))
                        if reply.get('method')=='Runtime.exceptionThrown':errors.append(reply)
                        if reply.get('id')==ident:
                            if 'error' in reply:raise RuntimeError(reply['error'])
                            return reply.get('result',{})
                async def js(expr):
                    r=await call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
                    if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
                    return r['result'].get('value')
                async def wait(expr,seconds=20):
                    deadline=time.monotonic()+seconds
                    while time.monotonic()<deadline:
                        if await js(expr):return
                        await asyncio.sleep(.2)
                    raise TimeoutError(expr)
                async def picture(name):
                    r=await call('Page.captureScreenshot',{'format':'png'});(OUT/name).write_bytes(base64.b64decode(r['data']))
                async def sample(name):
                    r=await js("(()=>{const v=document.getElementById('native-rgb'),i=document.getElementById('rgb'),c=document.createElement('canvas');c.width=48;c.height=24;const x=c.getContext('2d'),source=window.smoothRGBVisible?v:i;let hash=null;try{x.drawImage(source,0,0,48,24);hash=x.getImageData(0,0,48,24).data.reduce((a,b)=>((a*31)^b)>>>0,0)}catch(e){}return {...window.vggtRGBDebug,hash,imageComplete:i.complete,imageWidth:i.naturalWidth}})()")
                    samples.append({'name':name,**r});return r
                await call('Runtime.enable');await call('Page.enable')
                await wait("window.vggtRGBDebug?.mode==='native'&&window.vggtRGBDebug.readyState>=2")
                act('frame',frame=20);await wait("Math.abs(window.vggtRGBDebug.videoTime-window.vggtRGBDebug.serverTime)<.15")
                await asyncio.sleep(.4);a=await sample('paused20')
                act('frame',frame=80);await asyncio.sleep(.8);b=await sample('paused80')
                checks['paused_rgb_seek']=b['videoTime']>a['videoTime']+3 and a['hash']!=b['hash']
                await js("document.getElementById('chase').click()")
                await wait("window.vggtRGBDebug?.viewMode==='chase'")
                c=get('/api/smooth');checks['chase_offset']=np.linalg.norm(np.array(c['view_camera_position'])-np.array(c['view_camera_source']))>0
                act('frame',frame=0);act('play');await asyncio.sleep(.7);a=await sample('play1a');p=get('/api/smooth')
                await asyncio.sleep(1.4);b=await sample('play1b');q=get('/api/smooth')
                checks['rgb_advances']=b['videoTime']>a['videoTime']+.5 and a['hash']!=b['hash']
                checks['chase_moves']=np.linalg.norm(np.array(q['view_camera_position'])-np.array(p['view_camera_position']))>1e-6
                before=get('/api/smooth');act('video_clock',seconds=0,generation=before['generation'],run=before['run']);after=get('/api/smooth')
                checks['late_video_cannot_rewind_server']=after['time']>=before['time']-.05
                await picture('chase_playing.png');act('pause')
                count=get('/api/frame')['frame_count'];act('frame',frame=count-1);act('play');await asyncio.sleep(.7);a=await sample('restart_a');await asyncio.sleep(1.2);b=await sample('restart_b');act('pause')
                checks['replay_rgb_advances']=b['videoTime']>a['videoTime']+.4 and b['videoTime']<5 and a['hash']!=b['hash']
                await js("document.getElementById('reset').click()")
                await wait("window.vggtRGBDebug?.viewMode==='rgb'");checks['reset_rgb_mode']=True
                await js("document.getElementById('free').click()")
                await wait("window.vggtRGBDebug?.viewMode==='free'");checks['free_mode']=True
                await js("document.getElementById('native-rgb').src='/missing-v5-video.mp4'")
                await wait("window.vggtRGBDebug?.mode==='frames'")
                act('frame',frame=60);await asyncio.sleep(.8);a=await sample('fallback60');act('frame',frame=140);await asyncio.sleep(.8);b=await sample('fallback140')
                checks['failed_video_rgb_fallback']=a['mode']==b['mode']=='frames' and a['hash']!=b['hash'] and b['imageWidth']>0
                await call('Page.reload');await wait("window.vggtRGBDebug?.mode==='native'")
                await js("document.getElementById('chase').click()")
                await wait("window.vggtRGBDebug?.viewMode==='chase'");await asyncio.sleep(.6)
                checks['chase_button_pressed']=await js("document.getElementById('chase').getAttribute('aria-pressed')==='true'")
                await picture('chase_paused.png');checks['javascript_exceptions']=not errors
                (OUT/'checks.json').write_text(json.dumps({'checks':checks,'samples':samples,'errors':errors},indent=2)+'\n');print(checks);assert all(checks.values()),checks
        finally:
            chrome.terminate()
            try:chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
asyncio.run(main())
