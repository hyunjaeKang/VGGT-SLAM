"""Local main viewport and synchronized RGB/BEV cards around the Viser client."""
import io
import json
import mimetypes
import socket
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.parse import unquote

from PIL import Image
import viser


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class MainPanel:
    def __init__(self, port):
        self.lock = threading.RLock()
        self.snapshots = OrderedDict()
        self.version = 0
        self.viser_port = None
        self.action = None
        self.resize = None
        self.viewport = (1280, 720, 1.)
        panel = self
        client_root = (Path(viser.__file__).parent / 'client' / 'build').resolve()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send_data(self, status, data, content_type):
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                url = urlsplit(self.path)
                if url.path.startswith('/viser/'):
                    relative = unquote(url.path[len('/viser/'):]) or 'index.html'
                    source = (client_root / relative).resolve()
                    if source.is_relative_to(client_root) and source.is_file():
                        self.send_data(200, source.read_bytes(), mimetypes.guess_type(source.name)[0] or 'application/octet-stream')
                    else:
                        self.send_data(404, b'Not found', 'text/plain')
                    return
                if url.path == '/':
                    data = (Path(__file__).parent / 'web' / 'studio.html').read_bytes()
                    self.send_data(200, data, 'text/html; charset=utf-8')
                    return
                with panel.lock:
                    if url.path == '/api/frame':
                        data = dict(panel.snapshots[panel.version]['meta']) if panel.version else {'version': 0}
                        data['viser_port'] = panel.viser_port
                        self.send_data(200, json.dumps(data).encode(), 'application/json')
                        return
                    key = url.path.strip('/').split('.')[0]
                    version = int(parse_qs(url.query).get('v', [panel.version])[0]) if parse_qs(url.query).get('v', [str(panel.version)])[0].isdigit() else 0
                    snapshot = panel.snapshots.get(version)
                    if key in ('rgb', 'bev', 'camera') and snapshot is not None:
                        self.send_data(200, snapshot[key], 'image/jpeg')
                        return
                self.send_data(404, b'Not found', 'text/plain')

            def do_POST(self):
                if self.path not in ('/api/action', '/api/viewport') or int(self.headers.get('Content-Length', '0')) > 1024:
                    self.send_data(400, b'Bad request', 'text/plain')
                    return
                try:
                    data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                    if self.path == '/api/viewport':
                        width, height, dpr = float(data['width']), float(data['height']), float(data.get('dpr', 1))
                        if not 64 <= width <= 10000 or not 64 <= height <= 10000 or not .5 <= dpr <= 4:
                            raise ValueError('invalid viewport')
                        viewport = (round(width / 16) * 16, round(height / 16) * 16, dpr)
                        if viewport != panel.viewport:
                            panel.viewport = viewport
                            if panel.resize is not None:
                                panel.resize()
                        self.send_data(200, b'{"ok":true}', 'application/json')
                        return
                    if data.get('action') not in ('reset', 'free', 'zoom_in', 'zoom_out', 'zoom_reset', 'road_overlay', 'trajectory', 'mask_3d', 'mask_rgb', 'mask_bev', 'box_bev', 'box_rgb', 'bev_view', 'frame', 'previous_frame', 'next_frame', 'play', 'pause') or panel.action is None:
                        raise ValueError('unknown action')
                    panel.action(data['action'], data)
                    self.send_data(200, b'{"ok":true}', 'application/json')
                except (ValueError, KeyError, TypeError):
                    self.send_data(400, b'Bad action', 'text/plain')

        self.http = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def publish(self, rgb, bev, camera, metadata):
        encoded = {}
        for name, image in [('rgb', rgb), ('bev', bev), ('camera', camera)]:
            buf = io.BytesIO()
            Image.fromarray(image).save(buf, format='JPEG', quality=95, subsampling=0)
            encoded[name] = buf.getvalue()
        with self.lock:
            self.version += 1
            encoded['meta'] = dict(metadata, version=self.version)
            self.snapshots[self.version] = encoded
            while len(self.snapshots) > 4:
                self.snapshots.popitem(last=False)

    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)

    def update_status(self, **metadata):
        with self.lock:
            if not self.version:
                return
            snapshot = dict(self.snapshots[self.version])
            self.version += 1
            snapshot['meta'] = dict(snapshot['meta'], **metadata, version=self.version)
            self.snapshots[self.version] = snapshot
            while len(self.snapshots) > 4:
                self.snapshots.popitem(last=False)
