import asyncio,base64,json,subprocess,tempfile,time,urllib.request
from pathlib import Path
import websockets
OUT=Path(__file__).parent
STANDALONE='file:///Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map/web_app/standalone/TerraScene_Demo_UI_2026-11-04.html'
RUN=Path('logs/demo_runs/video_20261109T213652_654365000')
def get(path):
    with urllib.request.urlopen('file:///Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map/web_app/dist/index.html'+path,timeout=30) as r:return json.load(r)
def act(action,**values):
    req=urllib.request.Request('http://localhost:8108/api/action',data=json.dumps({'action':action,**values}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r:assert r.status==200
async def main():
    checks={};existing=set((RUN/'evidence/query_jobs').glob('search_*'))
    with tempfile.TemporaryDirectory(prefix='v5-search-',ignore_cleanup_errors=True) as profile:
        process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--use-angle=swiftshader','--enable-unsafe-swiftshader','--window-size=1600,1100','--remote-debugging-port=9573','--user-data-dir='+profile,'file:///Users/hyunjae.kang/2026_opensrc/VGGT_SLAM/vggt_slam_map/web_app/dist/index.html'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
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
                checks['loaded']=await js('!!window.TerraScenePreview')
                checks['desktop_no_overflow']=await js('document.documentElement.scrollWidth<=innerWidth+1')
                checks['english_korean_labels']=await js("['stat-route','route-text','unknown-label','data-notice'].every(id=>/[A-Za-z]/.test(document.getElementById(id).textContent)&&/[가-힣]/.test(document.getElementById(id).textContent))")
                await shot('desktop.png')
                await js("document.getElementById('search').value='나무';document.getElementById('search').dispatchEvent(new Event('input'))")
                checks['korean_object_search']=await js("document.getElementById('object-list').innerText.includes('Tree cluster / 나무 군집')")
                await js("document.getElementById('help').click()")
                checks['bilingual_help']=await js("document.getElementById('modal-content').innerText.includes('Glossary / 용어 설명')")
                await shot('help.png')
                await js("document.getElementById('modal-close').click();document.getElementById('scenario').value='blocked';document.getElementById('scenario').dispatchEvent(new Event('change'))")
                checks['bilingual_error']=await js("/[가-힣]/.test(document.getElementById('route-detail').textContent) && /[A-Za-z]/.test(document.getElementById('route-detail').textContent)")
                await js("document.getElementById('export').click()")
                checks['bilingual_export']=await js("document.getElementById('modal-content').innerText.includes('예시 결과 내보내기') && document.getElementById('modal-content').innerText.includes('Export sample results')")
                await js("document.getElementById('modal-close').click()")
                await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
                await asyncio.sleep(.5)
                checks['mobile_no_overflow']=await js('document.documentElement.scrollWidth<=innerWidth+1')
                await shot('mobile.png')
                audit=await js("(()=>{const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),result=[];let node;while(node=walker.nextNode()){let text=node.textContent.trim(),parent=node.parentElement;if(parent&&!parent.closest('script,style,svg')&&parent.getBoundingClientRect().width&&/[A-Za-z]{3}/.test(text)&&!/[가-힣]/.test(text)&&!['terra','scene','TS'].includes(text)&&!/^[0-9., :m²×−-]+$/.test(text))result.push(text)}return [...new Set(result)]})()")
                (OUT/'visible_text_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
                await call('Page.navigate',{'url':STANDALONE})
                await asyncio.sleep(2)
                checks['standalone_loaded']=await js("!!window.TerraScenePreview && document.getElementById('stat-route').textContent.includes('연결됨')")
                checks['no_js_errors']=not errors
                (OUT/'checks.json').write_text(json.dumps(checks,indent=2));print(checks);print('Visible English-only text:',audit)
                assert all(checks.values()),checks
        finally:
            process.terminate();process.wait(timeout=10)
asyncio.run(main())
