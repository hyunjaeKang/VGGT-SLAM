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
    checks={}
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
                checks['model_selector']=await js("document.body.innerText.includes('Search model')",ctx)
                checks['sam3_help']=await js("document.body.innerText.includes('자유 텍스트 분할')",ctx)
                checks['scope']=await js("document.body.innerText.includes('Search scope')",ctx)
                await js("[...document.querySelectorAll('input')].find(e=>e.value==='SAM3').click()",ctx)
                await asyncio.sleep(.3)
                checks['all_models']=await js("['SAM3','RF-DETR','YOLOE','YOLO26','YOLO11'].every(n=>document.body.innerText.includes(n))",ctx)
                await js("[...document.querySelectorAll('[role=option]')].find(e=>e.innerText==='YOLO26').click()",ctx)
                await asyncio.sleep(.6)
                checks['yolo_help']=await js("document.body.innerText.includes('YOLO26-seg') && document.body.innerText.includes('COCO')",ctx)
                await shot('search_models.png')
                checks['no_js_errors']=not errors
                (OUT/'browser_checks.json').write_text(json.dumps(checks,indent=2))
                print(checks)
                assert all(checks.values()),checks
        finally:
            process.terminate();process.wait(timeout=10)
asyncio.run(main())
