"""通用小工具：日志输出与服务器地址解析。"""
from __future__ import annotations

import os
import sys
import time

# 部署实例（caddy 自签证书）；可用环境变量 HM_SERVER 覆盖，本地调试可指 http://localhost:8080
DEFAULT_SERVER = "https://10.240.169.190:18080"

# 可选日志文件（双写；run_bot --log 设置，多实例分析用）
LOG_FILE = None


def server_from_env():
    return os.environ.get("HM_SERVER", "").strip() or DEFAULT_SERVER


def ensure_utf8():
    """Windows 控制台 GBK 兜底：强制 UTF-8 输出，防止中文日志乱码/抛错。"""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def log(*args):
    """带时间戳日志。兼容三种写法：
        log("纯文本")                                 单参数
        log("格式化: %s / %d", a, b)                  printf 风格（自动 % 格式化）
        log("前缀:", obj)                             多参数（空格拼接）
    """
    ts = time.strftime("%H:%M:%S")
    if len(args) == 1:
        msg = str(args[0])
    else:
        first = args[0]
        if isinstance(first, str) and "%" in first:
            try:
                msg = first % args[1:]
            except (TypeError, ValueError):
                msg = " ".join(str(a) for a in args)
        else:
            msg = " ".join(str(a) for a in args)
    print("[%s] %s" % (ts, msg), flush=True)
    if LOG_FILE is not None:
        try:
            LOG_FILE.write("[%s] %s\n" % (ts, msg))
            LOG_FILE.flush()
        except (OSError, ValueError):
            pass
