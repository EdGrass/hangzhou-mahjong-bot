"""HTTP 传输层：Bearer 认证、自签 TLS、429 退避、统一错误。

纯标准库（urllib），与指南最小 Bot 同款姿势。
所有业务调用方只 import 本模块的 api() / ApiError。
"""
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 35      # state 长轮询最长挂起 30s，留 5s 余量
RATE_LIMIT_RETRIES = 2    # 429 退避重试次数（节流后极少触发）
RATE_LIMIT_BACKOFF = 1.0
NETWORK_RETRIES = 3       # 网络瞬断（URLError/超时）重试次数
NETWORK_BACKOFF = 1.0


class _Throttle:
    """进程级令牌桶：多桌并发共享同一 /state 16/s 上限（实测 429 风暴源）。"""

    def __init__(self, rate=12.0, burst=3):
        self.rate = rate
        self.burst = float(burst)
        self.tokens = float(burst)
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            while self.tokens < 1.0:
                now = time.monotonic()
                self.tokens = min(self.burst,
                                  self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens < 1.0:
                    time.sleep((1.0 - self.tokens) / self.rate)
            self.tokens -= 1.0
            self.last = time.monotonic()


# 2026-09-10 拆分（指南 v29）：/state 有独立 16 次/秒额度、notify 不计入该额度、
# /action 另有额度。此前三类请求共用一个 12/s 桶，10 场并发时动作提交被
# 轮询挤到窗口关闭之后——自动房实测吃 67%/碰 78% 被 409 拒绝（1109 次失败
# claim 中 66% 那张牌最终无人要，即我方迟到而非竞争）。
THROTTLE_STATE = _Throttle(rate=14.0, burst=4)     # 指南上限 16/s，留余量
THROTTLE_ACTION = _Throttle(rate=24.0, burst=8)    # 动作独立额度，不再排队
THROTTLE = THROTTLE_STATE                          # 兼容旧引用（notify 连接等）

_TRACING = os.environ.get("HM_API_TRACE") == "1"
_TRACE_LOCK = threading.Lock()


def _trace(rec):
    """请求级追踪（仅 HM_API_TRACE=1 时生效）——定位窗口延迟用。"""
    try:
        os.makedirs("var", exist_ok=True)
        line = json.dumps(rec, ensure_ascii=False)
        with _TRACE_LOCK:
            with open(os.path.join("var", "api_trace.jsonl"), "a",
                      encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


class ApiError(Exception):
    """HTTP 非 2xx 响应。body 为原始文本，code 为尽力解析出的错误码。"""

    def __init__(self, status, body):
        self.status = status
        self.body = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
        self.code = self._parse_code(self.body)
        super().__init__("HTTP %d %s: %s" % (self.status, self.code or "", self.body[:200]))

    @staticmethod
    def _parse_code(body):
        """服务端错误体可能是 JSON（如 {"error": {"code": "NOT_QUALIFIED"}}）或纯文本。"""
        if not body:
            return None
        try:
            obj = json.loads(body)
        except (ValueError, TypeError):
            return None
        # 常见几种形态都尽力找一下
        for key in ("code", "error"):
            v = obj.get(key)
            if isinstance(v, dict):
                v = v.get("code")
            if isinstance(v, str):
                return v
        return None


class Client:
    """一个带固定 Bearer 令牌的 API 客户端。"""

    def __init__(self, server, token=""):
        self.server = server.rstrip("/")
        self.token = token
        self._ctx = ssl._create_unverified_context()  # 部署实例为 caddy 自签证书

    # -- 底层请求 ------------------------------------------------------------
    def request(self, method, path, body=None, timeout=DEFAULT_TIMEOUT,
                kind="state"):
        """发一次请求；按 kind 选令牌桶 + 429 退避，其余 HTTP 错误抛 ApiError。

        kind="action" 走独立桶：/action 不在 /state 的 16/s 额度内（指南 v29），
        与轮询共桶会让窗口动作排队到窗口关闭之后。
        """
        th = THROTTLE_ACTION if kind == "action" else THROTTLE
        t0 = time.monotonic()
        th.acquire()
        t1 = time.monotonic()
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.server + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        status = 0
        try:
            for attempt in range(max(RATE_LIMIT_RETRIES, NETWORK_RETRIES) + 1):
                try:
                    with urllib.request.urlopen(req, timeout=timeout,
                                                context=self._ctx) as r:
                        raw = r.read().decode("utf-8", errors="replace")
                        status = getattr(r, "status", 200) or 200
                        try:
                            return json.loads(raw)
                        except ValueError:
                            return raw  # 个别端点返回非 JSON（如纯文本）也照常透传
                except urllib.error.HTTPError as e:
                    # HTTPError 是 URLError 子类，必须先于网络分支判断
                    status = e.code
                    text = e.read().decode("utf-8", errors="replace")
                    if e.code == 429 and attempt < RATE_LIMIT_RETRIES:
                        time.sleep(RATE_LIMIT_BACKOFF * (attempt + 1))
                        continue
                    raise ApiError(e.code, text)
                except urllib.error.URLError as e:
                    # 网络瞬断/超时：统一转 ApiError(0)，调用方按瞬时故障处理
                    status = 0
                    if attempt < NETWORK_RETRIES:
                        time.sleep(NETWORK_BACKOFF * (attempt + 1))
                        continue
                    raise ApiError(0, "network error: %s" % (e,))
            raise ApiError(429, "rate limited after %d retries" % RATE_LIMIT_RETRIES)
        finally:
            if _TRACING:
                q = ""
                if "?seq=" in path:
                    q = path.split("?seq=", 1)[1]
                _trace({"ts": round(time.time(), 3),
                        "seq": q,
                        "path": path.split("?")[0], "kind": kind,
                        "wait_ms": round((t1 - t0) * 1000.0, 1),
                        "http_ms": round((time.monotonic() - t1) * 1000.0, 1),
                        "status": status})

    # -- 便捷方法 ------------------------------------------------------------
    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body, **kw)

    def patch(self, path, body=None, **kw):
        return self.request("PATCH", path, body, **kw)

    # -- 具体端点 ------------------------------------------------------------
    def me(self):
        """GET /api/me：user_id + 令牌绑定的 tournament_id + active_games。"""
        return self.get("/api/me")

    def tournament_rules(self):
        """GET /api/tournaments/me/rules：报名令牌直达 config（全局令牌 400）。"""
        return self.get("/api/tournaments/me/rules")

    def tournament(self, tid):
        """GET /api/tournaments/{id}：status/config/my_games/ranking/阶段字段组。"""
        return self.get("/api/tournaments/%s" % tid)

    def register(self, tid):
        return self.post("/api/tournaments/%s/register" % tid, {})

    def ready(self, tid):
        return self.post("/api/tournaments/%s/ready" % tid, {})

    def game_state(self, gid, seq=0):
        """GET /api/games/{id}/state?seq=N：seq=0 全量快照；N>0 增量；挂起最多 30s。"""
        return self.get("/api/games/%s/state?seq=%d" % (gid, seq))

    def game_action(self, gid, action):
        """POST /api/games/{id}/action：服务端纯验证，非法 409。"""
        return self.post("/api/games/%s/action" % gid, action, kind="action")

    def match(self):
        """POST /api/match：自动匹配房建房与入席一体（v13+；仅门户绑定全局令牌）。
        返回 {room_id, config, ...}——room_id 即锦标赛 id（kind=auto）。"""
        return self.post("/api/match", {})

    def open_notify(self, gid, timeout=65):
        """GET /api/games/{id}/notify：SSE 通知流（v12+；不占 /state 的 16/s 额度，
        每用户 32 并发连接）。返回可逐行 readline 的响应对象（调用方负责 close）。
        帧形如 data:{"seq":N}（任意状态变更推帧）；30s keepalive 空行/注释行。
        失败抛 ApiError（429/404/网络）。"""
        THROTTLE.acquire()
        req = urllib.request.Request(
            self.server + "/api/games/%s/notify" % gid, method="GET")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=self._ctx)
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, e.read().decode("utf-8", errors="replace"))
        except urllib.error.URLError as e:
            raise ApiError(0, "network error: %s" % (e,))

    # -- 免认证门户端点 -------------------------------------------------------
    def guide_version(self):
        """GET /portal/api/guide/version：指南版本与变更日志（免认证，5/s）。"""
        return self.get("/portal/api/guide/version")

    def fan_calc(self, payload):
        """POST /portal/api/tools/fan-calc：番型试算（免认证，10/s/IP）。"""
        return self.post("/portal/api/tools/fan-calc", payload)
