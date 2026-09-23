# -*- coding: utf-8 -*-
"""管理 var/.pause_mode：平台 match_enabled=false 时冻结训练，恢复后自愈链自动解除。"""
from __future__ import annotations
import argparse, io, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "var"))
import _feature_mode as fm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("status", "pause", "resume"), nargs="?", default="status")
    ap.add_argument("--reason", default="FEATURE_DISABLED")
    a = ap.parse_args()
    if a.cmd == "pause":
        os.makedirs(os.path.dirname(fm.PAUSE_FLAG), exist_ok=True)
        with io.open(fm.PAUSE_FLAG, "w", encoding="utf-8") as f:
            f.write(str(a.reason) + "\n" + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        print("已暂停训练链：", fm.PAUSE_FLAG)
    elif a.cmd == "resume":
        try:
            os.remove(fm.PAUSE_FLAG)
            print("已解除暂停：", fm.PAUSE_FLAG)
        except FileNotFoundError:
            print("当前未暂停")
    ok = fm.feature_match_enabled()
    print("match_enabled=%s pause=%s" % (ok, fm.pause_requested()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
