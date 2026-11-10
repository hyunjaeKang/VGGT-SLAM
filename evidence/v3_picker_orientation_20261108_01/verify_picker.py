import asyncio,json,tempfile,subprocess,urllib.request,time
from pathlib import Path
import websockets
async def main():
 with tempfile.TemporaryDirectory() as profile:
  p=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--no-first-run','--remote-debugging-port=9567',f'--user-data-dir={profile}','http://127.0.0.1:8103'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   await asyncio.sleep(3)
   t=next(x for x in json.load(urllib.request.urlopen('http://127.0.0.1:9567/json')) if x['type']=='page')
   async with websockets.connect(t['webSocketDebuggerUrl']) as ws:
    n=0;events=[]
    async def call(m,params={}):
     nonlocal n;n+=1;await ws.send(json.dumps(dict(id=n,method=m,params=params)))
     while True:
      r=json.loads(await ws.recv())
      if r.get('method')=='Page.fileChooserOpened':events.append(r)
      if r.get('id')==n:return r.get('result',r)
    async def ev(e):return (await call('Runtime.evaluate',{'expression':e,'awaitPromise':True,'returnByValue':True}))['result'].get('value')
    await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{'width':1600,'height':1100,'deviceScaleFactor':1,'mobile':False});await call('Page.setInterceptFileChooserDialog',{'enabled':True})
    await ev("(async()=>{window.realFetch=window.fetch;const state=await(await window.realFetch('/api/live')).json();state.job.state='road';window.fetch=(url,...args)=>url==='/api/live'?Promise.resolve(new Response(JSON.stringify(state),{headers:{'Content-Type':'application/json'}})):window.realFetch(url,...args);await poll();})()")
    h=await ev("(()=>{let r=document.getElementById('choose').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
    for typ in ['mousePressed','mouseReleased']:await call('Input.dispatchMouseEvent',{'type':typ,'x':h['x'],'y':h['y'],'button':'left','clickCount':1})
    await ev('1');assert events,'real click did not open chooser'
    node=events[0]['params']['backendNodeId'];video=Path('logs/demo_inputs/youtube_2t1i5LYoZXo_90s_20261106/clip.mp4').resolve()
    await call('DOM.setFileInputFiles',{'backendNodeId':node,'files':[str(video)]})
    report=await ev("({selected:document.getElementById('name').textContent,inputEnabled:!document.getElementById('file').disabled,buttonEnabled:!document.getElementById('choose').disabled,hint:document.getElementById('selection-hint').textContent,startDisabled:document.getElementById('start').disabled})")
    report['real_chooser_opened']=bool(events);print(json.dumps(report,ensure_ascii=False));assert report['selected']=='clip.mp4' and report['inputEnabled'] and report['startDisabled']
    folder=Path('evidence/v3_picker_orientation_20261108_01');folder.mkdir(exist_ok=True,parents=True);(folder/'picker_busy.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    tree=(await call('Page.getFrameTree'))['frameTree']
    workspace=tree['childFrames'][0]
    context=(await call('Page.createIsolatedWorld',{'frameId':workspace['frame']['id'],'worldName':'orientation'}))['executionContextId']
    gui=(await call('Page.createIsolatedWorld',{'frameId':workspace['childFrames'][0]['frame']['id'],'worldName':'gui'}))['executionContextId']
    await call('Runtime.evaluate',{'contextId':gui,'expression':"[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes('Map'))?.click()"})
    await asyncio.sleep(.5)
    await call('Runtime.evaluate',{'contextId':gui,'expression':"[...document.querySelectorAll('button')].find(e=>e.innerText==='Fit map')?.click()"})
    await asyncio.sleep(2)
    import base64
    shot=await call('Page.captureScreenshot',{'format':'png'})
    (folder/'free_upright.png').write_bytes(base64.b64decode(shot['data']))
    await call('Runtime.evaluate',{'contextId':context,'expression':"document.getElementById('reset').click()"})
  finally:p.terminate();p.wait()
asyncio.run(main())
