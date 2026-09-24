# -*- coding: utf-8 -*-
"""平台能力门：match_enabled=false 时冻结训练链，恢复后自动解除。"""
from __future__ import annotations
import json, os, ssl, urllib.request

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
