"""HTTP 传输层：Bearer 认证、自签 TLS、429 退避、统一错误。

纯标准库（urllib），与指南最小 Bot 同款姿势。
所有业务调用方只 import 本模块的 api() / ApiError。
"""
import json
import ssl
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 35      # state 长轮询最长挂起 30s，留 5s 余量
RATE_LIMIT_RETRIES = 5    # 429 最大退避重试次数
RATE_LIMIT_BACKOFF = 2.0  # 429 初始退避秒数
NETWORK_RETRIES = 3       # 网络瞬断（URLError/超时）重试次数
NETWORK_BACKOFF = 1.0


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
    def request(self, method, path, body=None, timeout=DEFAULT_TIMEOUT):
        """发一次请求；429 退避重试，其余 HTTP 错误抛 ApiError。返回已解析 JSON。"""
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.server + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        for attempt in range(max(RATE_LIMIT_RETRIES, NETWORK_RETRIES) + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=self._ctx) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                    try:
                        return json.loads(raw)
                    except ValueError:
                        return raw  # 个别端点返回非 JSON（如纯文本）也照常透传
            except urllib.error.URLError as e:
                # 网络瞬断/超时：统一转 ApiError(0)，调用方按瞬时故障处理
                if attempt < NETWORK_RETRIES:
                    time.sleep(NETWORK_BACKOFF * (attempt + 1))
                    continue
                raise ApiError(0, "network error: %s" % (e,))
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < RATE_LIMIT_RETRIES:
                    time.sleep(RATE_LIMIT_BACKOFF * (attempt + 1))
                    continue
                raise ApiError(e.code, e.read().decode("utf-8", errors="replace"))
        raise ApiError(429, "rate limited after %d retries" % RATE_LIMIT_RETRIES)

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
        return self.post("/api/games/%s/action" % gid, action)

    # -- 免认证门户端点 -------------------------------------------------------
    def guide_version(self):
        """GET /portal/api/guide/version：指南版本与变更日志（免认证，5/s）。"""
        return self.get("/portal/api/guide/version")

    def fan_calc(self, payload):
        """POST /portal/api/tools/fan-calc：番型试算（免认证，10/s/IP）。"""
        return self.post("/portal/api/tools/fan-calc", payload)
