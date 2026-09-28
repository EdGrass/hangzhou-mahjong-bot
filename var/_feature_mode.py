# -*- coding: utf-8 -*-
"""平台能力门：match_enabled=false 时冻结训练链，恢复后自动解除。"""
from __future__ import annotations
import json, os, ssl, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAUSE_FLAG = os.path.join(ROOT, "var", ".pause_mode")
BASE = "https://10.240.169.190:18080"


def feature_match_enabled(timeout=8):
    """GET /portal/api/features（免认证）；网络异常按 false 处理，保持暂停。"""
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(BASE + "/portal/api/features")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return bool(d.get("match_enabled"))
    except Exception:
        return False


def pause_requested():
    return os.path.exists(PAUSE_FLAG)


# R1592：B 段换役等待标记。_bsegment 在等当前房自然结束时置位，
# keeper/watchdog/ensure_all 看到它必须让出账号；_bsegment 正常结束/异常退出都会清掉。
# 残留超过 stale 秒自动失效，避免脚本被杀后永久停掉自愈链。
BSEG_WAIT_FLAG = os.path.join(ROOT, "var", ".bsegment_waiting")
BSEG_WAIT_STALE_SEC = 3600


def bsegment_waiting():
    """B 段正在等空档 ⇒ True；陈旧残留自动删除并返回 False。"""
    try:
        age = time.time() - os.path.getmtime(BSEG_WAIT_FLAG)
    except OSError:
        return False
    if age > BSEG_WAIT_STALE_SEC:
        try:
            os.remove(BSEG_WAIT_FLAG)
        except OSError:
            pass
        return False
    return True


def set_bsegment_waiting(on):
    if on:
        os.makedirs(os.path.dirname(BSEG_WAIT_FLAG), exist_ok=True)
        with open(BSEG_WAIT_FLAG, "w", encoding="utf-8") as f:
            f.write("pid=%d\n%s\n" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S")))
    else:
        try:
            os.remove(BSEG_WAIT_FLAG)
        except OSError:
            pass


def handle_pause_on_startup():
    """返回 True = 仍应暂停；False = 未暂停/刚解除，可继续启动链。"""
    if not pause_requested():
        return False
    if feature_match_enabled():
        try:
            os.remove(PAUSE_FLAG)
        except OSError:
            pass
        return False
    return True
