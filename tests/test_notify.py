"""bot/notify SSE 客户端单测：本地假 SSE 服务器驱动 NotifyLine 解析。

覆盖：帧(data:{"seq":N})→event、keepalive(空行/注释)→keepalive、
closed 帧→down、服务器立即断开→down（回退长轮询语义）。
"""
import http.server
import json
import threading
import time
import unittest

from bot.notify import NotifyLine


class _SSEHandler(http.server.BaseHTTPRequestHandler):
    script = []            # [(delay, payload_bytes), ...]；payload None=关流

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for delay, payload in self.script:
                if delay:
                    time.sleep(delay)
                if payload is None:
                    return                      # 关流（不加 closed 帧）
                self.wfile.write(payload)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *a):
        pass


class _FakeClient:
    def __init__(self, server):
        self.server = server

    def open_notify(self, gid, timeout=65):
        import ssl
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/games/%s/notify" % (self.server, gid))
        return urllib.request.urlopen(req, timeout=timeout)


def _serve(script):
    _SSEHandler.script = script
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SSEHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


class TestNotifyLine(unittest.TestCase):
    def test_events_and_keepalive(self):
        srv = _serve([
            (0, b'data: {"seq": 3}\n\n'),
            (0, b': keepalive\n\n'),
            (0, b'data: {"seq": 4}\n\n'),
            (0.2, None),
        ])
        try:
            nl = NotifyLine(_FakeClient(srv.server_port), "g1")
            nl.start()
            evs = []
            t0 = time.time()
            while time.time() - t0 < 5 and not nl.down:
                evs.append(nl.wait_event(timeout=1.0))
            # 语义断言：收到 ≥2 个 event、含 keepalive（空行/注释行均合法）、
            # 关流后 down
            self.assertGreaterEqual(evs.count("event"), 2, evs)
            self.assertIn("keepalive", evs)
            self.assertTrue(nl.down)
        finally:
            srv.shutdown()

    def test_immediate_close_is_down(self):
        srv = _serve([(0, None)])
        try:
            nl = NotifyLine(_FakeClient(srv.server_port), "g2")
            nl.start()
            t0 = time.time()
            evs = []
            while time.time() - t0 < 3:
                ev = nl.wait_event(timeout=0.5)
                if ev == "down":
                    evs.append(ev)
                    break
                evs.append(ev)
            self.assertIn("down", evs)
            self.assertTrue(nl.down)
        finally:
            srv.shutdown()

    def test_closed_frame_is_down(self):
        srv = _serve([
            (0, b'data: {"seq": 9, "closed": true}\n\n'),
            (0.2, None),
        ])
        try:
            nl = NotifyLine(_FakeClient(srv.server_port), "g3")
            nl.start()
            t0 = time.time()
            while time.time() - t0 < 3 and not nl.down:
                nl.wait_event(timeout=0.5)
            self.assertTrue(nl.down)
        finally:
            srv.shutdown()

    def test_connection_refused_is_down(self):
        # 无服务器 → open_notify 抛 → 线程 down
        nl = NotifyLine(_FakeClient(1), "g4")   # port 1 几乎必拒
        nl.start()
        t0 = time.time()
        while time.time() - t0 < 4 and not nl.down:
            nl.wait_event(timeout=0.5)
        self.assertTrue(nl.down)


if __name__ == "__main__":
    unittest.main()
