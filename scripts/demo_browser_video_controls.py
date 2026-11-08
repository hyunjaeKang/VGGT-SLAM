"""Drive real live-video Viser buttons through an isolated Chrome instance."""

import argparse
import asyncio
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

import websockets


async def inspect(url, port, output, object_search=False, verify_bev=False):
    output.mkdir(parents=True, exist_ok=False)
    result = {"url": url, "actions": {}, "javascript_exceptions": []}
    with tempfile.TemporaryDirectory(prefix="vggt-video-chrome-") as profile:
        process = subprocess.Popen(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-first-run",
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
            target = next(item for item in targets if item["type"] == "page")
            async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None) as ws:
                serial = 0

                async def call(method, params=None):
                    nonlocal serial
                    serial += 1
                    request_id = serial
                    await ws.send(json.dumps({"id": serial, "method": method, "params": params or {}}))
                    while True:
                        message = json.loads(await asyncio.wait_for(ws.recv(), 30))
                        if message.get("method") == "Runtime.exceptionThrown":
                            result["javascript_exceptions"].append(message)
                        if message.get("id") == request_id:
                            if "error" in message:
                                raise RuntimeError(message["error"])
                            return message.get("result", {})

                async def evaluate(expression):
                    value = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    return value.get("result", {}).get("value")

                async def state():
                    text = await evaluate("document.body.innerText") or ""
                    match = re.search(r"Video state: (\w+)\s*·\s*decoded=(\d+)", text)
                    return (match.group(1), int(match.group(2))) if match else (None, None)

                async def wait(predicate, timeout=90):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        current = await state()
                        if predicate(current):
                            return current
                        await asyncio.sleep(0.2)
                    raise TimeoutError(f"video GUI state timeout; last={current}")

                async def click(label):
                    clicked = await evaluate(f"(()=>{{const b=[...document.querySelectorAll('button')].find(e=>e.innerText==={json.dumps(label)});if(!b||b.disabled)return false;b.click();return true}})()")
                    if not clicked:
                        raise RuntimeError(f"button unavailable: {label}")

                async def screenshot(name):
                    value = await call("Page.captureScreenshot", {"format": "png"})
                    (output / name).write_bytes(base64.b64decode(value["data"]))

                await call("Page.enable")
                await call("Runtime.enable")
                await wait(lambda value: value == ("Paused", 0))
                result["actions"]["initial_paused"] = True
                await screenshot("initial_paused.png")
                for count in range(1, 6):
                    await click("Step video")
                    await wait(lambda value: value == ("Paused", count))
                    await asyncio.sleep(0.3)
                    assert await state() == ("Paused", count)
                result["actions"]["five_single_steps"] = True
                await asyncio.sleep(2)
                assert await state() == ("Paused", 5)
                result["actions"]["paused_capture_stable"] = True
                if verify_bev:
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        if 'BEV 갱신됨' in (await evaluate('document.body.innerText') or ''):
                            break
                        await asyncio.sleep(.2)
                    else:
                        raise TimeoutError('first live BEV update missing')
                    result['actions']['first_bev_update'] = True
                    await screenshot('first_bev.png')
                if object_search:
                    async def wait_text(predicate, timeout=120):
                        deadline = time.monotonic() + timeout
                        while time.monotonic() < deadline:
                            text = await evaluate("document.body.innerText") or ""
                            if predicate(text):
                                return text
                            await asyncio.sleep(.2)
                        raise TimeoutError("object query UI timeout")

                    current_query = ""

                    async def search(query):
                        nonlocal current_query
                        expression = f"(()=>{{const e=[...document.querySelectorAll('input')].find(x=>x.type==='text'&&x.value==={json.dumps(current_query)});if(!e)return false;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(query)});e.dispatchEvent(new Event('input',{{bubbles:true}}));e.focus();return true}})()"
                        assert await evaluate(expression)
                        await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                        await call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                        current_query = query
                        await asyncio.sleep(.5)
                        await click("Search")
                        await wait_text(lambda text: f"Searching for '{query}'" in text)

                    await asyncio.sleep(3)
                    await wait_text(lambda text: "worker=idle" in text)
                    await search("car")
                    # Continue capture/inference during the first search, then pause again.
                    await click("Pause / Resume video")
                    await wait(lambda value: value[0] == "Running" and value[1] >= 9)
                    await click("Pause / Resume video")
                    paused = await wait(lambda value: value[0] == "Paused")
                    result["capture_during_search"] = paused[1]
                    for query in ("car", "tree"):
                        if query == "tree":
                            await search(query)
                        text = await wait_text(lambda text: "Found " in text or f"No instances found for '{query}'" in text or "Error:" in text)
                        if "Error:" in text:
                            raise RuntimeError(text)
                        found = re.search(r"Found (\d+) 3D instance", text)
                        result[f"{query}_boxes"] = int(found.group(1)) if found else 0
                        await screenshot(f"query_{query}.png")
                        await click("Clear boxes")
                        await wait_text(lambda text: "3D query boxes cleared" in text)
                        result["actions"][f"{query}_search_clear"] = True
                    assert result["car_boxes"] > 0
                    await search("elephant")
                    await click("Stop video")
                    await wait(lambda value: value[0] in {"Stopping", "Completed"}, timeout=30)
                    result["actions"]["stop_during_search"] = True
                    await screenshot("stopping_during_query.png")
                    result["status"] = "completed"
                    print(json.dumps(result, indent=2))
                    return
                await click("Pause / Resume video")
                await wait(lambda value: value[0] == "Running" and value[1] >= (10 if verify_bev else 7))
                result["actions"]["resume"] = True
                await click("Pause / Resume video")
                paused = await wait(lambda value: value[0] == "Paused")
                await asyncio.sleep(2)
                assert await state() == paused
                result["actions"]["pause_again_stable"] = True
                await click("Step video")
                stepped = await wait(lambda value: value == ("Paused", paused[1] + 1))
                result["actions"]["single_step_after_pause"] = True
                result["decoded_before_stop"] = stepped[1]
                if verify_bev:
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        text = await evaluate('document.body.innerText') or ''
                        match = re.search(r'BEV 갱신됨\s*·\s*(\d+) 서브맵', text)
                        if match and int(match.group(1)) >= 2:
                            result['bev_submaps'] = int(match.group(1))
                            break
                        await asyncio.sleep(.2)
                    else:
                        raise TimeoutError('second live BEV update missing')
                    result['actions']['incremental_bev_updates'] = True
                await screenshot("paused_after_step.png")
                await click("Stop video")
                await wait(lambda value: value[0] in {"Stopping", "Completed"}, timeout=30)
                result["actions"]["stop"] = True
                await screenshot("stopping.png")
                result["status"] = "completed"
        except Exception as exc:
            result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            (output / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--debug-port", type=int, default=9236)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--object-search", action="store_true")
    parser.add_argument("--verify-bev", action="store_true")
    args = parser.parse_args()
    asyncio.run(inspect(args.url, args.debug_port, args.output, args.object_search, args.verify_bev))


if __name__ == "__main__":
    main()
