import asyncio,base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websockets
OUT=Path(__file__).parent
RUN=Path('logs/demo_runs/video_20261109T213652_654365000')
def get(path):
    with urllib.request.urlopen('http://localhost:8108'+path,timeout=30) as r:return json.load(r)
def act(action,**values):
    req=urllib.request.Request('http://localhost:8108/api/action',data=json.dumps({'action':action,**values}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:assert r.status==200
async def main():
    checks={};existing=set((RUN/'evidence/query_jobs').glob('search_*'))
    with tempfile.TemporaryDirectory(prefix='v5-search-',ignore_cleanup_errors=True) as profile:
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
                await js("localStorage.removeItem('vggt-v5-top-menu-hidden')")
                await call('Page.reload');await asyncio.sleep(3)
                checks['initial_shown']=await js("!document.getElementById('top-menu').hidden")
                await js("document.getElementById('top-menu-toggle').click()")
                checks['hidden']=await js("getComputedStyle(document.getElementById('top-menu')).display==='none'")
                checks['restore_button_visible']=await js("document.getElementById('top-menu-toggle').getBoundingClientRect().width>0 && document.getElementById('top-menu-toggle').textContent.includes('보이기')")
                checks['views_remain_visible']=await js("document.getElementById('rgb').getBoundingClientRect().width>0 && document.getElementById('bev').getBoundingClientRect().width>0")
                await shot('menu_hidden.png')
                await call('Page.reload');await asyncio.sleep(3)
                checks['persists_reload']=await js("document.getElementById('top-menu').hidden")
                await js("document.getElementById('top-menu-toggle').click()")
                checks['restored']=await js("!document.getElementById('top-menu').hidden && document.getElementById('top-menu-toggle').getAttribute('aria-expanded')==='true'")
                await shot('menu_shown.png')
                checks['no_js_errors']=not errors
                (OUT/'checks.json').write_text(json.dumps(checks,indent=2));print(checks)
                assert all(checks.values()),checks
        finally:
            process.terminate();process.wait(timeout=10)
asyncio.run(main())
