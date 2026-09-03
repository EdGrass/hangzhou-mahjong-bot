"""tools/preflight —— 开赛前一键体检（退出码 0=就绪）。

检查：① 服务器可达 & 指南版本（未知 BREAKING 报警）
      ② fan-calc 抽样与本地引擎判定一致（5 例确定性探针）
      ③ 本地测试/黄金集就绪
      ④ 正式赛 bot 是否在本机运行（ps 探测 run_bot.py）
用法：python tools/preflight.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bot                                  # noqa: E402
from bot.api import ApiError, Client        # noqa: E402
from mahjong.hu import is_baotou, is_win    # noqa: E402
from bot.util import ensure_utf8, log       # noqa: E402

PROBES = [
    (["1w", "1w", "1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "东", "东"], "东"),
    (["1w", "1w", "2w", "2w", "3b", "3b", "4t", "4t", "5t", "5t", "东", "东", "南"], "白"),
    (["1w", "2w", "3w", "4w", "5w", "6w", "7w", "8w", "9w", "1b", "1b", "1b", "白"], "东"),
]


def main():
    ensure_utf8()
    ok = True
    client = Client("https://10.240.169.190:18080")

    # 1) 服务器 + 指南版本
    try:
        meta = client.guide_version()
        ver = meta.get("version")
        log("服务器指南 v%s（本 bot v%s）", ver, bot.GUIDE_VERSION_KNOWN)
        if not isinstance(ver, int) or ver < bot.GUIDE_VERSION_KNOWN:
            ok = False
            log("✗ 版本异常：请人工核对")
        elif ver > bot.GUIDE_VERSION_KNOWN:
            brk = [c["summary"] for c in (meta.get("changes") or [])
                   if c.get("type") == "breaking" and c.get("version", 0) > bot.GUIDE_VERSION_KNOWN]
            if brk:
                ok = False
                for b in brk:
                    log("✗ 未知 BREAKING: %s", b)
            else:
                log("⚠ 服务器有更新但无 BREAKING（可运行，建议核对）")
        else:
            log("✓ 版本一致")
    except ApiError as e:
        ok = False
        log("✗ 服务器不可达: %s %s", e.status, e.code or e.body[:100])

    # 2) fan-calc 抽样一致
    try:
        bad = 0
        for hand, draw in PROBES:
            r = client.fan_calc({"hand": hand, "draw": draw,
                                 "chain": {"count": 0, "piao": 0}, "base": 1})
            mine_hu = is_win(hand + [draw])
            if bool(r.get("hu")) != mine_hu:
                bad += 1
        if bad:
            ok = False
            log("✗ fan-calc 抽样 %d/%d 不一致", bad, len(PROBES))
        else:
            log("✓ fan-calc 抽样 %d 例全部一致", len(PROBES))
    except ApiError as e:
        ok = False
        log("✗ fan-calc 调用失败: %s %s", e.status, e.code or e.body[:100])

    # 3) 本地单测快速子集（引擎相关）
    r = subprocess.run([sys.executable, "-m", "unittest",
                        "tests.test_hu", "tests.test_fan_golden",
                        "tests.test_shanten_exact"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        ok = False
        log("✗ 引擎单测未通过")
    else:
        log("✓ 引擎单测通过")

    # 4) bot 进程探测（本机）
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -match 'run_bot.py' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=20)
        n = int((out.stdout or "0").strip() or 0)
        if n > 0:
            log("✓ 检测到 %d 个 run_bot 进程", n)
        else:
            log("⚠ 本机无 run_bot 进程（若由看门狗/其他机器托管可忽略）")
    except Exception:
        log("⚠ 进程探测不可用（跳过）")

    log("体检结果: %s" % ("READY" if ok else "NOT READY"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
