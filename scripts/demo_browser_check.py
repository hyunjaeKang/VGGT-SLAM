"""Inspect a running local demo viewer with an isolated headless Chrome."""
import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets


async def inspect(url, port, output):
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    with tempfile.TemporaryDirectory(prefix="vggt-demo-chrome-") as profile:
        process = subprocess.Popen([chrome, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-first-run",
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
                errors, sockets = [], []

                async def call(method, params=None):
                    nonlocal counter
                    counter += 1
                    request_id = counter
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
                await call("Runtime.enable")
                await call("Network.enable")
                await call("Log.enable")
                await call("Page.reload")
                await asyncio.sleep(8)
                async def evaluate(expression):
                    answer = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    if "exceptionDetails" in answer:
                        raise RuntimeError(str(answer["exceptionDetails"]))
                    return answer["result"].get("value")

                value = await call("Runtime.evaluate", {"expression": "JSON.stringify({title:document.title, text:document.body.innerText, inputs:Array.from(document.querySelectorAll('input')).map(e=>({type:e.type,value:e.value,min:e.min,max:e.max,html:e.outerHTML})), buttons:Array.from(document.querySelectorAll('button')).map(e=>({text:e.innerText,role:e.getAttribute('role')}))})", "returnByValue": True})
                snapshot = json.loads(value["result"]["value"])
                picture = await call("Page.captureScreenshot", {"format": "png"})
                output.mkdir(parents=True, exist_ok=False)
                (output / "initial.png").write_bytes(base64.b64decode(picture["data"]))
                interactions = {}

                async def text_input(old_value, new_value):
                    found = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('input')].find(x=>x.type==='text'&&x.value==={json.dumps(old_value)}); if(!e)return false; e.focus();e.select();return true}})()")
                    if not found:
                        return False
                    await call("Input.insertText", {"text": new_value})
                    await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    await call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                    await asyncio.sleep(2)
                    return True

                if await text_input("239", "0"):
                    interactions["rewind"] = "frame ID 508" in await evaluate("document.body.innerText")
                    pressed = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Play / Pause');if(!b)return false;b.click();return true})()")
                    await asyncio.sleep(2)
                    if pressed:
                        await evaluate("[...document.querySelectorAll('button')].find(x=>x.innerText==='Play / Pause').click()")
                    current_frame = await evaluate("document.querySelector('input[inputmode=numeric]')?.value")
                    interactions["play_pause"] = bool(pressed and current_frame and int(current_frame) > 0)
                    await text_input(current_frame or "0", "239")
                    interactions["end"] = "frame ID 1855" in await evaluate("document.body.innerText")
                if await text_input("300000", "50000"):
                    interactions["point_limit"] = "displayed 50,000 points" in await evaluate("document.body.innerText")
                async def choose(old_value, new_value):
                    clicked = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('input')].find(x=>x.type==='text'&&x.value==={json.dumps(old_value)});if(!e)return false;e.click();return true}})()")
                    if not clicked:
                        return False
                    await asyncio.sleep(0.5)
                    found = await evaluate(f"(()=>{{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.innerText.trim()==={json.dumps(new_value)});if(!e)return false;e.click();return true}})()")
                    await asyncio.sleep(3)
                    return bool(found and await evaluate(f"[...document.querySelectorAll('input')].some(x=>x.type==='text'&&x.value==={json.dumps(new_value)})"))

                interactions["before_toggle"] = await choose("after", "before")
                if interactions["before_toggle"]:
                    interactions["after_toggle"] = await choose("before", "after")
                interactions["fit_button"] = await evaluate("(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText==='Fit map');if(!b)return false;b.click();return true})()")
                interactions["run_switch"] = await choose("s03_kitti_loop_on_20261031_01", "pandaset003_existing_20261030")
                if interactions["run_switch"]:
                    interactions["cached_state"] = "saved PCD" in await evaluate("document.body.innerText")
                    interactions["large_run_switch"] = await choose("pandaset003_existing_20261030", "kitti360_existing_20261030")
                    if interactions["large_run_switch"]:
                        await text_input("50000", "300000")
                        await asyncio.sleep(3)
                        text = await evaluate("document.body.innerText")
                        interactions["large_pcd_300k"] = "displayed 300,000 points" in text and "212,204,997" in text
                await asyncio.sleep(1)
                picture = await call("Page.captureScreenshot", {"format": "png"})
                (output / "after_controls.png").write_bytes(base64.b64decode(picture["data"]))
                result = {"url": url, "dom": snapshot, "interactions": interactions, "websockets": sockets, "browser_events": errors}
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
    args = parser.parse_args()
    asyncio.run(inspect(args.url, args.debug_port, args.output))


if __name__ == "__main__":
    main()
