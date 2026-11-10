"""End-to-end Live V3 check with a real file picker and real inference/search.

Run against a local service; creates a NEW run and preserves all existing runs.
"""
import argparse
import asyncio
import base64
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

import websockets


async def inspect(url, video, output, frames, port):
    output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='vggt-v3-browser-') as profile:
        chrome=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless=new','--window-size=1600,1100','--use-angle=swiftshader','--enable-unsafe-swiftshader',
            '--no-first-run',f'--remote-debugging-port={port}',f'--user-data-dir={profile}',url],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1) as r:targets=json.load(r)
                    if targets:break
                except OSError:pass
                await asyncio.sleep(.2)
            target=next(t for t in targets if t['type']=='page')
            async with websockets.connect(target['webSocketDebuggerUrl'],max_size=32*1024**2) as ws:
                counter=0;errors=[]
                async def call(method,params=None):
                    nonlocal counter
                    counter+=1;ident=counter
                    await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
                    while True:
                        reply=json.loads(await asyncio.wait_for(ws.recv(),30))
                        if reply.get('method')=='Runtime.exceptionThrown':errors.append(reply)
                        if reply.get('id')==ident:
                            if 'error' in reply:raise RuntimeError(reply['error'])
                            return reply.get('result',{})
                async def evaluate(expression,context=None):
                    params={'expression':expression,'returnByValue':True,'awaitPromise':True}
                    if context:params['contextId']=context
                    reply=await call('Runtime.evaluate',params)
                    if 'exceptionDetails' in reply:raise RuntimeError(reply['exceptionDetails'])
                    return reply['result'].get('value')
                async def picture(name):
                    shot=await call('Page.captureScreenshot',{'format':'png'})
                    (output/name).write_bytes(base64.b64decode(shot['data']))
                async def contexts():
                    tree=(await call('Page.getFrameTree'))['frameTree']
                    frame=tree['childFrames'][0]
                    workspace=(await call('Page.createIsolatedWorld',{'frameId':frame['frame']['id'],'worldName':'workspace'}))['executionContextId']
                    gui=(await call('Page.createIsolatedWorld',{'frameId':frame['childFrames'][0]['frame']['id'],'worldName':'controls'}))['executionContextId']
                    return workspace,gui
                await call('Runtime.enable');await call('Page.enable')
                await call('Emulation.setDeviceMetricsOverride',{'width':1600,'height':1100,'deviceScaleFactor':1,'mobile':False})
                await asyncio.sleep(2)
                document=(await call('DOM.getDocument'))['root']['nodeId']
                node=(await call('DOM.querySelector',{'nodeId':document,'selector':'#file'}))['nodeId']
                await call('DOM.setFileInputFiles',{'nodeId':node,'files':[str(video.resolve())]})
                await evaluate(f"document.getElementById('submap').value=3;document.getElementById('maxframes').value={frames};document.getElementById('disparity').value=0;document.getElementById('loops').value=0")
                assert await evaluate("document.getElementById('name').textContent==="+json.dumps(video.name))
                await picture('selected.png')
                await evaluate("document.getElementById('start').click()")
                samples=[];checks={'file_picker':True};deadline=time.monotonic()+300;lastkey=None;live_captured=False
                while time.monotonic()<deadline:
                    await asyncio.sleep(1)
                    state=await evaluate("fetch('/api/live').then(r=>r.json())");job=state['job']
                    if not job:continue
                    key=(job['state'],job['map_frames'],job['road_frames'],job['viewer_revision'])
                    if key!=lastkey:
                        sample={k:job.get(k) for k in ('state','decoded_frames','map_frames','steps','road_frames','search_ready','viewer_ready','viewer_revision')}
                        sample['at']=time.time();samples.append(sample);print(json.dumps(sample),flush=True);lastkey=key
                        (output/'samples.json').write_text(json.dumps(samples,indent=2))
                    if job['viewer_ready'] and job['state'] not in ('completed','finalizing'):
                        try:
                            workspace,gui=await contexts()
                            await evaluate("[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes('Search'))?.click()",gui)
                            await asyncio.sleep(.3)
                            disabled=await evaluate("[...document.querySelectorAll('button')].find(e=>e.innerText==='Search')?.disabled",gui)
                            checks['search_disabled_during_generation']=disabled is True
                            meta=await evaluate("fetch('/api/frame').then(r=>r.json())",workspace)
                            if meta.get('road_points',0)>0:
                                checks['live_road_surface']=True
                                if not live_captured:await picture('live_road.png');live_captured=True
                            if not checks.get('live_views'):
                                checks['live_views']=await evaluate("['rgb','bev','camera-view'].every(id=>{const x=document.getElementById(id);return x?.complete&&x.naturalWidth>0})",workspace)
                        except (RuntimeError,KeyError):pass  # workspace reconnecting to the final run
                    if job['state']=='failed':raise RuntimeError(job['message'])
                    if job['state']=='completed':break
                else:raise TimeoutError('Map/road generation did not finish')
                await asyncio.sleep(5)
                workspace,gui=await contexts()
                checks['completed_counts']=job['map_frames']==frames and job['road_frames']==frames
                checks['search_ready']=job['search_ready']
                checks['v3_title']=await evaluate("document.title.includes('Live V3')",workspace)
                await evaluate("[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes('Search')).click()",gui)
                await asyncio.sleep(.5)
                checks['search_enabled_after_generation']=await evaluate("[...document.querySelectorAll('button')].find(e=>e.innerText==='Search')?.disabled===false",gui)
                checks['search_all_default']=await evaluate("[...document.querySelectorAll('input')].some(e=>e.value==='전구간 전수')",gui)
                await picture('completed.png')
                await evaluate("[...document.querySelectorAll('button')].find(e=>e.innerText==='Search').click()",gui)
                for _ in range(180):
                    await asyncio.sleep(1)
                    text=await evaluate('document.body.innerText',gui)
                    if '검색 실패' in text:raise RuntimeError(text)
                    if '검색 완료 · car' in text:break
                else:raise TimeoutError('Post-generation search did not complete')
                meta=await evaluate("fetch('/api/frame').then(r=>r.json())",workspace)
                checks['search_selected']=meta['selected_query']
                await picture('car_search.png')
                checks['javascript_exceptions']=len(errors)==0
                report={'url':url,'video':str(video.resolve()),'job':job,'checks':checks,'samples':samples,
                        'final_meta':meta,'javascript_exceptions':errors}
                (output/'browser.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
                print(json.dumps(checks,ensure_ascii=False),flush=True)
                assert all(checks.values()),checks
        finally:
            chrome.terminate()
            try:chrome.wait(timeout=10)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8103')
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frames',type=int,default=6)
    parser.add_argument('--cdp-port',type=int,default=9553)
    args=parser.parse_args()
    asyncio.run(inspect(args.url,args.video,args.output,args.frames,args.cdp_port))
