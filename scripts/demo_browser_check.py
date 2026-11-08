"""Inspect a running local demo viewer with an isolated headless Chrome."""
import argparse
import asyncio
import base64
import json
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets


async def inspect(url, port, output, switch_run=None, object_query=None, verify_playback=False, search_query=None, verify_resize=False):
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with tempfile.TemporaryDirectory(prefix="vggt-demo-chrome-") as profile:
        process = subprocess.Popen([chrome, "--headless=new", "--window-size=1440,1000", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-first-run",
                                    f"--remote-debugging-port={port}", f"--user-data-dir={profile}", url],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            targets = None
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                        targets = json.load(response)
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            if not targets:
                raise RuntimeError("Chrome debugging endpoint unavailable")
            target = next(item for item in targets if item["type"] == "page")
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024) as ws:
                counter = 0
                gui_context = None
                errors, sockets = [], []

                async def call(method, params=None):
                    nonlocal counter
                    counter += 1
                    request_id = counter
                    params = dict(params or {})
                    if method == 'Runtime.evaluate' and gui_context is not None and 'contextId' not in params:
                        params['contextId'] = gui_context
                    await ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(await asyncio.wait_for(ws.recv(), 30))
                        if response.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded"):
                            errors.append(response)
                        if response.get("method") == "Network.webSocketCreated":
                            sockets.append(response["params"].get("url"))
                        if response.get("id") == request_id:
                            if "error" in response:
                                raise RuntimeError(str(response["error"]))
                            return response.get("result", {})

                await call("Page.enable")
                await call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
                await call("Runtime.enable")
                await call("Network.enable")
                await call("Log.enable")
                browser_started = time.perf_counter()
                await call("Page.reload")
                await asyncio.sleep(8)
                first_render_seconds = time.perf_counter() - browser_started
                tree = (await call('Page.getFrameTree'))['frameTree']
                root_context = (await call('Page.createIsolatedWorld', {'frameId': tree['frame']['id'], 'worldName': 'demo-root'}))['executionContextId']
                if tree.get('childFrames'):
                    gui_context = (await call('Page.createIsolatedWorld', {'frameId': tree['childFrames'][0]['frame']['id'], 'worldName': 'demo-controls'}))['executionContextId']

                async def evaluate_root(expression):
                    answer = await call('Runtime.evaluate', {'expression': expression, 'returnByValue': True,
                                                             'contextId': root_context, 'awaitPromise': True})
                    if 'exceptionDetails' in answer:
                        raise RuntimeError(str(answer['exceptionDetails']))
                    return answer['result'].get('value')
                async def evaluate(expression):
                    answer = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    if "exceptionDetails" in answer:
                        raise RuntimeError(str(answer["exceptionDetails"]))
                    return answer["result"].get("value")

                async def wait_text(fragment, timeout=30):
                    deadline = time.perf_counter() + timeout
                    while time.perf_counter() < deadline:
                        if fragment in (await evaluate("document.body.innerText") or ""):
                            return True
                        await asyncio.sleep(.2)
                    return False

                if not await wait_text("displayed"):
                    raise TimeoutError("cached map status did not arrive")

                value = await call("Runtime.evaluate", {"expression": "JSON.stringify({title:document.title, text:document.body.innerText, inputs:Array.from(document.querySelectorAll('input')).map(e=>({type:e.type,value:e.value,min:e.min,max:e.max,html:e.outerHTML})), buttons:Array.from(document.querySelectorAll('button')).map(e=>({text:e.innerText,role:e.getAttribute('role')}))})", "returnByValue": True})
                snapshot = json.loads(value["result"]["value"])
                picture = await call("Page.captureScreenshot", {"format": "png"})
                output.mkdir(parents=True, exist_ok=False)
                (output / "initial.png").write_bytes(base64.b64decode(picture["data"]))
                interactions = {}
                if gui_context is not None:
                    interactions['full_height_controls'] = await evaluate_root("document.getElementById('viewer').getBoundingClientRect().height >= innerHeight-1 && !document.querySelector('.context')")
                    interactions['main_canvas_not_covered'] = await evaluate_root("(()=>{let f=document.getElementById('viewer'),d=f.contentDocument,v=d?.querySelector('[data-main-viewport]'),cards=document.querySelector('.views');if(!v)return false;let canvases=[...v.querySelectorAll('canvas')].filter(c=>c.getBoundingClientRect().width>0);return canvases.length>0&&canvases.every(c=>f.getBoundingClientRect().top+c.getBoundingClientRect().bottom<=cards.getBoundingClientRect().top+2)})()")
                    interactions['left_views_do_not_cover_controls'] = await evaluate_root("document.querySelector('.views').getBoundingClientRect().right <= innerWidth-parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sidebar'))+1")
                    interactions['main_rgb_bev'] = await evaluate_root("['rgb','bev','camera-view'].every(id=>{let e=document.getElementById(id);return e&&e.complete&&e.naturalWidth>0})")
                    interactions['default_rgb_camera'] = await evaluate_root("!document.getElementById('camera-view').hidden")
                    await evaluate_root("document.getElementById('free').click()")
                    await asyncio.sleep(2)
                    interactions['free_view'] = await evaluate_root("document.getElementById('camera-view').hidden")
                    await evaluate_root("document.getElementById('reset').click()")
                    await asyncio.sleep(2)
                    interactions['reset_rgb_camera'] = await evaluate_root("!document.getElementById('camera-view').hidden")
                    interactions['main_frame_matches'] = await evaluate_root("(async()=>{let d=await(await fetch('/api/frame')).json();return d.camera_available&&d.raster.shape_hw[1]/d.raster.shape_hw[0]===d.aspect})()")

                if verify_resize and gui_context is not None:
                    async def bounds():
                        return await evaluate_root("(()=>{let h=document.getElementById('height-split').getBoundingClientRect(),w=document.getElementById('width-split').getBoundingClientRect(),cards=document.querySelectorAll('.views .card');return {height:h.top+5,hx:h.x+h.width/2,wx:w.x+w.width/2,wy:w.y+w.height/2,rgb:cards[0].getBoundingClientRect().width,bev:cards[1].getBoundingClientRect().width,window:innerHeight}})()")

                    async def drag(x, y, target_x, target_y):
                        await call('Input.dispatchMouseEvent', {'type':'mouseMoved','x':x,'y':y})
                        await call('Input.dispatchMouseEvent', {'type':'mousePressed','x':x,'y':y,'button':'left','buttons':1,'pointerType':'mouse','clickCount':1})
                        await call('Input.dispatchMouseEvent', {'type':'mouseMoved','x':(x+target_x)/2,'y':(y+target_y)/2,'buttons':1})
                        await call('Input.dispatchMouseEvent', {'type':'mouseMoved','x':target_x,'y':target_y,'buttons':1})
                        await call('Input.dispatchMouseEvent', {'type':'mouseReleased','x':target_x,'y':target_y,'button':'left','clickCount':1})
                        await asyncio.sleep(.5)

                    original = await bounds()
                    await drag(original['hx'],original['height'],original['hx'],original['height']+100)
                    tall = await bounds()
                    interactions['resize_3d_height'] = tall['height'] > original['height']+60
                    await drag(tall['wx'],tall['wy'],tall['wx']-100,tall['wy'])
                    wide = await bounds()
                    interactions['resize_rgb_bev_width'] = wide['rgb'] < original['rgb']-60 and wide['bev'] > original['bev']+60
                    interactions['resize_no_overlap'] = await evaluate_root("(()=>{let f=document.getElementById('viewer'),v=f.contentDocument.querySelector('[data-main-viewport]');return [...v.querySelectorAll('canvas')].every(c=>c.getBoundingClientRect().bottom<=document.querySelector('.views').getBoundingClientRect().top+1)})()")
                    picture = await call('Page.captureScreenshot', {'format':'png'})
                    (output/'resized.png').write_bytes(base64.b64decode(picture['data']))
                    await call('Page.reload')
                    await asyncio.sleep(4)
                    tree = (await call('Page.getFrameTree'))['frameTree']
                    root_context = (await call('Page.createIsolatedWorld', {'frameId':tree['frame']['id'],'worldName':'demo-root'}))['executionContextId']
                    gui_context = (await call('Page.createIsolatedWorld', {'frameId':tree['childFrames'][0]['frame']['id'],'worldName':'demo-controls'}))['executionContextId']
                    restored = await bounds()
                    interactions['resize_persists_reload'] = abs(restored['height']-wide['height'])<2 and abs(restored['rgb']-wide['rgb'])<2
                    await evaluate_root("document.getElementById('width-split').focus()")
                    await call('Input.dispatchKeyEvent', {'type':'keyDown','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
                    await call('Input.dispatchKeyEvent', {'type':'keyUp','key':'ArrowRight','code':'ArrowRight','windowsVirtualKeyCode':39})
                    await asyncio.sleep(.3)
                    keyboard = await bounds()
                    interactions['resize_keyboard'] = keyboard['rgb'] > restored['rgb']+15
                    await drag(keyboard['hx'],keyboard['height'],keyboard['hx'],1)
                    minimum = await bounds()
                    await drag(minimum['wx'],minimum['wy'],1,minimum['wy'])
                    bounded = await bounds()
                    interactions['resize_minimum_sizes'] = 180<=bounded['height']<=190 and 118<=bounded['rgb']<=122 and bounded['bev']>=118
                    await evaluate_root("document.getElementById('layout-reset').click()")
                    await asyncio.sleep(.5)
                    reset_bounds = await bounds()
                    interactions['resize_reset'] = abs(reset_bounds['height']-original['height'])<2 and abs(reset_bounds['rgb']-original['rgb'])<2
                    picture = await call('Page.captureScreenshot', {'format':'png'})
                    (output/'layout_reset.png').write_bytes(base64.b64decode(picture['data']))
                    (output/'resize_geometry.json').write_text(json.dumps({'original':original,'resized':wide,'reloaded':restored,'minimum':bounded,'reset':reset_bounds},indent=2)+'\n')

                async def tab(label):
                    clicked = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('[role=tab]')].find(e=>e.innerText.includes({json.dumps(label)}));if(!e)return false;e.click();return true}})()")
                    await asyncio.sleep(.5)
                    return clicked

                async def text_input(old_value, new_value):
                    found = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('input')].find(x=>x.type==='text'&&x.value==={json.dumps(old_value)}); if(!e)return false; e.focus();e.select();return true}})()")
                    if not found:
                        return False
                    await call("Input.insertText", {"text": new_value})
                    await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    await call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    await asyncio.sleep(2)
                    return True

                numeric_values = await evaluate("JSON.stringify([...document.querySelectorAll('input[inputmode=numeric]')].map(e=>e.value))")
                numeric_values = json.loads(numeric_values or "[]")
                frame_value = numeric_values[0] if numeric_values else ""
                budget_value = numeric_values[1] if len(numeric_values) > 1 else ""
                page_text = await evaluate("document.body.innerText")
                playback = re.search(r"playback index\s+\d+/(\d+)", page_text)
                total_frames = int(playback.group(1)) if playback else None
                initial_points = re.search(r"displayed ([\d,]+) points", page_text)
                expected_points = min(50_000, int(initial_points.group(1).replace(",", ""))) if initial_points else 50_000
                if verify_playback:
                    async def click_button(label):
                        return await evaluate(f"(()=>{{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==={json.dumps(label)});if(!b||b.disabled)return false;b.click();return true}})()")

                    async def wait_frame(predicate):
                        deadline = time.perf_counter() + 20
                        while time.perf_counter() < deadline:
                            value = await evaluate("document.querySelector('input[inputmode=numeric]')?.value")
                            if value is not None and predicate(int(value)):
                                return int(value)
                            await asyncio.sleep(.2)
                        raise TimeoutError("playback frame did not advance")

                    assert await click_button("Play / Pause")
                    assert await wait_text("Playback: Playing")
                    restarted = await wait_frame(lambda value: 0 < value < total_frames - 1)
                    interactions["restart_from_end"] = True
                    assert await click_button("Pause playback")
                    assert await wait_text("Playback: Paused")
                    paused_frame = int(await evaluate("document.querySelector('input[inputmode=numeric]').value"))
                    await asyncio.sleep(3)
                    interactions["paused_frame_stable"] = paused_frame == int(await evaluate("document.querySelector('input[inputmode=numeric]').value"))
                    if gui_context is not None:
                        main = await evaluate_root("(async()=>await(await fetch('/api/frame')).json())()")
                        interactions['playback_rgb_bev_sync'] = main['frame_index'] == paused_frame
                        interactions['playback_camera_updates'] = main['raster']['shape_hw'][1]/main['raster']['shape_hw'][0] == main['aspect'] and main['camera_available']
                    assert await click_button("Play / Pause")
                    assert await wait_text("Playback: Playing")
                    resumed = await wait_frame(lambda value: value > paused_frame)
                    interactions["resume_advances"] = resumed > paused_frame
                    assert await click_button("Pause playback")
                    assert await wait_text("Playback: Paused")
                    interactions["playback_status_visible"] = True
                    frame_value = await evaluate("document.querySelector('input[inputmode=numeric]').value")
                    picture = await call("Page.captureScreenshot", {"format": "png"})
                    (output / "playback_paused.png").write_bytes(base64.b64decode(picture["data"]))
                if frame_value and total_frames:
                    interactions["rewind"] = await text_input(frame_value, "0")
                    interactions["rewind_visible"] = "playback index 1/" in await evaluate("document.body.innerText")
                    pressed = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Play / Pause');if(!b)return false;b.click();return true})()")
                    await asyncio.sleep(2)
                    if pressed:
                        await evaluate("[...document.querySelectorAll('button')].find(x=>x.innerText==='Play / Pause').click()")
                    interactions["play_pause"] = bool(pressed)
                    current_frame = await evaluate("document.querySelector('input[inputmode=numeric]')?.value")
                    interactions["end"] = await text_input(current_frame or "0", str(total_frames - 1))
                    interactions["end_visible"] = await wait_text(f"playback index {total_frames}/{total_frames}")
                if budget_value:
                    interactions["point_limit"] = await text_input(budget_value, "50000")
                    interactions["point_limit_visible"] = await wait_text(f"displayed {expected_points:,} points")
                if "Point size (점 크기 배율)" in page_text:
                    interactions["point_size_change"] = await text_input("1", "3")
                    interactions["point_size_visible"] = "3" in json.loads(await evaluate("JSON.stringify([...document.querySelectorAll('input[inputmode=numeric]')].map(e=>e.value))"))
                    picture = await call("Page.captureScreenshot", {"format": "png"})
                    (output / "point_size_3x.png").write_bytes(base64.b64decode(picture["data"]))
                    interactions["point_size_reset"] = await text_input("3", "1")
                async def choose(old_value, new_value):
                    clicked = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('input')].find(x=>x.type==='text'&&x.value==={json.dumps(old_value)});if(!e)return false;e.click();return true}})()")
                    if not clicked:
                        return False
                    await asyncio.sleep(0.5)
                    found = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.innerText.trim()==={json.dumps(new_value)});if(!e)return false;e.click();return true}})()")
                    await asyncio.sleep(3)
                    return bool(found and await evaluate(f"[...document.querySelectorAll('input')].some(x=>x.type==='text'&&x.value==={json.dumps(new_value)})"))

                studio = 'Map Studio' in page_text
                if studio:
                    interactions['bev_visible'] = 'BEV' in page_text and '미관측' in page_text
                    interactions['sky_available'] = '실제 skyseg 분할' in (await evaluate('document.body.textContent'))
                    async def toggle_sky():
                        return await evaluate("(()=>{const l=[...document.querySelectorAll('label')].find(e=>e.innerText==='Hide sky');if(!l)return false;l.click();return true})()")
                    interactions['sky_toggle_off'] = await toggle_sky()
                    await asyncio.sleep(2)
                    interactions['sky_original_state'] = '원본 비교' in (await evaluate('document.body.textContent'))
                    interactions['sky_toggle_on'] = await toggle_sky()
                    await asyncio.sleep(2)
                    interactions['sky_filtered_state'] = '하늘 제거 켜짐' in (await evaluate('document.body.textContent'))
                    interactions['inspect_tab'] = await tab('Inspect')
                interactions["before_toggle"] = await choose("after", "before")
                if interactions["before_toggle"]:
                    interactions["after_toggle"] = await choose("before", "after")
                if studio:
                    await tab('Map')
                interactions["fit_button"] = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Fit map');if(!b)return false;b.click();return true})()")
                if studio and (object_query or search_query):
                    interactions['search_tab'] = await tab('Search')
                if search_query:
                    interactions['query_input'] = await text_input('car', search_query)
                    interactions['search_start'] = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Search');if(!b||b.disabled)return false;b.click();return true})()")
                    interactions['search_completed'] = await wait_text(f'검색 완료 · {search_query}', timeout=180)
                    if not interactions['search_completed']:
                        raise RuntimeError(await evaluate('document.body.innerText'))
                    interactions['query_result_visible'] = await wait_text('valid 3D boxes')
                    picture = await call('Page.captureScreenshot', {'format': 'png'})
                    (output / 'search_result.png').write_bytes(base64.b64decode(picture['data']))
                if object_query:
                    current_query = await evaluate("[...document.querySelectorAll('input')].find(x=>x.type==='text'&&(x.value.startsWith('query_')||x.value.includes('개 ·')||x.value.includes('3D관측')))?.value")
                    interactions["object_select"] = await choose(current_query or "None", object_query)
                    object_text = await evaluate("document.body.innerText")
                    count = re.search(r"valid 3D boxes (\d+)", object_text)
                    interactions["object_box_count"] = int(count.group(1)) if count else 0
                    interactions["object_boxes_visible"] = bool(count and int(count.group(1)) > 0)
                    if gui_context is not None:
                        await evaluate_root("document.getElementById('reset').click()")
                        await asyncio.sleep(2)
                        interactions['query_rgb_camera_reset'] = await evaluate_root("!document.getElementById('camera-view').hidden")
                    picture = await call("Page.captureScreenshot", {"format": "png"})
                    (output / "object_boxes.png").write_bytes(base64.b64decode(picture["data"]))
                    interactions["object_clear"] = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Clear object boxes');if(!b)return false;b.click();return true})()")
                    await asyncio.sleep(2)
                    interactions["object_clear_visible"] = "No saved object query selected." in await evaluate("document.body.innerText")
                    interactions["object_reopen"] = await choose("None", object_query)
                if switch_run:
                    current_run = await evaluate("document.querySelector('input[aria-haspopup=listbox]')?.value")
                    interactions["run_switch"] = await choose(current_run, switch_run)
                    if interactions["run_switch"]:
                        interactions["cached_state"] = "saved PCD" in await evaluate("document.body.innerText")
                await asyncio.sleep(1)
                picture = await call("Page.captureScreenshot", {"format": "png"})
                (output / "after_controls.png").write_bytes(base64.b64decode(picture["data"]))
                result = {"url": url, "dom": snapshot, "first_render_seconds": first_render_seconds,
                          "timing_method": "fixed 8-second wait then status readiness; not precise first-draw timing",
                          "interactions": interactions, "websockets": sockets,
                          "websocket_worker_connected": any("Connected! ws://" in item.get("params", {}).get("entry", {}).get("text", "") for item in errors),
                          "javascript_exceptions": sum(item.get("method") == "Runtime.exceptionThrown" for item in errors),
                          "browser_events": errors}
                (output / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--debug-port", type=int, default=9226)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--switch-run", help="optional second run name to select after the initial render")
    parser.add_argument("--object-query", help="saved query ID to select, clear and reopen")
    parser.add_argument("--verify-playback", action="store_true")
    parser.add_argument("--verify-resize", action="store_true")
    parser.add_argument("--search-query", help="run an actual cached PE/SAM3 search from the UI")
    args = parser.parse_args()
    asyncio.run(inspect(args.url, args.debug_port, args.output, args.switch_run, args.object_query, args.verify_playback, args.search_query, args.verify_resize))


if __name__ == "__main__":
    main()
