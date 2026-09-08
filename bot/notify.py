"""notify —— /api/games/{id}/notify SSE 客户端（M 并发轮询预算解药）。

背景：自动匹配房 M=10 / 正式窗 M 桌并发下，各场独立 30s 长轮询 /state 会在
事件密集期撞上每用户 16/s 聚合限速（本地再叠加 12/s 节流）→ 窗口响应延迟 →
409 INVALID_ACTION 风暴（实测 M=10 自动房每场 pass 大量 409）。notify 通道
（指南 v12+）不占 /state 频率额度（每用户 32 并发连接），任意状态变更即推
{"seq":N} 帧，客户端收帧后才按需拉 /state → 请求数与事件批次数成正比。

语义（与 game.py 集成）：
- 每场一条 notify 连接 + 一个 daemon 线程，事件经 queue 送达主循环；
- 帧 data:{"seq":N} / data:{"seq":N,"closed":true}；
  30s keepalive = 空行或 ": ..." 注释行（推送 'keepalive' 供主循环做周期兜底）；
- 连接失败/中途断连/closed → 线程退出并推送 'down'（主循环回退传统长轮询；
  v1 保守：本场不再自动重连——重连价值低且增加协议面）；
- wait_event(timeout) 超时返回 "timeout"（调用方视作 keepalive 等价即可）。

逃生门：环境变量 HM_NO_NOTIFY=1 禁用（回退纯长轮询）。
"""
from __future__ import annotations

import json
import queue
import threading

from .util import log


class NotifyLine:
    def __init__(self, client, gid, idle_timeout=65):
        self.client = client
        self.gid = gid
        self.idle_timeout = idle_timeout   # socket 读超时须 > 30s keepalive 间隔
        self._q = queue.Queue(maxsize=64)
        self._th = None
        self.down = False                  # 主循环只读标志（真 down 后不再重连）

    # ---------- 线程 ----------
    def start(self):
        if self._th is not None:
            return
        self._th = threading.Thread(target=self._run, daemon=True,
                                    name="notify-%s" % str(self.gid)[-20:])
        self._th.start()

    def _run(self):
        resp = None
        try:
            resp = self.client.open_notify(self.gid, timeout=self.idle_timeout)
            # HTTP 200 后逐行读 SSE；行间间隔由服务器 keepalive 保证 < 30s
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    self._put("keepalive")
                elif line.startswith(":"):
                    self._put("keepalive")     # 注释行 = keepalive
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        obj = json.loads(payload)
                    except ValueError:
                        continue
                    if obj.get("closed"):
                        self._put("down")      # 场终/死场关流：交给主循环收尾
                        return
                    if isinstance(obj, dict) and "seq" in obj:
                        self._put("event")
        except Exception as e:  # noqa: BLE001（网络/429/404 → down 降级）
            self._put("down")
            log("notify 不可用(%s: %s) → 该场回退长轮询", self.gid,
                str(e)[:120])
        finally:
            try:
                if resp is not None:
                    resp.close()
            except Exception:
                pass
            self.down = True
            try:
                self._q.put_nowait("down")
            except queue.Full:
                pass

    def _put(self, ev):
        try:
            self._q.put_nowait(ev)
        except queue.Full:
            pass                       # 队列满：主循环必在消费，丢 keepalive 无害

    # ---------- 主循环侧 ----------
    def wait_event(self, timeout=31.0):
        """返回 'event' | 'keepalive' | 'down' | 'timeout'。"""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return "timeout"

    def close(self):
        """终止线程（尽力而为；daemon 线程随进程回收）。"""
        try:
            self._q.put_nowait("down")
        except queue.Full:
            pass
