import asyncio,base64,json,subprocess,tempfile,urllib.request
from pathlib import Path
import websockets
async def main():
 folder=Path('evidence/plan_review_20261108_01');folder.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='vggt-plan-browser-') as profile:
  browser=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--disable-gpu','--remote-debugging-port=9571',f'--user-data-dir={profile}',Path('26.11.09.VGGT_SLAM.Plan.html').resolve().as_uri()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for _ in range(50):
    try:
     targets=json.load(urllib.request.urlopen('http://127.0.0.1:9571/json',timeout=1));break
    except OSError:await asyncio.sleep(.1)
   target=next(t for t in targets if t['type']=='page')
   async with websockets.connect(target['webSocketDebuggerUrl'],max_size=32*1024**2) as ws:
    n=0;errors=[]
    async def call(method,params=None):
     nonlocal n;n+=1;await ws.send(json.dumps(dict(id=n,method=method,params=params or {})))
     while True:
      d=json.loads(await ws.recv())
      if d.get('method')=='Runtime.exceptionThrown':errors.append(d)
      if d.get('id')==n:
       if 'error'in d:raise RuntimeError(d['error'])
       return d.get('result',{})
    async def ev(expression):
     d=await call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
     if 'exceptionDetails'in d:raise RuntimeError(d['exceptionDetails'])
     return d['result'].get('value')
    async def shot(name):
     d=await call('Page.captureScreenshot',{'format':'png'});(folder/name).write_bytes(base64.b64decode(d['data']))
    await call('Runtime.enable');await call('Page.enable')
    await call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
    await asyncio.sleep(.5)
    checks={}
    checks['source_rows']=await ev("document.querySelectorAll('#source-table tbody tr').length===41")
    checks['desktop_no_horizontal_overflow']=await ev('document.documentElement.scrollWidth<=innerWidth+1')
    checks['calculator_initialized']=await ev("document.getElementById('budget-result').textContent.includes('독립 worker')")
    await shot('desktop.png')
    await ev("document.querySelector('[data-filter=fast]').click()")
    checks['model_filter']=await ev("(()=>{let n=[...document.querySelectorAll('#model-table tbody tr')].filter(e=>!e.classList.contains('hidden')).length;return n>0&&n<16})()")
    await ev("document.querySelector('[data-filter=all]').click();document.getElementById('geometry-ms').value=120000;document.getElementById('geometry-ms').dispatchEvent(new Event('input'))")
    checks['calculator_overload_warning']=await ev("document.getElementById('budget-result').textContent.includes('지속 처리 예산 초과')")
    await ev("document.getElementById('geometry-ms').value=2500;document.getElementById('geometry-ms').dispatchEvent(new Event('input'));document.getElementById('source-search').value='SAM';document.getElementById('source-search').dispatchEvent(new Event('input'))")
    checks['source_search']=await ev("(()=>{const n=[...document.querySelectorAll('#source-table tbody tr')].filter(e=>!e.classList.contains('hidden')).length;return n>1&&n<41})()")
    await ev("document.getElementById('source-search').value='';document.getElementById('source-search').dispatchEvent(new Event('input'));document.getElementById('architecture').scrollIntoView()")
    await shot('architecture.png')
    await call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
    await ev('window.scrollTo(0,0)');await asyncio.sleep(.1)
    checks['mobile_no_horizontal_overflow']=await ev('document.documentElement.scrollWidth<=innerWidth+1')
    await shot('mobile.png')
    checks['javascript_exceptions']=len(errors)==0
    report={'checks':checks,'errors':errors,'file':str(Path('26.11.09.VGGT_SLAM.Plan.html').resolve())}
    (folder/'validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps(checks));assert all(checks.values()),report
  finally:
   browser.terminate()
   try:browser.wait(timeout=5)
   except subprocess.TimeoutExpired:browser.kill();browser.wait()
asyncio.run(main())
