"""Local version chooser; both viewers keep their own process/UI state."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VGGT · 버전 선택</title><style>body{background:#0f172a;color:#e2e8f0;font:18px/1.7 system-ui;max-width:900px;margin:10vh auto;padding:24px}a{color:#67e8f9}article{border:1px solid #334155;border-radius:16px;padding:24px;margin:20px 0}small{color:#94a3b8}</style><h1>VGGT · 데모 버전 선택</h1><article><h2><a href="http://localhost:8101">Classic V1 · 기존 버전</a></h2><p>현재 기능과 재생 방식을 보존한 버전. 프레임별 고화질 지도·검색·도로·BEV·뷰 조작.</p></article><article><h2><a href="http://localhost:8102">Smooth V2 · 부드러운 재생</a></h2><p>독립 시간축, 점군 부분 갱신, 재생 중 경량 표시·정지 시 고화질. 원본 RGB 영상과 카메라 시점 보간.</p><small>지도는 키프레임 기준이며, 보간 카메라는 새 SLAM 추정값이 아닙니다. RGB 분할·박스는 정지한 지도 프레임에서 확인하세요. KITTI 재생은 타임스탬프가 없어 명시한10fps를 사용합니다.</small></article></html>'''


def serve_picker(port=8100):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            body=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Version chooser: http://localhost:{port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
