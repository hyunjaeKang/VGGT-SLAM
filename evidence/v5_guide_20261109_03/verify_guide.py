import asyncio,base64,json,subprocess,tempfile,urllib.request
from pathlib import Path
import websockets

async def main():
    out=Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='v5-guide-') as profile:
        chrome=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--disable-gpu','--no-first-run','--window-size=1440,1000','--remote-debugging-port=9568','--user-data-dir='+profile,'http://localhost:8107/guide'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen('http://localhost:9568/json',timeout=1) as r:targets=json.load(r)
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
                        r=json.loads(await asyncio.wait_for(ws.recv(),20))
                        if r.get('method')=='Runtime.exceptionThrown':errors.append(r)
                        if r.get('id')==ident:
                            if 'error' in r:raise RuntimeError(r['error'])
                            return r.get('result',{})
                async def js(expr):
                    r=await call('Runtime.evaluate',{'expression':expr,'returnByValue':True})
                    if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
                    return r['result'].get('value')
                await call('Runtime.enable');await call('Page.enable');await asyncio.sleep(2)
                checks={}
                checks['all_five_versions']=await js("document.querySelectorAll('.version').length===5")
                checks['local_anchor_links']=await js("[...document.querySelectorAll('a[href^=\"#\"]')].every(a=>document.getElementById(a.hash.slice(1)))")
                await js("document.querySelector('[data-goal=build]').click()")
                checks['build_filter']=await js("document.querySelectorAll('.version:not([hidden])').length===3")
                await js("document.querySelector('[data-goal=watch]').click()")
                checks['watch_filter']=await js("document.querySelectorAll('.version:not([hidden])').length===2")
                await js("document.querySelector('[data-goal=all]').click()")
                await js("[...document.querySelectorAll('summary')].find(e=>e.textContent.includes('V4')).click()")
                checks['commands']=await js("document.body.innerText.includes('demo.py live5')&&document.body.innerText.includes('demo.py live4')")
                shot=await call('Page.captureScreenshot',{'format':'png'});(out/'desktop.png').write_bytes(base64.b64decode(shot['data']))
                await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
                checks['mobile_no_overflow']=await js('document.documentElement.scrollWidth<=innerWidth')
                shot=await call('Page.captureScreenshot',{'format':'png'});(out/'mobile.png').write_bytes(base64.b64decode(shot['data']))
                await call('Emulation.clearDeviceMetricsOverride')
                await js("document.querySelectorAll('details').forEach(d=>d.open=true)")
                pdf=await call('Page.printToPDF',{'printBackground':False,'paperWidth':8.27,'paperHeight':11.69,'marginTop':.5,'marginBottom':.5,'marginLeft':.5,'marginRight':.5,'displayHeaderFooter':False})
                Path('docs/USER_GUIDE.pdf').write_bytes(base64.b64decode(pdf['data']))
                checks['javascript_exceptions']=not errors
                (out/'checks.json').write_text(json.dumps({'checks':checks,'errors':errors},indent=2)+'\n');print(checks)
                assert all(checks.values()),checks
        finally:
            chrome.terminate()
            try:chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait()

asyncio.run(main())
